import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SECRETS = "/home/hatch/workspace/asmr-service/secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
VID = "kt2b-rsw9SU"
IDS = json.load(open("/home/hatch/workspace/asmr-service/work/series_playlists.json"))

creds = Credentials.from_authorized_user_file(f"{SECRETS}/token.json", SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(f"{SECRETS}/token.json", "w") as f:
        f.write(creds.to_json())
yt = build("youtube", "v3", credentials=creds)
v = yt.videos().list(part="processingDetails,status,snippet", id=VID).execute()["items"][0]
print("processingStatus:", v.get("processingDetails", {}).get("processingStatus"))
print("privacyStatus:", v.get("status", {}).get("privacyStatus"))
print("publishAt:", v.get("status", {}).get("publishAt"))
print("title:", v.get("snippet", {}).get("title"))
for name, pid in IDS.items():
    r = yt.playlistItems().list(part="snippet", playlistId=pid, maxResults=50).execute()
    ids = [it["snippet"]["resourceId"]["videoId"] for it in r.get("items", [])]
    print(f"playlist {name} ({pid}): {len(ids)} items, video present: {VID in ids}")
