#!/usr/bin/env python3
"""Pasang publishAt pada video dari manifes job. Pakai: set_publish.py <manifest> <ISO8601-UTC>"""
import json, sys, time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SECRETS = "/home/hatch/workspace/asmr-service/secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]
m = json.load(open(sys.argv[1]))
vid, when = m.get("videoId"), sys.argv[2]
if not vid:
    print("BELUM ADA videoId"); sys.exit(1)
creds = Credentials.from_authorized_user_file(f"{SECRETS}/token.json", SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(f"{SECRETS}/token.json", "w") as f:
        f.write(creds.to_json())
yt = build("youtube", "v3", credentials=creds)
yt.videos().update(part="status", body={
    "id": vid,
    "status": {"privacyStatus": "private", "publishAt": when,
               "selfDeclaredMadeForKids": False, "embeddable": True},
}).execute()
chk = yt.videos().list(part="status", id=vid).execute()["items"][0]["status"]
print("PUBLISHAT TERPASANG:", chk.get("publishAt"), "| privacy:", chk["privacyStatus"])
m["publishAt"] = when
json.dump(m, open(sys.argv[1], "w"), indent=2, ensure_ascii=False)
print("MANIFES DIPERBARUI")
