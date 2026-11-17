import json, time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SECRETS = "/home/hatch/workspace/asmr-service/secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
VID = "kt2b-rsw9SU"
LOG = "/home/hatch/workspace/asmr-service/logs/playlist_finisher.log"
IDS = json.load(open("/home/hatch/workspace/asmr-service/work/series_playlists.json"))

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

def service():
    creds = Credentials.from_authorized_user_file(f"{SECRETS}/token.json", SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(f"{SECRETS}/token.json", "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def has(yt, pid):
    r = yt.playlistItems().list(part="snippet", playlistId=pid, maxResults=50).execute()
    return any(it["snippet"]["resourceId"]["videoId"] == VID for it in r.get("items", []))

log("MULAI menunggu proses video selesai")
for i in range(60):
    try:
        yt = service()
        it = yt.videos().list(part="processingDetails", id=VID).execute()["items"][0]
        if it.get("processingDetails", {}).get("processingStatus") == "succeeded":
            if not has(yt, IDS["rain"]):
                yt.playlistItems().insert(part="snippet", body={"snippet": {
                    "playlistId": IDS["rain"], "position": 0,
                    "resourceId": {"kind": "youtube#video", "videoId": VID}}}).execute()
                log("masuk Rain Sounds for Sleep (posisi atas)")
            if not has(yt, IDS["umbrella"]):
                yt.playlistItems().insert(part="snippet", body={"snippet": {
                    "playlistId": IDS["umbrella"],
                    "resourceId": {"kind": "youtube#video", "videoId": VID}}}).execute()
                log("masuk Nature Sounds for Sleep")
            log("DONE")
            break
    except Exception as e:
        log(f"error sementara: {e}")
    time.sleep(180)
else:
    log("TIMEOUT")
