
from contextlib import asynccontextmanager
import io
import json
import logging
import re

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from pypdf import PdfReader

from .config import APP_NAME, DEMO_MODE, MAX_UPLOAD_MB
from .policy import check_chat_request
from .audit import audit_event
from .llm import generate_answer
from .rag import retrieve, ingest_document
from .sqlquery import get_metrics

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    actor: str = Field(default="local-user", max_length=100)


def _needs_live_metrics(question: str) -> bool:
    """Identify questions that may require current diagnostic metrics."""
    pattern = (
        r"\bdatabase\s+size\b"
        r"|\bsize\s+of\s+(?:the\s+)?[\w.-]+\s+database\b"
        r"|\bactive\s+requests?\b"
        r"|\bblocking\s+(?:sessions?|requests?|status)\b"
        r"|\bcurrent\s+blocking\b"
        r"|\blive\s+metrics\b"
        r"|\bdashboard\s+metrics\b"
        r"|\bdatabase\s+health\b"
        r"|\bdiagnostic\s+metrics\b"
    )
    return bool(re.search(pattern, question, flags=re.IGNORECASE))


def _format_live_metrics(metrics_result: dict) -> str:
    """Format diagnostic results as clearly identified tool evidence."""
    return (
        "VERIFIED LIVE TOOL RESULT\n"
        "The following data was returned by the application's "
        "get_metrics() diagnostic function during this request. "
        "It is a point-in-time result. Do not invent or extrapolate "
        "additional metric values.\n"
        f"{json.dumps(metrics_result, ensure_ascii=False, default=str)}"
    )


def _answer_database_size(
    question: str,
    metrics_result: dict,
) -> str | None:
    """
    Answer database-size questions directly from live diagnostic data.

    Returns None if the question is not a database-size question.
    Never estimates or invents a database size.
    """
    asks_size = bool(
        re.search(r"\bsize\b", question, flags=re.IGNORECASE)
        and re.search(r"\bdatabase\b", question, flags=re.IGNORECASE)
    )

    if not asks_size:
        return None

    metrics = metrics_result.get("metrics", {})
    database_sizes = metrics.get("database_sizes", {})
    rows = database_sizes.get("rows", [])

    # Identify a requested database name, for example:
    # "What is the size of the NNOpsTest database?"
    requested_db = re.search(
        r"\b(?:of|for)\s+(?:the\s+)?"
        r"([A-Za-z0-9_.-]+)\s+database\b",
        question,
        flags=re.IGNORECASE,
    )

    requested_name = (
        requested_db.group(1).strip()
        if requested_db
        else None
    )

    if requested_name:
        matching_rows = [
            row for row in rows
            if str(row.get("database_name", "")).casefold()
            == requested_name.casefold()
        ]
    else:
        # If no specific database is named, return the available
        # database sizes rather than selecting an arbitrary row.
        matching_rows = rows

    if not matching_rows:
        if requested_name:
            return (
                "Summary:\n"
                f"No live database-size result was returned for "
                f"{requested_name}.\n\n"
                "Evidence:\n"
                "The requested database was not found in the "
                "current database_sizes diagnostic results.\n\n"
                "Safe Read-Only Next Steps:\n"
                "Check the database name and refresh the dashboard.\n\n"
                "Risks:\n"
                "No size has been inferred or estimated.\n\n"
                "Uncertainty:\n"
                "The requested database size could not be verified "
                "from the available live results."
            )
        return (
            "Summary:\n"
            "No database-size rows were returned by the live diagnostic.\n\n"
            "Evidence:\n"
            "The database_sizes result contained no matching rows.\n\n"
            "Safe Read-Only Next Steps:\n"
            "Refresh the dashboard and check SQL Server connectivity "
            "and diagnostic permissions.\n\n"
            "Risks:\n"
            "No database size has been inferred or estimated.\n\n"
            "Uncertainty:\n"
            "The current database sizes are unavailable."
        )

    # Validate each size before presenting it as a result.
    valid_rows = [
        row for row in matching_rows
        if row.get("database_name") is not None
        and row.get("size_mb") is not None
    ]

    if not valid_rows:
        return (
            "The live diagnostic did not provide a database name "
            "and size value that could be verified."
        )

    lines = [
        f"- {row['database_name']}: {row['size_mb']} MB"
        for row in valid_rows
    ]

    return (
        "Summary:\n"
        "Database size from the latest live diagnostic:\n"
        + "\n".join(lines)
        + "\n\nEvidence:\n"
        "These values came directly from the application's "
        "approved SQL Server database-size diagnostic during "
        "this request.\n\n"
        "Safe Read-Only Next Steps:\n"
        "Refresh the dashboard to retrieve an updated point-in-time "
        "measurement.\n\n"
        "Risks:\n"
        "Database size can change as files grow or database "
        "configuration changes.\n\n"
        "Uncertainty:\n"
        "This is a point-in-time result, not historical database "
        "size information."
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": APP_NAME,
        "demo_mode": DEMO_MODE,
    }


