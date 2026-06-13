from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api import dubbing, auth, image, audio, billing, admin, profile

app = FastAPI(title="DubBot", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(auth.router)
app.include_router(dubbing.router)
app.include_router(image.router)
app.include_router(audio.router)
app.include_router(billing.router)
app.include_router(admin.router)
app.include_router(profile.router)

# 健康检查
@app.get("/health")
def health():
    return {"status": "ok", "service": "dubbot"}

# 静态文件（处理后的视频）
os.makedirs("/tmp/dubbot/outputs", exist_ok=True)
app.mount("/outputs", StaticFiles(directory="/tmp/dubbot/outputs"), name="outputs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
