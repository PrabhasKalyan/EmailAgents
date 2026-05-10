import os

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Per-account daily cap and global delay window
PER_ACCOUNT_DAILY_LIMIT = int(os.environ.get("PER_ACCOUNT_DAILY_LIMIT", "50"))
SEND_DELAY_MIN = int(os.environ.get("SEND_DELAY_MIN", "180"))
SEND_DELAY_MAX = int(os.environ.get("SEND_DELAY_MAX", "480"))
SEND_WINDOW_START_HOUR_EST = 9
SEND_WINDOW_END_HOUR_EST = 18

# 4 Gmail accounts. Each entry: address + base64 OAuth2 token JSON.
GMAIL_ACCOUNTS = [
    {
        "address": os.environ.get("GMAIL_A_ADDRESS", ""),
        "credentials_b64": os.environ.get("GMAIL_A_CREDENTIALS", ""),
    },
    {
        "address": os.environ.get("GMAIL_B_ADDRESS", ""),
        "credentials_b64": os.environ.get("GMAIL_B_CREDENTIALS", ""),
    },
    {
        "address": os.environ.get("GMAIL_C_ADDRESS", ""),
        "credentials_b64": os.environ.get("GMAIL_C_CREDENTIALS", ""),
    },
    {
        "address": os.environ.get("GMAIL_D_ADDRESS", ""),
        "credentials_b64": os.environ.get("GMAIL_D_CREDENTIALS", ""),
    },
]

GMAIL_ACCOUNTS = [a for a in GMAIL_ACCOUNTS if a["address"]]
