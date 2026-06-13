from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import uuid

from app.models.database import get_db, User, UsageLog
from app.api.auth import get_current_user_dependency
from app.core.audio_processor import audio_processor

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])

@router.post("/text-to-speech")
async def text_to_speech(
    text: str = Form(...),
    voice: str = Form("alloy"),
    language: str = Form("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """文字转语音 - Edge TTS本地方案"""
    try:
        output_path = audio_processor.text_to_speech(text, voice, language)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")

@router.post("/separate-vocals")
async def separate_vocals(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """人声分离"""
    if not file.content_type.startswith("audio/"):
        raise HTTPException(400, "只支持音频文件")
    
    upload_dir = "/tmp/dubbot/audio"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        result = audio_processor.separate_vocals(file_path)
        return {"status": "completed", "vocals": result["vocals"], "instrumental": result["instrumental"]}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")

@router.post("/merge")
async def merge_audio(
    files: List[UploadFile] = File(...),
    crossfade: float = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """音频拼接"""
    upload_dir = "/tmp/dubbot/audio"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_paths = []
    for file in files:
        file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(await file.read())
        file_paths.append(file_path)
    
    try:
        output_path = audio_processor.merge(file_paths, crossfade=crossfade)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")

@router.post("/extract-from-video")
async def extract_audio_from_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """从视频提取音频"""
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "只支持视频文件")
    
    upload_dir = "/tmp/dubbot/audio"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        output_path = audio_processor.extract_from_video(file_path)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")


@router.post("/split")
async def split_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """音频分割（基于静音检测）"""
    if not file.content_type.startswith("audio/"):
        raise HTTPException(400, "只支持音频文件")
    
    upload_dir = "/tmp/dubbot/audio"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        segments = audio_processor.split_by_silence(file_path)
        return {"status": "completed", "segments": segments}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")


@router.post("/mix")
async def mix_audio(
    files: List[UploadFile] = File(...),
    volumes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """音频混音"""
    upload_dir = "/tmp/dubbot/audio"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_paths = []
    for file in files:
        file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(await file.read())
        file_paths.append(file_path)
    
    vol_list = None
    if volumes:
        try:
            vol_list = [float(v) for v in volumes.split(",")]
        except:
            vol_list = None
    
    try:
        output_path = audio_processor.mix(file_paths, volumes=vol_list)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")


@router.post("/voice-clone")
async def voice_clone(
    text: str = Form(...),
    samples: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """语音克隆（GPT-SoVITS / Edge TTS fallback）"""
    if not text.strip():
        raise HTTPException(400, "Text is required")
    
    upload_dir = "/tmp/dubbot/audio"
    os.makedirs(upload_dir, exist_ok=True)
    
    sample_paths = []
    for sample in samples:
        sample_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{sample.filename}")
        with open(sample_path, "wb") as f:
            f.write(await sample.read())
        sample_paths.append(sample_path)
    
    try:
        output_path = audio_processor.clone_voice(sample_paths, text)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        print(f"Voice clone failed: {e}, using Edge TTS fallback")
        try:
            output_path = audio_processor.text_to_speech(text, voice="alloy", language="en")
            return {"status": "completed", "output_path": output_path, "note": "Fallback to standard TTS"}
        except Exception as e2:
            raise HTTPException(500, f"处理失败: {str(e2)}")
