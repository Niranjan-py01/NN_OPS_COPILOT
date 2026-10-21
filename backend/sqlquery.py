"""Read-only SQL Server diagnostics for NN-Ops-Copilot Phase 1."""

from .config import DEMO_MODE, SQLSERVER_CONNECTION_STRING
from .policy import validate_fixed_query


DEMO_METRICS = {
    "blocking_sessions": {
        "value": 1,
        "status": "warning",
        "description": "Sample only: one blocking chain; not live data.",
    },
    "long_running_queries": {
        "value": 2,
        "status": "warning",
        "description": "Sample only: two queries exceed 60 seconds; not live data.",
    },
    "top_cpu_queries": {
        "value": 3,
        "status": "info",
        "description": "Sample high-CPU query records; not live data.",
    },
    "tempdb_usage_pct": {
        "value": 42.5,
        "status": "healthy",
        "description": "Illustrative tempdb usage only; not live data.",
    },
    "database_count": {
        "value": 5,
        "status": "healthy",
        "description": "Sample database inventory; not live data.",
    },
    "backup_status": {
        "value": "Review required",
        "status": "warning",
        "description": "Validate successful backups and restore tests separately.",
    },
}


# Fixed diagnostic SELECT queries only. Never accept SQL text from the UI or an LLM.
QUERIES = {
    "database_sizes": """
    SELECT
        DB_NAME() AS database_name,
        CAST(
            SUM(size) * 8.0 / 1024
            AS DECIMAL(18, 2)
        ) AS size_mb
    FROM sys.database_files
    """,
    "active_requests": """
        SELECT TOP (20)
            r.session_id,
            s.login_name,
            s.host_name,
            DB_NAME(r.database_id) AS database_name,
            r.status,
            r.command,
            r.total_elapsed_time,
            r.cpu_time,
            r.logical_reads,
            r.wait_type,
            r.blocking_session_id
        FROM sys.dm_exec_requests AS r
        INNER JOIN sys.dm_exec_sessions AS s
            ON r.session_id = s.session_id
        WHERE r.session_id <> @@SPID
          AND s.is_user_process = 1
        ORDER BY r.total_elapsed_time DESC
    """,
    
    "blocking_sessions": """
        SELECT TOP (100)
            r.session_id AS blocked_session_id,
            r.blocking_session_id,
            r.wait_type,
            r.wait_time AS wait_time_ms,
            r.wait_resource,
            r.status AS request_status,
            DB_NAME(r.database_id) AS database_name,
            blocked.login_name AS blocked_login_name,
            blocker.login_name AS blocking_login_name,
            blocker.host_name AS blocking_host_name
        FROM sys.dm_exec_requests AS r
        INNER JOIN sys.dm_exec_sessions AS blocked
            ON r.session_id = blocked.session_id
        LEFT JOIN sys.dm_exec_sessions AS blocker
            ON r.blocking_session_id = blocker.session_id
        WHERE r.blocking_session_id > 0
          AND blocked.is_user_process = 1
        ORDER BY r.wait_time DESC
    """,

}


def get_metrics() -> dict:
    """Return demo metrics or run the fixed read-only diagnostic queries."""
    if DEMO_MODE:
        return {"mode": "demo", "metrics": DEMO_METRICS}

    if not SQLSERVER_CONNECTION_STRING:
        return {
            "mode": "error",
            "metrics": {},
            "message": (
                "SQL Server connection is not configured. "
                "Check SQLSERVER_* settings in the .env file."
            ),
        }

    try:
        import pyodbc

        output = {}

        with pyodbc.connect(
            SQLSERVER_CONNECTION_STRING,
            timeout=5,
            autocommit=True,
        ) as connection:
            cursor = connection.cursor()

            for name, query in QUERIES.items():
                if not validate_fixed_query(query, approved_queries=list(QUERIES.values())):
                    raise RuntimeError(
                        f"Fixed collector query failed policy validation: {name}"
                    )

                cursor.execute(query)

                # A SELECT query should return column metadata.
                if cursor.description is None:
                    raise RuntimeError(
                        f"Diagnostic query returned no result metadata: {name}"
                    )

                columns = [column[0] for column in cursor.description]
                rows = [
                    dict(zip(columns, row))
                    for row in cursor.fetchmany(100)
                ]

                output[name] = {
                    "rows": rows,
                    "count": len(rows),
                }

        return {"mode": "live", "metrics": output}

    except Exception as exc:
        # Do not expose raw ODBC errors or connection details to the API client.
        return {
            "mode": "error",
            "metrics": {},
            "message": (
                f"SQL Server collector failed ({exc.__class__.__name__}). "
                "Check server logs, query-policy validation, and SQL permissions."
            ),
        }

