from fastapi import FastAPI
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# مسار ملف البيانات الضخم داخل مجلدك
DATA_PATH = "data/saudi_job_market.csv"

@app.get("/")
def read_root():
    return {
        "message": "Welcome to Employer Outreach Agent API!",
        "status": "Running successfully"
    }

@app.get("/data-sample")
def get_data_sample():
    if os.path.exists(DATA_PATH):
        # نقرأ فقط عمود أسماء الشركات والمسميات الوظيفية لتوفير الذاكرة وسرعة الحساب
        df_stats = pd.read_csv(DATA_PATH, usecols=["company_name", "job_title"])
        
        total_rows = len(df_stats)
        unique_companies = df_stats["company_name"].nunique()
        unique_jobs = df_stats["job_title"].nunique()
        
        # نأخذ عينة صغيرة جداً للعرض فقط
        df_sample = pd.read_csv(DATA_PATH, nrows=3).fillna("")
        sample_data = df_sample.to_dict(orient="records")
        
        return {
            "file_found": True,
            "total_jobs_in_dataset": total_rows,
            "total_unique_companies_found": unique_companies,
            "total_unique_job_titles": unique_jobs,
            "sample_rows": sample_data
        }
    else:
        return {"file_found": False, "error": "Dataset not found"}