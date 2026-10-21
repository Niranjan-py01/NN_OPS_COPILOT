# NN-Ops-Copilot — Phase 1 MVP

Local-first DBA Copilot for Microsoft SQL Server: Streamlit UI, FastAPI API, PostgreSQL audit metadata, Qdrant RAG, Ollama inference, and optional read-only SQL Server collectors.

## Run locally (Python 3.11 recommended)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d postgres qdrant
ollama pull llama3.2
ollama pull nomic-embed-text
```
Start Ollama if it is not already running. In terminal 1:
```powershell
uvicorn backend.main:app --reload
```
In terminal 2:
```powershell
streamlit run frontend/streamlit_app.py
```
API docs: http://127.0.0.1:8000/docs

Set `DEMO_MODE=true` for sample metrics. They are synthetic and are never live telemetry. To enable live collectors, set `DEMO_MODE=false` and configure `SQLSERVER_CONNECTION_STRING` using a dedicated least-privilege read-only login and Microsoft ODBC Driver 18.

## Important
This is a development MVP scaffold, not a security-certified production system. Before production add enterprise authentication/SSO, enforce real RBAC and server/customer authorization, TLS, a secrets manager, network restrictions, migrations, rate limiting, backup/restore testing, monitoring, and security review. Do not expose PostgreSQL or Qdrant publicly. Chat does not execute arbitrary SQL.
