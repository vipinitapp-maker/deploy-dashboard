# 🚀 GuardianHub Deployment Center

A real-time, local deployment orchestration dashboard built with **FastAPI**, **WebSockets**, and **Tailwind CSS**. 

This application provides a single-pane-of-glass interface to trigger isolated service builds, stream live console outputs (`stdout`/`stderr`), and monitor Kubernetes rollout statuses for the **GuardianHub** platform ecosystem.

---

## 🌟 Key Features

- **Directory-Isolated Execution**: Automatically executes build and deploy scripts within their exact repository working directories (`agentverse-studio`, `yantramops-guardianhub`, `mcp-registry`).
- **Real-Time Log Streaming**: Streams terminal output live to the web UI using WebSockets.
- **Kubernetes Rollout Verification**: Automatically runs `kubectl rollout status` and displays real-time health badges (**Deployed & Ready**, **Building & Deploying...**, **Progressing**, or **Failed**).
- **Batch Deployment**: Trigger single service rebuilds or execute sequential full-stack deployments with one click.
- **Dark-Mode UI**: Built with a responsive, modern terminal-themed dashboard.

---

## 📁 Repository Directory Mapping

The dashboard manages deployments across distinct codebase directories on your local environment:

| Service Name | Namespace | Target Working Directory | Deployment Script |
| :--- | :--- | :--- | :--- |
| **Agentverse Studio** | `yantram-core` | `/Users/vipintiwari/codec/agentverse-studio` | `./ops/build_deploy/build_service_guardianhub.sh agentverse-studio --target guardianhub -n yantram-core` |
| **Tool Registry** | `yantram-core` | `/Users/vipintiwari/codec/yantramops-guardianhub` | `./ops/build_deploy/build_service_guardianhub.sh tool-registry --target guardianhub -n yantram-core` |
| **Sutram AI Host** | `yantram-core` | `/Users/vipintiwari/codec/yantramops-guardianhub` | `./ops/build_deploy/build_service_guardianhub.sh sutram-ai-host --target guardianhub -n yantram-core` |
| **Lexguard Compliance** | `yantram-agents` | `/Users/vipintiwari/codec/mcp-registry` | `./ops/build_deploy/build_service_guardianhub.sh lexguard-compliance --target guardianhub -n yantram-agents` |
| **Data Principal** | `yantram-agents` | `/Users/vipintiwari/codec/mcp-registry` | `./ops/build_deploy/build_service_guardianhub.sh data-principal --target guardianhub -n yantram-agents` |

---

## 🏗️ Project Structure

```text
deploy-dashboard/
├── app.py              # FastAPI backend, WebSocket manager, & Subprocess orchestrator
├── static/
│   └── index.html      # Dark-mode dashboard UI with Tailwind CSS & WS client
├── requirements.txt    # Python dependencies
├── .gitignore          # Git exclusion rules
└── README.md
