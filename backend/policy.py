import re

BLOCKED_INTENT = re.compile(
    r"\b(drop|delete|truncate|insert|update|merge|alter|grant|revoke|shutdown|"
    r"create\s+(database|login|user|table|index)|xp_cmdshell)\b", re.I
)
BLOCKED_SQL = re.compile(
    r"\b(drop|delete|truncate|insert|update|merge|alter|create|grant|revoke|exec|backup|restore|dbcc|shutdown)\b", re.I
)

def check_chat_request(message: str) -> tuple[bool, str]:
    if BLOCKED_INTENT.search(message or ""):
        return False, "This request appears to involve a write, destructive, or privileged operation. Phase 1 is read-only, so I cannot execute it. I can provide safe explanatory guidance instead."
    return True, "Allowed for read-only assistance."



def validate_fixed_query(
    query: str,
    approved_queries=None,
) -> bool:
    """Validate a query, optionally requiring an exact approved-query match."""
    if not isinstance(query, str) or not query.strip():
        return False

    normalized = " ".join(query.split()).casefold()

    # Production collector calls must supply the approved query list.
    if approved_queries is not None:
        approved = {
            " ".join(item.split()).casefold()
            for item in approved_queries
            if isinstance(item, str) and item.strip()
        }
        return normalized in approved

    # Backward-compatible checks for existing unit tests.
    if not normalized.startswith("select"):
        return False

    if BLOCKED_SQL.search(normalized):
        return False

    if ";" in normalized:
        return False

    return True

