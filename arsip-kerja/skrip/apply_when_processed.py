import json, time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SECRETS = "/home/hatch/workspace/asmr-service/secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
VID = "kt2b-rsw9SU"
WHEN = "2026-11-16T12:30:00Z"
MANIFEST = "/home/hatch/workspace/asmr-service/jobs/rain-garden-1hour.json"
LOG = "/home/hatch/workspace/asmr-service/logs/schedule_rain_garden.log"

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

log("MULAI menunggu proses selesai")
for i in range(60):  # maks ~3 jam
    try:
        yt = service()
        it = yt.videos().list(part="status,processingDetails,contentDetails", id=VID).execute()["items"][0]
        ps = it.get("processingDetails", {}).get("processingStatus")
        if ps == "succeeded":
            yt.videos().update(part="status", body={"id": VID, "status": {
                "privacyStatus": "private", "publishAt": WHEN,
                "selfDeclaredMadeForKids": False, "embeddable": True}}).execute()
            chk = yt.videos().list(part="status,contentDetails", id=VID).execute()["items"][0]
            pa = chk["status"].get("publishAt")
            log(f"SELESAI publishAt={pa} durasi={chk['contentDetails'].get('duration')}")
            if pa:
                m = json.load(open(MANIFEST))
                m["publishAt"] = WHEN
                m["status"] = "scheduled"
                json.dump(m, open(MANIFEST, "w"), indent=2, ensure_ascii=False)
                log("MANIFES: scheduled")
            break
        if ps in ("failed", "terminated"):
            log(f"PROSES GAGAL: {ps}")
            break
    except Exception as e:
        log(f"error sementara: {e}")
    time.sleep(180)
else:
    log("TIMEOUT 3 jam")
