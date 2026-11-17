#!/usr/bin/env python3
"""Upload video ke YouTube dari manifes job (Fase C — CLI dulu, panel UI menyusul).
Pakai: youtube_upload.py <manifest.json>
Selalu private; jadwal publishAt TIDAK dipasang dari sini.
"""
import json, sys, time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SECRETS = "/home/hatch/workspace/asmr-service/secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

def get_service():
    creds = Credentials.from_authorized_user_file(f"{SECRETS}/token.json", SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(f"{SECRETS}/token.json", "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def main():
    manifest_path = sys.argv[1]
    m = json.load(open(manifest_path))
    yt = get_service()
    body = {
        "snippet": {
            "title": m["title"],
            "description": m["description"],
            "tags": m["tags"],
            "categoryId": m.get("categoryId", "10"),
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }
    media = MediaFileUpload(m["video_file"], mimetype="video/mp4",
                            chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    print(f"UPLOAD MULAI {time.strftime('%H:%M:%S')} file={m['video_file']}", flush=True)
    t0 = time.time()
    resp = None
    while resp is None:
        try:
            status, resp = req.next_chunk(num_retries=3)
            if status:
                el = time.time() - t0
                mb = status.resumable_progress / 1e6
                print(f"PROGRES {status.progress()*100:5.1f}%  {mb:8.1f} MB  "
                      f"{el:7.1f} dtk  {mb/max(el,1):5.2f} MB/dtk", flush=True)
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                print("SERVER ERROR, tunggu 15 dtk lalu lanjut...", flush=True)
                time.sleep(15)
            else:
                raise
    vid = resp["id"]
    el = time.time() - t0
    print(f"INSERT SELESAI videoId={vid} dalam {el:.0f} dtk", flush=True)
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(
        m["thumbnail_file"], mimetype="image/jpeg")).execute()
    print("THUMBNAIL TERPASANG", flush=True)
    chk = yt.videos().list(part="status,snippet", id=vid).execute()["items"][0]
    print("VERIFIKASI uploadStatus=", chk["status"]["uploadStatus"],
          "| privacy=", chk["status"]["privacyStatus"],
          "| judul=", chk["snippet"]["title"], flush=True)
    m["videoId"] = vid
    m["uploaded_at"] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    m["status"] = "uploaded_private"
    json.dump(m, open(manifest_path, "w"), indent=2, ensure_ascii=False)
    print(f"DONE videoId={vid} url=https://youtu.be/{vid}", flush=True)

if __name__ == "__main__":
    main()