@app.get("/api/dashboard")
def dashboard():
    result = get_metrics()

    audit_event(
        "dashboard_view",
        "local-user",
        {"mode": result.get("mode")},
    )

    return result


@app.post("/api/chat")
def chat(body: ChatRequest):
    allowed, reason = check_chat_request(body.message)

    audit_event(
        "chat_request",
        body.actor,
        {
            "question": body.message[:500],
            "allowed": allowed,
        },
    )

    if not allowed:
        return {
            "blocked": True,
            "answer": reason,
            "sources": [],
            "live_metrics_included": False,
        }

    try:
        # Retrieve relevant internal knowledge.
        hits = retrieve(body.message)

        context_parts = [
            (
                f"[Source: {hit['source']} | "
                f"relevance: {hit.get('score', 0):.3f}]\n"
                f"{hit['text']}"
            )
            for hit in hits
        ]

        # Initialize these for every request.
        metrics_result = None
        live_metrics_included = False

        # Retrieve real diagnostic metrics only when relevant.
        if _needs_live_metrics(body.message):
            try:
                metrics_result = get_metrics()

                context_parts.append(
                    _format_live_metrics(metrics_result)
                )
                live_metrics_included = True

            except Exception:
                logger.exception(
                    "Could not retrieve live metrics for chat."
                )

                context_parts.append(
                    "LIVE METRICS UNAVAILABLE: The application's "
                    "diagnostic function failed during this request. "
                    "Do not guess or invent current metric values."
                )

        context = "\n\n".join(context_parts)

        # Use deterministic application logic for database-size
        # questions instead of asking the LLM to extract the number.
        answer = None

        if live_metrics_included and metrics_result is not None:
            answer = _answer_database_size(
                body.message,
                metrics_result,
            )

        # Other questions continue through the existing RAG + LLM flow.
        if answer is None:
            answer = generate_answer(
                body.message,
                context,
            )

        # Return only actual retrieved RAG documents as sources.
        sources = list({
            hit["source"]: {
                "source": hit["source"],
                "score": hit.get("score"),
            }
            for hit in hits
        }.values())

        audit_event(
            "chat_response",
            body.actor,
            {
                "source_count": len(sources),
                "live_metrics_included": live_metrics_included,
            },
        )

        return {
            "blocked": False,
            "answer": answer,
            "sources": sources,
            "live_metrics_included": live_metrics_included,
        }

    except Exception as exc:
        logger.exception(
            "Chat request failed (%s)",
            type(exc).__name__,
        )

        audit_event(
            "chat_failure",
            body.actor,
            {"error_type": type(exc).__name__},
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "The DBA Copilot could not complete this request. "
                "Check the server logs and try again."
            ),
        )


@app.post("/api/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...)):
    name = file.filename or "uploaded-document"

    suffix = (
        "." + name.rsplit(".", 1)[-1].lower()
        if "." in name
        else ""
    )

    if suffix not in {".pdf", ".txt", ".md"}:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, TXT, and MD files are supported.",
        )

    raw = await file.read()

    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_MB} MB limit.",
        )

    try:
        if suffix == ".pdf":
            content = "\n".join(
                page.extract_text() or ""
                for page in PdfReader(io.BytesIO(raw)).pages
            )
        else:
            content = raw.decode(
                "utf-8",
                errors="replace",
            )

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from document.",
        )

    result = ingest_document(name, content)

    audit_event(
        "knowledge_ingestion",
        "local-user",
        {
            "name": name,
            "result": result.get("ok"),
        },
    )

    if not result.get("ok"):
        raise HTTPException(
            status_code=503,
            detail=result.get("message", "Ingestion failed"),
        )

    return result
