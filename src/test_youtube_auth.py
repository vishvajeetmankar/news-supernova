# ============================================================
# FILE: src/test_youtube_auth.py
# ============================================================
"""
Run this locally to test YOUR YouTube credentials in isolation, without
generating a video or uploading anything. This tells you clearly whether the
problem is the credentials themselves, or something else (like GitHub Secrets
being copy-pasted with extra characters).

Usage (paste your values directly below and run):
    python src/test_youtube_auth.py
"""

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build

# ---- PASTE YOUR EXACT VALUES HERE (same as your GitHub Secrets) ----
CLIENT_ID = "PASTE_YOUTUBE_CLIENT_ID_HERE"
CLIENT_SECRET = "PASTE_YOUTUBE_CLIENT_SECRET_HERE"
REFRESH_TOKEN = "PASTE_YOUTUBE_REFRESH_TOKEN_HERE"
# ----------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

print("Testing YouTube OAuth credentials...")
print(f"  client_id starts with: {CLIENT_ID[:15]}...")
print(f"  client_secret starts with: {CLIENT_SECRET[:8]}...")
print(f"  refresh_token starts with: {REFRESH_TOKEN[:8]}... (length: {len(REFRESH_TOKEN)})")
print()

creds = Credentials(
    token=None,
    refresh_token=REFRESH_TOKEN.strip(),
    client_id=CLIENT_ID.strip(),
    client_secret=CLIENT_SECRET.strip(),
    token_uri="https://oauth2.googleapis.com/token",
    scopes=SCOPES,
)

try:
    creds.refresh(Request())
    print("✅ SUCCESS! Credentials are valid — token refreshed fine.")
    print("   -> The problem is in GitHub Secrets (copy-paste issue), not the credentials themselves.")
    print("   -> Carefully re-copy these EXACT working values into your GitHub repo secrets.")

    # bonus: confirm which channel this token controls
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="snippet", mine=True).execute()
    for item in resp.get("items", []):
        print(f"   -> This token controls channel: {item['snippet']['title']}")

except RefreshError as e:
    print("❌ FAILED. The credentials themselves are invalid.")
    print("   Error:", e)
    print()
    print("   -> This means: token expired/revoked, OR client_id/secret don't match")
    print("      the client that generated this refresh token.")
    print("   -> Fix: run src/get_youtube_token.py again to get a fresh refresh token,")
    print("      making sure you use the SAME client_id/client_secret as above.")
