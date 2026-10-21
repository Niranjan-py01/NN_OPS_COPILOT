import os
import requests
import streamlit as st

st.set_page_config(page_title="NN-Ops-Copilot", page_icon="🛡️", layout="wide")
API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

st.title("🛡️ NN-Ops-Copilot")
st.caption("Phase 1 · DBA Operations Copilot · Local-first · Read-only by design")

with st.sidebar:
    st.header("Workspace")
    actor = st.text_input("Operator ID", value="local-user")
    st.info("Phase 1 is read-only. It does not execute changes against SQL Server.")
    st.caption("Demo metrics are illustrative, not live telemetry.")

overview, copilot, knowledge, status = st.tabs(
    ["Overview", "DBA Copilot", "Knowledge Base", "Platform Status"]
)

with overview:
    st.subheader("DBA Operations Overview")
    try:
        response = requests.get(f"{API_BASE}/api/dashboard", timeout=10)
        response.raise_for_status()
        data = response.json()
        mode = data.get("mode")

        if mode == "demo":
            st.warning("DEMO MODE — sample metrics only; not live SQL Server telemetry.")
        elif mode == "live":
            st.success("Connected to live read-only collectors.")
        else:
            st.error(data.get("message", "Collector status unavailable"))

        metrics = data.get("metrics", {})
        if mode == "demo":
            columns = st.columns(3)
            for index, (key, item) in enumerate(metrics.items()):
                with columns[index % 3]:
                    st.metric(key.replace("_", " ").title(), item.get("value", "N/A"))
                    st.caption(item.get("description", ""))
                    if item.get("status") == "warning":
                        st.warning("Review")
                    elif item.get("status") == "healthy":
                        st.success("Healthy")
                    else:
                        st.info("Informational")
        else:
            st.json(metrics)
    except requests.RequestException as exc:
        st.error("FastAPI is not reachable. Run: uvicorn backend.main:app --reload")
        st.caption(f"Details: {exc.__class__.__name__}")
    except ValueError:
        st.error("FastAPI returned an invalid JSON response for the dashboard.")

    st.markdown("### Phase 1 capabilities")
    st.write("- Read-only SQL Server collectors")
    st.write("- Local Ollama explanations")
    st.write("- Qdrant retrieval from internal knowledge")
    st.write("- Audit event recording")

with copilot:
    st.subheader("Ask the DBA Copilot")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                st.caption("Sources: " + ", ".join(message["sources"]))

    prompt = st.chat_input("Example: What should I check when SQL Server has blocking?")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Applying policy and querying the local model..."):
                try:
                    response = requests.post(
                        f"{API_BASE}/api/chat",
                        json={"message": prompt, "actor": actor},
                        timeout=150,
                    )
                    if response.ok:
                        data = response.json()
                        answer = data.get("answer", "No answer returned.")
                        sources = list(
                            dict.fromkeys(
                                item.get("source", "unknown")
                                for item in data.get("sources", [])
                            )
                        )
                    else:
                        answer = f"API error ({response.status_code}): {response.text}"
                        sources = []

                    st.markdown(answer)
                    if sources:
                        st.caption("Sources: " + ", ".join(sources))
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer, "sources": sources}
                    )
                except requests.RequestException:
                    answer = "Cannot reach FastAPI. Start the backend and retry."
                    st.error(answer)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer, "sources": []}
                    )
                except ValueError:
                    answer = "FastAPI returned an invalid JSON response."
                    st.error(answer)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer, "sources": []}
                    )

with knowledge:
    st.subheader("Internal Knowledge Base")
    st.write("Upload approved DBA runbooks, SOPs, and RCA documents for Qdrant indexing.")
    uploaded = st.file_uploader("Choose PDF, TXT, or Markdown", type=["pdf", "txt", "md"])

    if uploaded and st.button("Index document", type="primary"):
        try:
            response = requests.post(
                f"{API_BASE}/api/knowledge/upload",
                files={
                    "file": (
                        uploaded.name,
                        uploaded.getvalue(),
                        uploaded.type or "application/octet-stream",
                    )
                },
                timeout=180,
            )
            if response.ok:
                try:
                    response_data = response.json()
                    message = response_data.get("message", "Document indexed successfully.")
                except ValueError:
                    message = "Document indexed successfully."
                st.success(message)
            else:
                st.error(f"Indexing failed ({response.status_code}): {response.text}")
        except requests.RequestException as exc:
            st.error("Cannot reach FastAPI. Check that the backend is running.")
            st.caption(f"Details: {exc.__class__.__name__}")

    st.warning(
        "Single-tenant MVP: upload only approved internal documents. "
        "Multi-customer retrieval isolation needs additional implementation."
    )

with status:
    st.subheader("Platform Health")
    if st.button("Check API"):
        try:
            response = requests.get(f"{API_BASE}/health", timeout=5)
            response.raise_for_status()
            st.json(response.json())
        except requests.RequestException:
            st.error("API unavailable. Check the FastAPI terminal.")
        except ValueError:
            st.error("API returned an invalid JSON response.")

    st.markdown("**Local service endpoints**")
    st.code(
        "FastAPI  http://127.0.0.1:8000\n"
        "Ollama   http://127.0.0.1:11434\n"
        "Qdrant   http://127.0.0.1:6335\n"
        "Postgres 127.0.0.1:5432"
    )
    st.caption("Qdrant host port assumes Docker maps 127.0.0.1:6335 to container port 6333.")
