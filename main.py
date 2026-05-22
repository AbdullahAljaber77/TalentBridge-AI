from fastapi import FastAPI
import sys
import os

# حل سحري لضمان رؤية مجلد app في جميع الأنظمة
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.routers.data_router import router as data_router

app = FastAPI(
    title="Employer Outreach Agent API",
    description="Multi-Agent System for Saudi Job Market Outreach",
    version="1.0.0"
)

# ربط الـ Router
app.include_router(data_router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to Employer Outreach Agent API!",
        "status": "Running successfully",
        "structure": "Modular Architecture Activated"
    }