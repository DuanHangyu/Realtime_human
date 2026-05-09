"""
FastAPI training server for digital human character generation.
Start with: python server.py
Open: http://localhost:8000
"""

import asyncio
import json
import os
import re
import shutil
import sys
import uuid
import threading
import time
from pathlib import Path
from typing import Optional

import cv2

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    StreamingResponse,
    JSONResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Ensure the project root directory is on sys.path so imports like
# `from talkingface...` and `from model...` resolve correctly.
_SERVER_DIR = Path(__file__).resolve().parent          # living_human/training_server/
_LIVING_DIR = _SERVER_DIR.parent                       # living_human/
_PROJECT_DIR = _LIVING_DIR.parent                      # dhy_human/
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from pipeline import TrainingPipeline, TOTAL_STEPS, STEP_NAMES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB

_FRONTEND_CHARS_DIR = _LIVING_DIR / "react-frontend" / "public" / "characters"

# ---------------------------------------------------------------------------
# In-memory task store
# ---------------------------------------------------------------------------

class TaskInfo:
    """Holds state for a single training task."""

    def __init__(self, task_id: str, name: str, video_path: str, output_dir: str):
        self.task_id = task_id
        self.name = name
        self.video_path = video_path
        self.output_dir = output_dir
        self.status: str = "pending"  # pending | running | completed | failed
        self.error: Optional[str] = None
        self.current_step: int = 0
        self.step_percent: int = 0
        self.step_message: str = ""
        self.step_history: list[dict] = []
        self.created_at: float = time.time()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status,
            "error": self.error,
            "current_step": self.current_step,
            "step_percent": self.step_percent,
            "step_message": self.step_message,
            "total_steps": TOTAL_STEPS,
            "step_history": list(self.step_history),
            "created_at": self.created_at,
        }


_tasks: dict[str, TaskInfo] = {}
_tasks_lock = threading.Lock()

# Directory for uploaded videos and output data
_BASE_DIR = _LIVING_DIR / "video_data"

# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------

_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$')

def _validate_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="角色名称不能为空")
    if not _SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="角色名称包含非法字符，仅允许中文、字母、数字、下划线、连字符")
    return name

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="数字人角色训练系统")

# Allow cross-origin requests from the frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (index.html)
_static_dir = _SERVER_DIR / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = _static_dir / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.post("/api/train")
async def start_training(
    video: UploadFile = File(...),
    name: str = Form(...),
):
    """Upload a video and start a training task."""
    name = _validate_name(name)

    if not video.filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="仅支持 .mp4 视频文件")

    task_id = uuid.uuid4().hex[:12]
    task_dir = _BASE_DIR / name
    task_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded video in chunks with size limit and content validation
    video_path = task_dir / "input.mp4"
    total = 0
    header_checked = False
    with open(video_path, "wb") as f:
        while True:
            chunk = await video.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_SIZE:
                video_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="文件大小超过限制 (500MB)")
            if not header_checked and len(chunk) >= 12:
                # MP4 files have 'ftyp' at bytes 4-7
                if chunk[4:8] != b"ftyp":
                    video_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=400, detail="文件内容不是有效的 MP4 视频")
                header_checked = True
            f.write(chunk)

    task = TaskInfo(
        task_id=task_id,
        name=name,
        video_path=str(video_path),
        output_dir=str(task_dir),
    )
    with _tasks_lock:
        _tasks[task_id] = task

    # Start training in background thread
    thread = threading.Thread(target=_run_training, args=(task,), daemon=True)
    thread.start()

    return {"task_id": task_id, "name": name}


@app.get("/api/tasks")
async def list_tasks():
    """List all training tasks."""
    with _tasks_lock:
        return [t.to_dict() for t in _tasks.values()]


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a single task's details."""
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@app.get("/api/tasks/{task_id}/progress")
async def task_progress(task_id: str):
    """SSE endpoint for real-time progress updates."""
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_stream():
        last_history_len = 0
        while True:
            with _tasks_lock:
                t = _tasks.get(task_id)
                if t is None:
                    break
                data = t.to_dict()

            new_history = data["step_history"][last_history_len:]
            for entry in new_history:
                yield f"event: step\ndata: {_json(entry)}\n\n"
            last_history_len = len(data["step_history"])

            yield f"event: progress\ndata: {_json(data)}\n\n"

            if data["status"] in ("completed", "failed"):
                break

            await asyncio.sleep(0.5)

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/download/{task_id}")
async def download_result(task_id: str):
    """Download the generated assets/data file."""
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    data_file = Path(task.output_dir) / "assets" / "data"
    if not data_file.exists():
        raise HTTPException(status_code=404, detail="输出文件不存在")

    return FileResponse(
        path=str(data_file),
        filename=f"{task.name}_data",
        media_type="application/gzip",
    )


