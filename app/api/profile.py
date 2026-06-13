from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import hashlib

from app.models.database import get_db, User, UserProfile
from app.api.auth import get_current_user_dependency

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _verify_password(password: str, hashed: str) -> bool:
    return _hash_password(password) == hashed

@router.get("")
async def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """获取用户资料"""
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "plan": current_user.plan,
        "api_key": current_user.api_key,
        "minutes_used": current_user.minutes_used,
        "minutes_limit": current_user.minutes_limit,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "display_name": profile.display_name if profile else None,
        "avatar_url": profile.avatar_url if profile else None,
        "company": profile.company if profile else None,
        "phone": profile.phone if profile else None,
    }

@router.put("")
async def update_profile(
    display_name: str = None,
    company: str = None,
    phone: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """更新用户资料"""
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
    
    if display_name is not None:
        profile.display_name = display_name
    if company is not None:
        profile.company = company
    if phone is not None:
        profile.phone = phone
    
    db.commit()
    return {"status": "updated"}

@router.put("/password")
async def change_password(
    current_password: str,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """修改密码"""
    if not _verify_password(current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    
    current_user.hashed_password = _hash_password(new_password)
    db.commit()
    return {"status": "password_changed"}
