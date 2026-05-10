"""
One-time helper to generate the base64 token JSON for one Gmail account.

Usage:
  1. In Google Cloud Console create an OAuth client (Desktop app), download
     the client_secret_*.json file.
  2. Run:
        python scripts/gmail_oauth_setup.py path/to/client_secret.json
  3. A browser window opens — sign in with the Gmail account you want to use.
  4. The script prints a base64 string. Set it as GMAIL_A_CREDENTIALS (or B/C/D)
     and the email as GMAIL_A_ADDRESS.

Repeat once per Gmail account.
"""
import base64
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/gmail.readonly"]


def main(client_secret_path):
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(port=0)
    payload = json.loads(creds.to_json())
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    print("\n=== GMAIL_x_CREDENTIALS (set as env var) ===")
    print(encoded)
    print("=== end ===\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: gmail_oauth_setup.py path/to/client_secret.json")
        sys.exit(1)
    main(sys.argv[1])
