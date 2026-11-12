"""
FastAPI Backend for the Steirische Harmonika (Normalnoten + Rosenzopf Griffschrift) Pipeline.

Endpoints:
  - GET  /api/health           : System, GPU & FFmpeg readiness check
  - POST /api/transcribe       : Ingests media, creates asynchronous pipeline job, and returns job status.
  - GET  /api/jobs/{job_id}    : Returns detailed stage progress, logs, and results.
  - GET  /api/jobs/{job_id}/stream : Real-time Server-Sent Events (SSE) progress stream.
  - GET  /files/outputs/{path} : Serves generated PDFs, SVG/PNG sheet music pages, and WAV files.
"""

import asyncio
import hashlib
import json
from pathlib import Path
import threading
import time
import torch
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .jobs import JobManager, run_pipeline_job
from .media_ingest import get_ffmpeg_executable

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT_DIR / "outputs"
JOBS_DIR = OUTPUTS_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

job_manager = JobManager(JOBS_DIR)

app = FastAPI(
    title="Steirische Harmonika – Normalnoten & Griffschrift Werkbank API",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict:
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    ffmpeg_ok = False
    try:
        get_ffmpeg_executable()
        ffmpeg_ok = True
    except Exception:
        ffmpeg_ok = False

    return {
        "status": "ok",
        "gpu": gpu_name,
        "cuda_available": torch.cuda.is_available(),
        "ffmpeg_available": ffmpeg_ok,
        "reference_tuning": "G-C-F-B (4-reihig, System Max Rosenzopf)",
    }


@app.post("/api/transcribe")
async def transcribe_uploaded_media(
    file: UploadFile = File(...),
    title: str = Form(""),
    wait: bool = Query(False),
) -> dict:
    """
    Ingests an uploaded Audio or Video file, creates an asynchronous job tracking
    all 8 pipeline stages in real-time, and starts processing in the background.
    If wait=True, blocks until completion and returns the final result.
    """
    filename = file.filename or "upload.mp4"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Hochgeladene Datei ist leer.")

    content_hash = hashlib.sha256(content).hexdigest()[:12]
    job_dir = JOBS_DIR / content_hash
    job_dir.mkdir(parents=True, exist_ok=True)

    raw_upload_path = job_dir / f"source{Path(filename).suffix.lower()}"
    raw_upload_path.write_bytes(content)

    job, is_new = job_manager.get_or_create_job(content_hash, filename, title)

    # If the job failed previously or is new, start a fresh worker
    if is_new or job.status == "failed":
        if job.status == "failed":
            job, _ = job_manager.get_or_create_job(
                content_hash, filename, title, force_new=True
            )
        worker = threading.Thread(
            target=run_pipeline_job,
            args=(job, raw_upload_path, filename, title, OUTPUTS_DIR),
            daemon=True,
        )
        worker.start()

    if wait:
        while job.status in ("queued", "running"):
            await asyncio.sleep(0.3)
        if job.status == "failed":
            raise HTTPException(
                status_code=422, detail=job.error or "Verarbeitungsfehler aufgetreten."
            )
        return job.result or job.to_dict()

    return job.to_dict()


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    """
    Returns the real-time status of a transcription job, including all 8 stages,
    durations, active stage description, and telemetry logs.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_status(job_id: str):
    """
    Server-Sent Events (SSE) streaming endpoint pushing real-time progress updates,
    stage changes, and log messages directly to the client.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")

    async def event_generator():
        last_str = None
        # Send initial snapshot immediately
        snapshot = job.to_dict()
        last_str = json.dumps(snapshot)
        yield f"data: {last_str}\n\n"

        if job.status in ("completed", "failed"):
            return

        while True:
            await asyncio.sleep(0.35)
            current_job = job_manager.get_job(job_id)
            if not current_job:
                break
            payload = current_job.to_dict()
            cur_str = json.dumps(payload)
            if cur_str != last_str:
                yield f"data: {cur_str}\n\n"
                last_str = cur_str
            if current_job.status in ("completed", "failed"):
                # Send final state
                yield f"data: {cur_str}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/files/outputs/{file_path:path}")
def serve_output_file(file_path: str, download: bool = False):
    target = (OUTPUTS_DIR / file_path).resolve()
    if not str(target).startswith(str(OUTPUTS_DIR.resolve())) or not target.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.")
    media_type = "application/pdf" if target.suffix.lower() == ".pdf" else None
    headers = {}
    if target.suffix.lower() == ".pdf":
        disp = "attachment" if download else "inline"
        headers["Content-Disposition"] = f'{disp}; filename="{target.name}"'
    return FileResponse(str(target), media_type=media_type, headers=headers)


WEB_DIST_DIR = ROOT_DIR / "web" / "dist"

@app.get("/favicon.ico", include_in_schema=False)
def get_favicon_ico():
    target = WEB_DIST_DIR / "favicon.ico"
    if target.exists():
        return FileResponse(str(target), media_type="image/x-icon")
    alt = ROOT_DIR / "web" / "public" / "favicon.ico"
    if alt.exists():
        return FileResponse(str(alt), media_type="image/x-icon")
    raise HTTPException(status_code=404)

if WEB_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST_DIR), html=True), name="web_ui")
