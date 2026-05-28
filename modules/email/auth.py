import imaplib
import os
from dataclasses import dataclass

from config.settings import GMAIL_ENV_PATH, GMAIL_IMAP_HOST, GMAIL_IMAP_PORT


@dataclass
class EmailCredentials:
    address: str
    app_password: str


def _read_env_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values

    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_email_credentials() -> EmailCredentials:
    env_values = _read_env_file(GMAIL_ENV_PATH)
    address = env_values.get("EMAIL_ADDRESS", "").strip()
    app_password = env_values.get("EMAIL_APP_PASSWORD", "").strip()
    if not address or not app_password:
        raise ValueError("Email credentials are missing. Expected EMAIL_ADDRESS and EMAIL_APP_PASSWORD in config/email/.env.")
    return EmailCredentials(address=address, app_password=app_password)


def connect_imap() -> imaplib.IMAP4_SSL:
    credentials = load_email_credentials()
    client = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
    client.login(credentials.address, credentials.app_password)
    return client
