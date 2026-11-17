import time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
SECRETS = "/home/hatch/workspace/asmr-service/secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
VID = "kt2b-rsw9SU"
OLD = "2026-11-16T12:30:00Z"
NEW = "2026-11-17T12:30:00Z"
LOG = "/home/hatch/workspace/asmr-service/logs/guard_publish.log"

def log(m):
    with open(LOG, "a") as f: f.write(f"{time.strftime('%H:%M:%S')} {m}\n")

def svc():
    creds = Credentials.from_authorized_user_file(f"{SECRETS}/token.json", SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(f"{SECRETS}/token.json", "w") as f: f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

log("MULAI menjaga publishAt -> besok")
for i in range(40):  # ±3,3 jam
    try:
        yt = svc()
        cur = yt.videos().list(part="status,snippet", id=VID).execute()["items"][0]
        pa = cur["status"].get("publishAt")
        if pa == NEW:
            log("DONE publishAt terkunci besok"); break
        if pa == OLD or pa is None:
            st, sn = cur["status"], cur["snippet"]
            yt.videos().update(part="status,snippet", body={"id": VID,
                "snippet": {"title": sn["title"], "description": sn["description"],
                            "tags": sn.get("tags", []), "categoryId": sn["categoryId"]},
                "status": {"privacyStatus": "private", "publishAt": NEW,
                           "embeddable": st.get("embeddable", True),
                           "license": st.get("license", "youtube"),
                           "publicStatsViewable": st.get("publicStatsViewable", True)}}).execute()
            log(f"re-apply publishAt (terbaca {pa})")
        else:
            log(f"STOP publishAt berubah ke nilai lain: {pa} (dibiarkan)"); break
    except Exception as e:
        log(f"error sementara: {e}")
    time.sleep(300)
else:
    log("TIMEOUT")