# ---------------------------------------------------------------------------
# Deploy helpers
# ---------------------------------------------------------------------------

def _generate_preview(video_path: Path, output_path: Path) -> None:
    """Extract the first frame from a video, resize to 128x128, save as JPEG."""
    cap = cv2.VideoCapture(str(video_path))
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("无法从视频中提取帧")
    frame = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(output_path), frame)


def _update_characters_index(char_id: str, name: str, preview_rel: str) -> None:
    """Update characters/index.json — add or replace entry for *char_id*.

    Uses atomic write (write to temp file, then rename).
    """
    index_path = _FRONTEND_CHARS_DIR / "index.json"
    if index_path.exists():
        entries: list[dict] = json.loads(
            index_path.read_text(encoding="utf-8")
        )
    else:
        entries = []

    new_entry = {"id": char_id, "name": name, "preview": preview_rel}
    replaced = False
    for i, entry in enumerate(entries):
        if entry.get("id") == char_id:
            entries[i] = new_entry
            replaced = True
            break
    if not replaced:
        entries.append(new_entry)

    tmp_path = index_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(index_path)


@app.post("/api/deploy/{task_id}")
async def deploy_task(task_id: str):
    """Deploy a completed training result to the frontend characters directory."""
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    src_dir = Path(task.output_dir) / "assets"
    video_src = src_dir / "01.mp4"
    data_src = src_dir / "data"

    if not video_src.exists():
        raise HTTPException(status_code=404, detail="视频文件 01.mp4 不存在")
    if not data_src.exists():
        raise HTTPException(status_code=404, detail="数据文件 data 不存在")

    char_id = task.name
    dest_dir = _FRONTEND_CHARS_DIR / char_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(str(video_src), str(dest_dir / "01.mp4"))
    shutil.copy2(str(data_src), str(dest_dir / "data"))

    preview_path = dest_dir / "preview.jpg"
    _generate_preview(video_src, preview_path)

    _update_characters_index(
        char_id=char_id,
        name=task.name,
        preview_rel=f"characters/{char_id}/preview.jpg",
    )

    return {"detail": f"角色 '{task.name}' 已部署到前端"}


@app.get("/api/characters")
async def list_characters():
    """List all deployed characters."""
    index_path = _FRONTEND_CHARS_DIR / "index.json"
    if not index_path.exists():
        return []
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    return entries


@app.delete("/api/characters/{char_id}")
async def delete_character(char_id: str):
    """Delete a deployed character from the frontend."""
    if char_id == "default":
        raise HTTPException(status_code=400, detail="不能删除默认角色")

    char_dir = _FRONTEND_CHARS_DIR / char_id
    if not char_dir.exists():
        raise HTTPException(status_code=404, detail="角色不存在")

    # Remove character directory
    shutil.rmtree(char_dir, ignore_errors=True)

    # Remove from index.json
    index_path = _FRONTEND_CHARS_DIR / "index.json"
    if index_path.exists():
        entries: list[dict] = json.loads(
            index_path.read_text(encoding="utf-8")
        )
        entries = [e for e in entries if e.get("id") != char_id]
        tmp_path = index_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(index_path)

    return {"detail": f"角色 '{char_id}' 已删除"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its files."""
    with _tasks_lock:
        task = _tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task.status == "running":
            raise HTTPException(status_code=400, detail="正在训练中，无法删除")
        # Remove from dict while holding lock to prevent races
        _tasks.pop(task_id, None)

    output_dir = Path(task.output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)

    return {"detail": "已删除"}


# ---------------------------------------------------------------------------
# Background training runner
# ---------------------------------------------------------------------------

def _run_training(task: TaskInfo):
    """Run the training pipeline in a background thread."""
    with _tasks_lock:
        task.status = "running"

    def progress_callback(step: int, step_name: str, percent: float, msg: str = ""):
        entry = {
            "step": step,
            "step_name": step_name,
            "percent": int(percent),
            "message": msg,
        }
        with _tasks_lock:
            task.current_step = step
            task.step_percent = int(percent)
            task.step_message = msg
            task.step_history.append(entry)

    try:
        pipeline = TrainingPipeline(task.video_path, task.output_dir)
        pipeline.progress_callback = progress_callback
        pipeline.run()
        with _tasks_lock:
            task.status = "completed"
    except Exception as e:
        with _tasks_lock:
            task.status = "failed"
            task.error = str(e)
        import traceback
        traceback.print_exc()


def _json(obj) -> str:
    """Compact JSON serialization for SSE."""
    return json.dumps(obj, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 切换到项目根目录，确保所有相对路径（如 checkpoint/）正确解析
    os.chdir(str(_PROJECT_DIR))
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    print("数字人角色训练系统启动中...")
    print(f"上传目录: {_BASE_DIR}")
    print(f"项目目录: {_PROJECT_DIR}")
    print("打开浏览器访问: http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
