"""Settings: from .env on a laptop, from AWS Secrets Manager in the cloud.

Every module that reads a setting imports this first, so secrets are loaded once,
before anything uses them. Locally nothing changes: .env is read as before and
the app uses SQLite.

In the cloud the server or Lambda function only gets the NAMES of its secrets as
environment variables, never the values (Week 6: secrets management):
  APP_SECRET_ID  JSON secret with JWT_SECRET, TURN_SECRET, ARKESEL_API_KEY, ARKESEL_SENDER, FRONTEND_ORIGINS
  DB_SECRET_ID   the RDS-managed secret (username + password, rotated by AWS)
  DB_HOST, DB_NAME, DB_PORT   where the database is
  DB_SSLROOTCERT  path to the RDS certificate bundle; when set, the server's certificate is verified
"""
import json
import os
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()


def read_secret(secret_id):
    import boto3  # only needed in the cloud

    client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION"))
    return json.loads(client.get_secret_value(SecretId=secret_id)["SecretString"])


def load_app_secret():
    # Values already set in the environment win, so a developer can override one locally
    for key, value in read_secret(os.environ["APP_SECRET_ID"]).items():
        if value and not os.getenv(key):
            os.environ[key] = str(value)


def load_database_url():
    """Build DATABASE_URL from the RDS-managed secret. Called again if the password was rotated."""
    creds = read_secret(os.environ["DB_SECRET_ID"])
    # TLS always; with the RDS certificate bundle we also check we're talking to the real database
    root_cert = os.getenv("DB_SSLROOTCERT")
    tls = f"sslmode=verify-full&sslrootcert={quote(root_cert)}" if root_cert else "sslmode=require"
    os.environ["DATABASE_URL"] = (
        f"postgresql://{quote(creds['username'], safe='')}:{quote(creds['password'], safe='')}"
        f"@{os.environ['DB_HOST']}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'healthconnect')}?{tls}"
    )


if os.getenv("APP_SECRET_ID"):
    load_app_secret()
if os.getenv("DB_SECRET_ID") and not os.getenv("DATABASE_URL"):
    load_database_url()
