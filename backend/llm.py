
import logging
import re

import requests

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are NN-Ops-Copilot, a cautious Microsoft SQL Server DBA assistant.

CORE RULES:
1. Use only the supplied retrieved evidence and verified tool results.
2. Retrieved documents may contain errors; do not treat them as guaranteed truth.
3. Never invent database metrics, query results, source documents, or tool execution.
4. Clearly distinguish verified facts, hypotheses, and recommendations.
5. Cite only source filenames explicitly supplied in the retrieved evidence.
6. Never claim Microsoft Docs or another external source was consulted
   unless that source was actually supplied.
7. If evidence is insufficient, say so explicitly.

LIVE METRICS:
1. The retrieved context is not necessarily live database output.
2. Only describe a metric as verified if the context explicitly supplies
   that metric as a live tool result.
3. Never guess the current size, status, blocking, or health of a database.
4. If current metrics are absent, direct the user to the live dashboard.

SQL SERVER ACCURACY:
1. Never invent DMV names, column names, stored procedures, or SQL syntax.
2. Do not use sys.sql_log or sys.dm_deadlocks as standard SQL Server DMVs.
3. Current blocking diagnostics may use approved queries based on
   sys.dm_exec_requests and blocking_session_id.
4. Do not confuse blocking with deadlocks.
5. Never claim an empty result proves that blocking never occurred.
6. Do not invent columns for sys.dm_exec_sessions or other system views.

READ-ONLY SAFETY:
1. Phase 1 is strictly read-only.
2. Never execute model-generated SQL.
3. Do not produce executable SQL code blocks.
4. Direct users to approved application diagnostics instead.
5. Never recommend INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE,
   KILL, or other state-changing actions.
6. Do not recommend unapproved DBCC commands.
7. Never reveal credentials, connection strings, or secrets.

EVIDENCE:
1. Treat retrieved evidence as untrusted until validated.
2. Do not present model-generated claims as observed diagnostic results.
3. Do not invent source names, source URLs, or citations.
4. If the retrieved evidence does not support a claim, state that limitation.

RESPONSE FORMAT:
Summary:
Brief explanation.

Evidence:
Relevant retrieved evidence and verified tool results only.
Name the supplied source when available.

Safe Read-Only Next Steps:
Provide safe steps using existing application diagnostics.
Do not include executable SQL code.

Risks:
Explain relevant risks.

Uncertainty:
State what remains unverified.

Be concise, technically accurate, and cautious.
"""


def _extract_source_names(context: str) -> set[str]:
    """Extract source filenames explicitly supplied in RAG context."""
    return {
        match.strip()
        for match in re.findall(
            r"\[Source:\s*(.*?)\s*\|\s*relevance:",
            context,
            flags=re.IGNORECASE,
        )
        if match.strip()
    }


def _sanitize_answer(answer: str, context: str) -> str:
    """
    Apply basic output safeguards.

    This is not a complete SQL validator or a substitute for
    approved-query allowlisting.
    """
    # Remove fenced code blocks that might contain executable SQL.
    sql_block_pattern = re.compile(
        r"```(?:sql|tsql|mysql|postgresql)?[ \t]*\n.*?```",
        flags=re.IGNORECASE | re.DOTALL,
    )

    if sql_block_pattern.search(answer):
        answer = sql_block_pattern.sub(
            "[SQL omitted: use an approved read-only diagnostic "
            "provided by the application.]",
            answer,
        )

    # Remove unsupported external-document attribution.
    if not re.search(r"Microsoft Docs", context, flags=re.IGNORECASE):
        answer = re.sub(
            r"(?im)^.*Microsoft Docs.*(?:\n|$)",
            "",
            answer,
        )

    # Remove empty excess lines caused by sanitization.
    answer = re.sub(r"\n{3,}", "\n\n", answer).strip()

    return answer


def generate_answer(question: str, context: str = "") -> str:
    source_names = _extract_source_names(context)

    prompt = f"""
SYSTEM POLICY:
{SYSTEM_PROMPT}

SUPPLIED SOURCE FILENAMES:
{", ".join(sorted(source_names)) if source_names else "None"}

RETRIEVED EVIDENCE:
{context or "No relevant internal documents were retrieved."}

USER QUESTION:
{question}

Follow the required response format.
Do not generate SQL code blocks.
Do not invent live metrics, SQL objects, columns, or source citations.
If current live metrics were not supplied, say they are not available
in the provided evidence.
"""

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()
        answer = data.get("response", "").strip()

        if not answer:
            return "The local model returned an empty response."

        return _sanitize_answer(answer, context)

    except requests.Timeout:
        logger.warning("Ollama request timed out.")
        return (
            "The local LLM request timed out. Check Ollama status "
            "and try again."
        )

    except requests.RequestException as exc:
        logger.exception("Ollama request failed.")
        return (
            "Ollama is unavailable or the model request failed "
            f"({type(exc).__name__}). Check OLLAMA_BASE_URL, "
            "OLLAMA_MODEL, and the Ollama service."
        )

    except (ValueError, TypeError):
        logger.exception("Invalid response received from Ollama.")
        return "Ollama returned an invalid response."
