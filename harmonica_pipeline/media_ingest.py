"""
Video & Audio Ingestion Module (FFmpeg Video-to-Audio Conversion & Frame Extraction).

Converts uploaded video files (.mp4, .mov, .webm, .mkv, .avi, .m4v) or audio files
(.wav, .mp3, .m4a, .ogg, .flac, .aac) into normalized 22.05 kHz 16-bit Mono WAV
for the Harmonika AI transcription pipeline, and extracts a preview frame for videos.
"""

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
import librosa

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".3gp"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".opus"}


@dataclass(frozen=True)
class IngestedMedia:
    job_id: str
    original_filename: str
    media_kind: str           # "VIDEO" or "AUDIO"
    conversion_step: str      # e.g. "MP4 Video -> 22.05 kHz Mono WAV (FFmpeg)"
    wav_path: Path
    duration_s: float
    preview_frame_path: Path | None


def get_ffmpeg_executable() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg executable not found in PATH.")
    return exe


def ingest_media_file(
    uploaded_path: Path,
    original_filename: str,
    job_dir: Path,
) -> IngestedMedia:
    """
    Takes an uploaded video or audio file, hashes its content, converts video/audio
    to a standardized 22.05 kHz Mono WAV via FFmpeg, and extracts a thumbnail frame
    if the input is a video container.
    """
    job_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(original_filename).suffix.lower()
    is_video = ext in VIDEO_EXTENSIONS
    ffmpeg_exe = get_ffmpeg_executable()

    wav_out = job_dir / "extracted_audio.wav"
    cmd_audio = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(uploaded_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "22050",
        "-sample_fmt",
        "s16",
        str(wav_out),
    ]
    proc = subprocess.run(cmd_audio, capture_output=True, text=True)
    if proc.returncode != 0 or not wav_out.exists():
        raise RuntimeError(
            f"FFmpeg audio extraction failed for {original_filename}: {proc.stderr[-400:]}"
        )

    duration_s = float(librosa.get_duration(path=str(wav_out)))

    preview_frame: Path | None = None
    if is_video:
        frame_out = job_dir / "video_frame.jpg"
        seek_t = min(2.0, max(0.0, duration_s * 0.15))
        cmd_frame = [
            ffmpeg_exe,
            "-y",
            "-ss",
            f"{seek_t:.2f}",
            "-i",
            str(uploaded_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(frame_out),
        ]
        subprocess.run(cmd_frame, capture_output=True, text=True)
        if frame_out.exists() and frame_out.stat().st_size > 0:
            preview_frame = frame_out

    file_hash = hashlib.sha256(uploaded_path.read_bytes()).hexdigest()[:12]
    media_kind = "VIDEO" if is_video else "AUDIO"
    ext_label = ext.upper().lstrip(".") or "MEDIA"
    conversion_step = (
        f"{ext_label}-Video → 22.05 kHz Mono WAV (FFmpeg)"
        if is_video
        else f"{ext_label}-Audio → 22.05 kHz Mono WAV (FFmpeg)"
    )

    return IngestedMedia(
        job_id=file_hash,
        original_filename=original_filename,
        media_kind=media_kind,
        conversion_step=conversion_step,
        wav_path=wav_out,
        duration_s=round(duration_s, 2),
        preview_frame_path=preview_frame,
    )
