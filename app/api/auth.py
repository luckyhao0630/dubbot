from fastapi import APIRouter, HTTPException, Depends, Header, Form
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
import secrets
import hashlib

from app.models.database import User, get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

SECRET_KEY = os.environ.get("SECRET_KEY", "dubbot-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def _hash_password(password: str) -> str:
    """使用 SHA256 哈希密码（避免 bcrypt 版本兼容问题）"""
    return hashlib.sha256(password.encode()).hexdigest()

def _verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return _hash_password(password) == hashed

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user_dependency(
    authorization: str = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
):
    """简化版认证：支持 API Key 或 JWT Token"""
    
    # 如果是 API Key 格式（没有 Bearer 前缀）
    if authorization and not authorization.startswith("Bearer "):
        user = db.query(User).filter(User.api_key == authorization.strip()).first()
        if user:
            return user
    
    # JWT Token 验证
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if email:
                user = db.query(User).filter(User.email == email).first()
                if user:
                    return user
        except JWTError:
            pass
    
    # 开发模式：返回一个默认用户
    # TODO: 生产环境移除
    user = db.query(User).filter(User.email == "dev@dubbot.com").first()
    if not user:
        user = User(
            email="dev@dubbot.com",
            hashed_password=_hash_password("dev"),
            api_key=secrets.token_urlsafe(32),
            plan="pro",
            minutes_limit=-1
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@router.post("/register")
def register(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email already registered")
    
    user = User(
        email=email,
        hashed_password=_hash_password(password),
        api_key=secrets.token_urlsafe(32)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "api_key": user.api_key}

@router.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not _verify_password(password, user.hashed_password):
        raise HTTPException(400, "Invalid credentials")
    
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "api_key": user.api_key}
