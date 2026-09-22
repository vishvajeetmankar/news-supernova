"""
RUN THIS ONLY ONCE, ON YOUR OWN COMPUTER (not in GitHub Actions).
It opens a browser, asks you to log into the Google account that owns your
"News Supernova" YouTube channel, and prints a REFRESH TOKEN.

Save that refresh token as the GitHub secret: YOUTUBE_REFRESH_TOKEN
After this, the automation never needs a browser again.

Setup before running:
  1. Go to https://console.cloud.google.com/  -> create a project
  2. Enable "YouTube Data API v3"
  3. Create OAuth Client ID -> Application type: Desktop app
  4. Copy Client ID & Client Secret into a local .env (or paste below)
  5. pip install google-auth-oauthlib
  6. python src/get_youtube_token.py
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CLIENT_CONFIG = {
    "installed": {
        "client_id": os.environ.get("YOUTUBE_CLIENT_ID", "PASTE_CLIENT_ID_HERE"),
        "client_secret": os.environ.get("YOUTUBE_CLIENT_SECRET", "PASTE_CLIENT_SECRET_HERE"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
    creds = flow.run_local_server(port=0)
    print("\n\n===== SAVE THIS AS GitHub SECRET: YOUTUBE_REFRESH_TOKEN =====")
    print(creds.refresh_token)
    print("===============================================================")
