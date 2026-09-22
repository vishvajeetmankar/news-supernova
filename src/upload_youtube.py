"""
Uploads the rendered short to YouTube using the free YouTube Data API v3 quota
(10,000 units/day; one upload = ~1600 units, so ~6 uploads/day fit easily
within our 5/day plan).

Auth uses a refresh token generated ONCE via get_youtube_token.py, so the
GitHub Actions job never needs a browser login.
"""

import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)


def upload_short(video_path: str, title: str, description: str, tags=None):
    youtube = _get_service()

    body = {
        "snippet": {
            "title": title[:95] + " #shorts",   # YouTube title limit ~100 chars
            "description": description + "\n\n#shorts #news #trending",
            "tags": tags or ["news", "shorts", "trending", "hindi news"],
            "categoryId": "25",  # News & Politics
        },
        "status": {
            "privacyStatus": "public",   # change to "private" while testing if you prefer
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
    print("Uploaded! Video ID:", response.get("id"))
    return response.get("id")
