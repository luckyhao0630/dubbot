from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./dubbot.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 订阅信息
    plan = Column(String, default="free")  # free, creator, pro
    minutes_used = Column(Float, default=0.0)
    minutes_limit = Column(Float, default=10.0)  # free=10, creator=120, pro=-1(unlimited)
    
    # API Key
    api_key = Column(String, unique=True, index=True)

class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    task_id = Column(String)
    action = Column(String)  # upload, process, download
    duration = Column(Float)  # 视频时长
    cost = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class Promotion(Base):
    __tablename__ = "promotions"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)  # 活动码
    name = Column(String)  # 活动名称
    description = Column(Text)  # 活动描述
    bonus_minutes = Column(Float, default=0)  # 赠送分钟数
    bonus_quota = Column(Integer, default=0)  # 赠送次数
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    max_uses = Column(Integer, default=-1)  # -1 表示无限
    current_uses = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserPromotion(Base):
    __tablename__ = "user_promotions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    promotion_id = Column(Integer)
    used_at = Column(DateTime, default=datetime.utcnow)

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True)
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    company = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

# 创建表
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
