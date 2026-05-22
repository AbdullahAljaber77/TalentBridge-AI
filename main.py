from fastapi import FastAPI
import os
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env تلقائياً
load_dotenv()

app = FastAPI()

@app.get("/")
def read_root():
    # هنا نقرأ متغير تجريبي للتأكد من ربط الأسرار مستقبلاً
    app_env = os.getenv("FASTAPI_ENV", "Not Found")
    return {
        "message": "Welcome to Employer Outreach Agent API!",
        "status": "Running successfully",
        "environment": app_env
    }