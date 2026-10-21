
import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

driver = os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
host = os.getenv("SQLSERVER_HOST", "localhost")
database = os.getenv("SQLSERVER_DATABASE", "NNOpsTest")
username = os.getenv("SQLSERVER_USERNAME", "nnops_diagnostic")
password = os.getenv("SQLSERVER_PASSWORD")

if not password or password == "YOUR_ACTUAL_PASSWORD":
    raise RuntimeError("Please set the real SQL Server password in .env.")

connection_string = (
    f"DRIVER={{{driver}}};"
    f"SERVER={host};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={{{password}}};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
    "Connection Timeout=5;"
)

with pyodbc.connect(connection_string) as connection:
    cursor = connection.cursor()
    cursor.execute("SELECT DB_NAME(), SUSER_SNAME()")
    row = cursor.fetchone()
    print("Connection successful!")
    print("Database:", row[0])
    print("Login:", row[1])
