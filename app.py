import asyncio
import json
import os
import subprocess
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="GuardianHub Local Deployment Manager")

# Service Configuration Mapping
SERVICES_CONFIG = {
    "agentverse-studio": {
        "name": "Agentverse Studio",
        "deployment": "agentverse-studio",
        "namespace": "yantram-core",
        "working_dir": "/Users/vipintiwari/codec/agentverse-studio",
        "build_cmd": "./ops/build_deploy/build_service_guardianhub.sh agentverse-studio --target guardianhub -n yantram-core",
        "category": "Core / Agentverse"
    },
    "tool-registry": {
        "name": "Tool Registry",
        "deployment": "tool-registry",
        "namespace": "yantram-core",
        "working_dir": "/Users/vipintiwari/codec/yantramops-guardianhub",
        "build_cmd": "./ops/build_deploy/build_service_guardianhub.sh tool-registry --target guardianhub -n yantram-core",
        "category": "Core"
    },
    "sutram-ai-host": {
        "name": "Sutram AI Host",
        "deployment": "sutram-ai-host",
        "namespace": "yantram-core",
        "working_dir": "/Users/vipintiwari/codec/yantramops-guardianhub",
        "build_cmd": "./ops/build_deploy/build_service_guardianhub.sh sutram-ai-host --target guardianhub -n yantram-core",
        "category": "Core"
    },
    "lexguard-compliance": {
        "name": "Lexguard Compliance",
        "deployment": "lexguard-compliance",
        "namespace": "yantram-agents",
        "working_dir": "/Users/vipintiwari/codec/mcp-registry",
        "build_cmd": "./ops/build_deploy/build_service_guardianhub.sh lexguard-compliance --target guardianhub -n yantram-agents",
        "category": "Agents"
    },
    "data-principal": {
        "name": "Data Principal",
        "deployment": "data-principal",
        "namespace": "yantram-agents",
        "working_dir": "/Users/vipintiwari/codec/mcp-registry",
        "build_cmd": "./ops/build_deploy/build_service_guardianhub.sh data-principal --target guardianhub -n yantram-agents",
        "category": "Agents"
    }
}


class DeploymentStatus(BaseModel):
    service_id: str
    name: str
    deployment: str
    namespace: str
    working_dir: str
    status: str  # "READY", "NOT_FOUND", "PROGRESSING", "FAILED", "BUILDING"
    replicas: str
    category: str


# Serve static frontend files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get_index():
    return FileResponse("static/index.html")


@app.get("/api/services")
async def get_services():
    """Return configured services metadata."""
    return list(SERVICES_CONFIG.values())


@app.get("/api/status", response_model=List[DeploymentStatus])
async def get_status():
    """Query Kubernetes for current status of all deployments."""
    statuses = []
    for svc_id, cfg in SERVICES_CONFIG.items():
        deployment = cfg["deployment"]
        namespace = cfg["namespace"]

        # Check deployment via kubectl
        cmd = f"kubectl get deployment {deployment} -n {namespace} -o json"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            try:
                data = json.loads(stdout.decode())
                spec_replicas = data.get("spec", {}).get("replicas", 0)
                ready_replicas = data.get("status", {}).get("readyReplicas", 0)

                if ready_replicas == spec_replicas and spec_replicas > 0:
                    status_str = "READY"
                else:
                    status_str = "PROGRESSING"
                replicas_str = f"{ready_replicas}/{spec_replicas}"
            except Exception:
                status_str = "UNKNOWN"
                replicas_str = "0/0"
        else:
            status_str = "NOT_FOUND"
            replicas_str = "0/0"

        statuses.append(DeploymentStatus(
            service_id=svc_id,
            name=cfg["name"],
            deployment=deployment,
            namespace=namespace,
            working_dir=cfg["working_dir"],
            status=status_str,
            replicas=replicas_str,
            category=cfg["category"]
        ))
    return statuses


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


ws_manager = WebSocketManager()


@app.websocket("/ws/deploy")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            req = json.loads(data)
            action = req.get("action")

            if action == "deploy_service":
                svc_id = req.get("service_id")
                if svc_id in SERVICES_CONFIG:
                    asyncio.create_task(run_deployment_pipeline(svc_id))
            elif action == "deploy_all":
                for svc_id in SERVICES_CONFIG.keys():
                    await run_deployment_pipeline(svc_id)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def run_cmd_and_stream(svc_id: str, cmd: str, cwd: str):
    """Executes shell commands in a designated directory and streams terminal output."""
    await ws_manager.broadcast({
        "type": "log",
        "service_id": svc_id,
        "line": f"\n[DIR: {cwd}] $ {cmd}\n"
    })

    # Ensure working directory exists
    if not os.path.exists(cwd):
        await ws_manager.broadcast({
            "type": "log",
            "service_id": svc_id,
            "line": f"[ERROR] Directory does not exist: {cwd}\n"
        })
        return False

    proc = await asyncio.create_subprocess_shell(
        cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        decoded_line = line.decode('utf-8', errors='replace')
        await ws_manager.broadcast({
            "type": "log",
            "service_id": svc_id,
            "line": decoded_line
        })

    await proc.wait()
    return proc.returncode == 0


async def run_deployment_pipeline(svc_id: str):
    """Orchestrates deletion, build/deploy, and k8s status rollout check."""
    cfg = SERVICES_CONFIG[svc_id]
    deployment = cfg["deployment"]
    namespace = cfg["namespace"]
    cwd = cfg["working_dir"]
    build_cmd = cfg["build_cmd"]

    await ws_manager.broadcast({
        "type": "status_update",
        "service_id": svc_id,
        "status": "BUILDING"
    })

    # Step 1: Delete existing K8s deployment
    delete_cmd = f"kubectl delete deployment {deployment} -n {namespace} --ignore-not-found=true"
    await run_cmd_and_stream(svc_id, delete_cmd, cwd)

    # Step 2: Trigger build and deploy script from working directory
    success = await run_cmd_and_stream(svc_id, build_cmd, cwd)

    if not success:
        await ws_manager.broadcast({
            "type": "status_update",
            "service_id": svc_id,
            "status": "FAILED"
        })
        return

    # Step 3: Wait for Kubernetes Rollout completion
    await ws_manager.broadcast({
        "type": "log",
        "service_id": svc_id,
        "line": f"\n[K8S] Waiting for deployment '{deployment}' rollout in namespace '{namespace}'...\n"
    })

    rollout_cmd = f"kubectl rollout status deployment/{deployment} -n {namespace} --timeout=180s"
    rollout_success = await run_cmd_and_stream(svc_id, rollout_cmd, cwd)

    final_status = "READY" if rollout_success else "FAILED"
    await ws_manager.broadcast({
        "type": "status_update",
        "service_id": svc_id,
        "status": final_status
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8090, reload=True)