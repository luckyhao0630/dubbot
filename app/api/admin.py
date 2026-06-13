from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.database import get_db, User, Promotion, UserPromotion, UsageLog
from app.api.auth import get_current_user_dependency

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

def require_admin(current_user: User = Depends(get_current_user_dependency)):
    """检查是否为管理员（简化版：email 包含 admin 或者是特定用户）"""
    # 临时方案：特定用户为管理员
    admin_emails = ["admin@dubbot.com", "peng@dubbot.com"]
    if current_user.email not in admin_emails:
        raise HTTPException(403, "Admin access required")
    return current_user

@router.get("/promotions")
async def list_promotions(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """获取所有活动"""
    promotions = db.query(Promotion).all()
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "description": p.description,
            "bonus_minutes": p.bonus_minutes,
            "bonus_quota": p.bonus_quota,
            "is_active": p.is_active,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "end_date": p.end_date.isoformat() if p.end_date else None,
            "max_uses": p.max_uses,
            "current_uses": p.current_uses,
        }
        for p in promotions
    ]

@router.post("/promotions")
async def create_promotion(
    code: str,
    name: str,
    description: str = "",
    bonus_minutes: float = 0,
    bonus_quota: int = 0,
    max_uses: int = -1,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """创建新活动"""
    if db.query(Promotion).filter(Promotion.code == code).first():
        raise HTTPException(400, "Promotion code already exists")
    
    promotion = Promotion(
        code=code,
        name=name,
        description=description,
        bonus_minutes=bonus_minutes,
        bonus_quota=bonus_quota,
        max_uses=max_uses,
    )
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    return {"id": promotion.id, "code": code, "status": "created"}

@router.put("/promotions/{promotion_id}")
async def update_promotion(
    promotion_id: int,
    name: str = None,
    description: str = None,
    bonus_minutes: float = None,
    bonus_quota: int = None,
    is_active: bool = None,
    max_uses: int = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """更新活动"""
    promotion = db.query(Promotion).filter(Promotion.id == promotion_id).first()
    if not promotion:
        raise HTTPException(404, "Promotion not found")
    
    if name is not None:
        promotion.name = name
    if description is not None:
        promotion.description = description
    if bonus_minutes is not None:
        promotion.bonus_minutes = bonus_minutes
    if bonus_quota is not None:
        promotion.bonus_quota = bonus_quota
    if is_active is not None:
        promotion.is_active = is_active
    if max_uses is not None:
        promotion.max_uses = max_uses
    
    db.commit()
    return {"status": "updated", "id": promotion_id}

@router.delete("/promotions/{promotion_id}")
async def delete_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """删除活动"""
    promotion = db.query(Promotion).filter(Promotion.id == promotion_id).first()
    if not promotion:
        raise HTTPException(404, "Promotion not found")
    
    db.delete(promotion)
    db.commit()
    return {"status": "deleted", "id": promotion_id}

@router.get("/stats")
async def get_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """获取统计数据"""
    total_users = db.query(User).count()
    total_tasks = db.query(UsageLog).count()
    total_minutes = db.query(UsageLog).filter(UsageLog.duration != None).count()
    
    # 按方案统计用户
    plan_stats = {}
    for user in db.query(User).all():
        plan = user.plan or "free"
        if plan not in plan_stats:
            plan_stats[plan] = 0
        plan_stats[plan] += 1
    
    return {
        "total_users": total_users,
        "total_tasks": total_tasks,
        "total_minutes_processed": total_minutes,
        "plan_distribution": plan_stats,
    }

@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """获取用户列表"""
    users = db.query(User).offset(skip).limit(limit).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "plan": u.plan,
            "minutes_used": u.minutes_used,
            "minutes_limit": u.minutes_limit,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]
