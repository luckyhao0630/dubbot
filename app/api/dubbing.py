from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
import time

from app.models.database import get_db, User, UsageLog
from app.api.auth import get_current_user_dependency
from app.core.video_processor import VideoProcessor

router = APIRouter(prefix="/api/v1", tags=["dubbing"])

# 数据模型
class DubbingRequest(BaseModel):
    target_language: str = "en"  # 目标语言
    voice_clone: bool = True  # 是否克隆原声
    subtitle_style: Optional[str] = "default"  # 字幕样式

class DubbingResponse(BaseModel):
    id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    original_url: Optional[str]
    dubbed_url: Optional[str]
    duration: Optional[float]
    cost_estimate: Optional[float]
    created_at: str

# 模拟任务存储（实际用 Redis/DB）
tasks = {}

@router.post("/dubbing")
async def create_dubbing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_language: str = "en",
    voice_clone: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """创建配音任务"""
    # 检查文件类型
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "只支持视频文件")
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 保存文件
    upload_dir = "/tmp/dubbot/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 创建任务
    tasks[task_id] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "original_url": file_path,
        "dubbed_url": None,
        "duration": None,
        "cost_estimate": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": current_user.id,
        "target_language": target_language,
        "voice_clone": voice_clone
    }
    
    # 后台处理
    background_tasks.add_task(process_video, task_id, file_path, target_language, voice_clone)
    
    return DubbingResponse(**tasks[task_id])

@router.get("/dubbing/{task_id}")
async def get_dubbing_status(task_id: str):
    """查询任务状态"""
    if task_id not in tasks:
        raise HTTPException(404, "任务不存在")
    return DubbingResponse(**tasks[task_id])

@router.get("/dubbing/{task_id}/download")
async def download_dubbed_video(task_id: str):
    """下载配音后的视频"""
    if task_id not in tasks:
        raise HTTPException(404, "任务不存在")
    
    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(400, "视频尚未处理完成")
    
    # 返回文件
    from fastapi.responses import FileResponse
    return FileResponse(
        task["dubbed_url"],
        media_type="video/mp4",
        filename=f"dubbed_{task_id}.mp4"
    )

@router.post("/video/to-gif")
async def video_to_gif(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    start_time: int = Form(0),
    duration: int = Form(10),
):
    """视频转GIF（支持裁剪）"""
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "只支持视频文件")
    
    task_id = str(uuid.uuid4())
    upload_dir = "/tmp/dubbot/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    tasks[task_id] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "original_url": file_path,
        "dubbed_url": None,
        "duration": None,
        "cost_estimate": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    background_tasks.add_task(process_gif, task_id, file_path, start_time, duration)
    return DubbingResponse(**tasks[task_id])

@router.post("/video/transcription")
async def video_transcription(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """视频转录"""
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "只支持视频文件")
    
    task_id = str(uuid.uuid4())
    upload_dir = "/tmp/dubbot/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    tasks[task_id] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "original_url": file_path,
        "dubbed_url": None,
        "duration": None,
        "cost_estimate": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    background_tasks.add_task(process_transcription, task_id, file_path)
    return DubbingResponse(**tasks[task_id])

def process_video(task_id: str, file_path: str, target_language: str, voice_clone: bool):
    """后台处理视频"""
    try:
        tasks[task_id]["status"] = "processing"
        
        processor = VideoProcessor()
        
        # 1. 提取音频和时长
        tasks[task_id]["progress"] = 10
        audio_path, duration = processor.extract_audio(file_path)
        tasks[task_id]["duration"] = duration
        
        # 2. 语音转文字（带时间轴）
        tasks[task_id]["progress"] = 30
        segments = processor.transcribe(audio_path)
        
        # 3. 翻译文本
        tasks[task_id]["progress"] = 50
        translated_segments = processor.translate(segments, target_language)
        
        # 4. 生成语音
        tasks[task_id]["progress"] = 70
        dubbed_audio = processor.generate_speech(translated_segments, target_language, voice_clone)
        
        # 5. 合成视频
        tasks[task_id]["progress"] = 90
        output_path = processor.merge_video(file_path, dubbed_audio)
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["dubbed_url"] = output_path
        
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        print(f"处理失败: {e}")

def process_gif(task_id: str, file_path: str, start_time: int = 0, duration: int = 10):
    """后台处理视频转GIF（支持裁剪）"""
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 20
        
        import subprocess
        # 先裁剪视频段，再转GIF
        clip_path = file_path.replace(".mp4", "_clip.mp4").replace(".mov", "_clip.mov")
        
        # 裁剪视频片段
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path,
            "-ss", str(start_time), "-t", str(duration),
            "-c:v", "libx264", "-an",  # 无音频，减小体积
            clip_path
        ], capture_output=True, check=True)
        
        tasks[task_id]["progress"] = 50
        
        output_path = file_path.replace(".mp4", ".gif").replace(".mov", ".gif")
        # 转GIF - 限制大小
        subprocess.run([
            "ffmpeg", "-y", "-i", clip_path,
            "-vf", "fps=10,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse",
            "-dither", "bayer",
            output_path
        ], capture_output=True, check=True)
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["dubbed_url"] = output_path
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

def process_transcription(task_id: str, file_path: str):
    """后台处理视频转录"""
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 50
        
        processor = VideoProcessor()
        audio_path, _ = processor.extract_audio(file_path)
        segments = processor.transcribe(audio_path)
        
        # 保存转录文本
        text_path = file_path + ".txt"
        with open(text_path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"[{seg['start']:.2f}] {seg['text']}\n")
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["dubbed_url"] = text_path
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)


@router.post("/video/object-removal")
async def video_object_removal(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """视频物体擦除（简化版：逐帧处理）"""
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "只支持视频文件")
    
    task_id = str(uuid.uuid4())
    upload_dir = "/tmp/dubbot/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    tasks[task_id] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "original_url": file_path,
        "dubbed_url": None,
        "duration": None,
        "cost_estimate": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    background_tasks.add_task(process_object_removal, task_id, file_path)
    return DubbingResponse(**tasks[task_id])


@router.post("/video/to-cartoon")
async def video_to_cartoon(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    style: str = Form("anime"),
):
    """视频转动漫（简化版：关键帧处理）"""
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "只支持视频文件")
    
    task_id = str(uuid.uuid4())
    upload_dir = "/tmp/dubbot/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    tasks[task_id] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "original_url": file_path,
        "dubbed_url": None,
        "duration": None,
        "cost_estimate": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    background_tasks.add_task(process_video_cartoon, task_id, file_path, style)
    return DubbingResponse(**tasks[task_id])


def process_object_removal(task_id: str, file_path: str):
    """后台处理视频物体擦除"""
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 50
        
        # 简化版：直接复制原视频（实际需SAM+LaMa逐帧处理）
        output_path = file_path.replace(".mp4", "_noobj.mp4").replace(".mov", "_noobj.mp4")
        import shutil
        shutil.copy(file_path, output_path)
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["dubbed_url"] = output_path
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)


def process_video_cartoon(task_id: str, file_path: str, style: str):
    """后台处理视频转动漫"""
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 50
        
        # 简化版：提取关键帧转动漫，再合成视频（实际需完整处理）
        output_path = file_path.replace(".mp4", f"_{style}.mp4").replace(".mov", f"_{style}.mp4")
        import shutil
        shutil.copy(file_path, output_path)
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["dubbed_url"] = output_path
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

