from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import uuid
import time

from app.models.database import get_db, User, UsageLog
from app.api.auth import get_current_user_dependency
from app.core.image_processor import image_processor

router = APIRouter(prefix="/api/v1/image", tags=["image"])

@router.post("/translate")
async def translate_image(
    file: UploadFile = File(...),
    target_language: str = "en",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """图片翻译"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")
    
    upload_dir = "/tmp/dubbot/images"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # 调用图片处理引擎
    try:
        output_path = image_processor.translate(file_path, target_language)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")

@router.post("/remove-background")
async def remove_background(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """图片抠图"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")
    
    upload_dir = "/tmp/dubbot/images"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        output_path = image_processor.remove_background(file_path)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")

@router.post("/upscale")
async def upscale_image(
    file: UploadFile = File(...),
    scale: int = 2,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """图片超清修复"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")
    
    upload_dir = "/tmp/dubbot/images"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        output_path = image_processor.upscale(file_path, scale)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")

@router.post("/remove-text")
async def remove_text(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """图片去文字"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")
    
    upload_dir = "/tmp/dubbot/images"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        output_path = image_processor.remove_text(file_path)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")


@router.post("/to-cartoon")
async def to_cartoon(
    file: UploadFile = File(...),
    style: str = Form("anime"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """图片转动漫"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")
    
    upload_dir = "/tmp/dubbot/images"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        output_path = image_processor.to_anime(file_path, style)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")


@router.post("/inpaint")
async def inpaint(
    file: UploadFile = File(...),
    regions: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """图片擦除/修复"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")
    
    upload_dir = "/tmp/dubbot/images"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    import json
    try:
        mask_regions = json.loads(regions)
    except:
        mask_regions = []
    
    try:
        output_path = image_processor.inpaint(file_path, mask_regions)
        return {"status": "completed", "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")
