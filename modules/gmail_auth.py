"""Gmail credential loader. Reads base64 OAuth2 token JSON from env vars."""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import GMAIL_ACCOUNTS

SCOPES = ["https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/gmail.readonly"]


def credentials_from_b64(b64):
    if not b64:
        raise RuntimeError("missing OAuth2 token JSON")
    data = json.loads(base64.b64decode(b64).decode("utf-8"))
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    return creds


def gmail_service(b64_token):
    creds = credentials_from_b64(b64_token)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def all_services():
    out = []
    for acc in GMAIL_ACCOUNTS:
        if not acc["address"] or not acc["credentials_b64"]:
            continue
        out.append((acc["address"], gmail_service(acc["credentials_b64"])))
    return out
