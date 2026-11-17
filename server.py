"""ASMR Tools v2 — FastAPI entry point."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from api.router import router

app = FastAPI(title="ASMR Tools", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/js-v2") or request.url.path.endswith(".css"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

# --- Login gate sederhana (HTTP Basic) ---
# Aktif hanya bila env ASMR_AUTH_USER dan ASMR_AUTH_PASS_SHA256 diisi
# (di VM: lewat EnvironmentFile systemd menunjuk file secrets di luar repo).
# Tanpa env itu, tool berjalan terbuka seperti biasa (mis. dev lokal).
import base64, hashlib, secrets as _secrets
_AUTH_USER = os.environ.get("ASMR_AUTH_USER", "")
_AUTH_PASS_SHA256 = os.environ.get("ASMR_AUTH_PASS_SHA256", "")

@app.middleware("http")
async def basic_auth_gate(request, call_next):
    if _AUTH_USER and _AUTH_PASS_SHA256:
        hdr = request.headers.get("authorization", "")
        ok = False
        if hdr.startswith("Basic "):
            try:
                raw = base64.b64decode(hdr[6:]).decode("utf-8")
                u, _, p = raw.partition(":")
                ok = (_secrets.compare_digest(u, _AUTH_USER)
                      and _secrets.compare_digest(
                          hashlib.sha256(p.encode()).hexdigest(),
                          _AUTH_PASS_SHA256))
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401, content="Login diperlukan.",
                            headers={"WWW-Authenticate": 'Basic realm="ASMR Tools"'})
    return await call_next(request)

app.include_router(router, prefix="/api")


@app.on_event("startup")
async def jobs_startup_sweep():
    """Jobs left running/queued when the previous process died are
    marked interrupted so they can be resumed from their checkpoints."""
    try:
        from core.jobs import sweep_interrupted
        marked = sweep_interrupted()
        if marked:
            print(f"[jobs] startup sweep: {len(marked)} job(s) marked interrupted: {marked}", flush=True)
    except Exception as e:
        print(f"[jobs] startup sweep failed: {e}", flush=True)

# Static assets
if os.path.isdir("frontend/js"):
    app.mount("/js-v2", StaticFiles(directory="frontend/js"), name="js")
if os.path.isdir("frontend/assets"):
    app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")
if os.path.isdir("media"):
    app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/style.css")
async def serve_css():
    return FileResponse("frontend/style.css", media_type="text/css")


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("frontend/index.html", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
