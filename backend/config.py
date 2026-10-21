
import os
from dotenv import load_dotenv

# Load environment variables from the project's .env file
load_dotenv()

# --------------------------------------------------
# Application settings
# --------------------------------------------------
APP_NAME = os.getenv("APP_NAME", "NN-Ops-Copilot")
APP_ENV = os.getenv("APP_ENV", "development")

DEMO_MODE = os.getenv("DEMO_MODE", "true").strip().lower() == "true"

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

# --------------------------------------------------
# Ollama settings
# --------------------------------------------------
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://127.0.0.1:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

OLLAMA_EMBED_MODEL = os.getenv(
    "OLLAMA_EMBED_MODEL",
    "nomic-embed-text",
)

# --------------------------------------------------
# Qdrant settings
# --------------------------------------------------
QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://127.0.0.1:6333",
).rstrip("/")

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None

QDRANT_COLLECTION = os.getenv(
    "QDRANT_COLLECTION",
    "nn_ops_knowledge",
)

# --------------------------------------------------
# PostgreSQL settings
# --------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# --------------------------------------------------
# SQL Server settings
# --------------------------------------------------
SQLSERVER_HOST = os.getenv("SQLSERVER_HOST", "localhost")
SQLSERVER_DATABASE = os.getenv(
    "SQLSERVER_DATABASE",
    "NNOpsTest",
)
SQLSERVER_USERNAME = os.getenv("SQLSERVER_USERNAME", "")
SQLSERVER_PASSWORD = os.getenv("SQLSERVER_PASSWORD", "")

SQLSERVER_DRIVER = os.getenv(
    "SQLSERVER_DRIVER",
    "ODBC Driver 18 for SQL Server",
)

SQLSERVER_ENCRYPT = os.getenv("SQLSERVER_ENCRYPT", "yes")
SQLSERVER_TRUST_SERVER_CERTIFICATE = os.getenv(
    "SQLSERVER_TRUST_SERVER_CERTIFICATE",
    "yes",
)

# Use a complete connection string if one is explicitly configured.
SQLSERVER_CONNECTION_STRING = os.getenv(
    "SQLSERVER_CONNECTION_STRING",
    "",
).strip()

# Otherwise, build it from the individual .env settings.
if not SQLSERVER_CONNECTION_STRING and SQLSERVER_USERNAME and SQLSERVER_PASSWORD:
    SQLSERVER_CONNECTION_STRING = (
        f"DRIVER={{{SQLSERVER_DRIVER}}};"
        f"SERVER={SQLSERVER_HOST};"
        f"DATABASE={SQLSERVER_DATABASE};"
        f"UID={SQLSERVER_USERNAME};"
        f"PWD={{{SQLSERVER_PASSWORD}}};"
        f"Encrypt={SQLSERVER_ENCRYPT};"
        f"TrustServerCertificate={SQLSERVER_TRUST_SERVER_CERTIFICATE};"
    )

# --------------------------------------------------
# File upload settings
# --------------------------------------------------
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))
