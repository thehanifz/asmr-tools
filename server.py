"""ASMR Tools v2 — FastAPI entry point."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from api.router import router

app = FastAPI(title="ASMR Tools", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Static assets
if os.path.isdir("frontend/js"):
    app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
if os.path.isdir("frontend/assets"):
    app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")


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
