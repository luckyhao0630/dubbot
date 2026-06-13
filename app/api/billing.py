from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import os

from app.models.database import get_db, User
from app.api.auth import get_current_user_dependency

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Paddle API配置（从环境变量读取）
PADDLE_API_KEY = os.environ.get("PADDLE_API_KEY", "")
PADDLE_VENDOR_ID = os.environ.get("PADDLE_VENDOR_ID", "")

# 价格方案（与前端一致）
PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "minutes_limit": 10,
        "features": ["3 languages", "720p output", "Watermark"]
    },
    "creator": {
        "name": "Creator",
        "price": 29,
        "minutes_limit": 120,
        "features": ["12 languages", "1080p output", "No watermark"]
    },
    "pro": {
        "name": "Pro",
        "price": 79,
        "minutes_limit": -1,  # unlimited
        "features": ["All languages", "4K output", "API access"]
    }
}

@router.get("/plans")
async def get_plans():
    """获取所有价格方案"""
    return PLANS

@router.get("/subscription")
async def get_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """获取当前用户订阅信息"""
    plan = PLANS.get(current_user.plan, PLANS["free"])
    return {
        "plan": current_user.plan,
        "plan_name": plan["name"],
        "minutes_used": current_user.minutes_used,
        "minutes_limit": current_user.minutes_limit,
        "features": plan["features"]
    }

@router.post("/upgrade")
async def upgrade_plan(
    plan: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """升级方案（简化版，实际需接入Paddle支付）"""
    if plan not in PLANS:
        raise HTTPException(400, "Invalid plan")
    
    # 更新用户方案
    current_user.plan = plan
    current_user.minutes_limit = PLANS[plan]["minutes_limit"]
    db.commit()
    
    return {
        "status": "success",
        "plan": plan,
        "message": f"Upgraded to {PLANS[plan]['name']}. Payment integration pending."
    }

@router.get("/usage")
async def get_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """获取用量统计"""
    plan = PLANS.get(current_user.plan, PLANS["free"])
    if current_user.minutes_limit == -1:
        remaining = None  # 无限
    else:
        remaining = max(0, current_user.minutes_limit - current_user.minutes_used)
    
    return {
        "minutes_used": current_user.minutes_used,
        "minutes_limit": current_user.minutes_limit,
        "minutes_remaining": remaining,
        "plan": current_user.plan,
        "plan_name": plan["name"]
    }

@router.get("/history")
async def get_billing_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """获取消费历史"""
    from app.models.database import UsageLog
    
    logs = db.query(UsageLog).filter(
        UsageLog.user_id == current_user.id
    ).order_by(UsageLog.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": log.id,
            "task_id": log.task_id,
            "action": log.action,
            "duration": log.duration,
            "cost": log.cost,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
