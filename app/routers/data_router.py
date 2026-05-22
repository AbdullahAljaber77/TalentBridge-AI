from fastapi import APIRouter
import pandas as pd
import os

router = APIRouter(
    prefix="/data",
    tags=["Data Operations"]
)

DATA_PATH = "data/saudi_job_market.csv"

@router.get("/sample")
def get_data_sample():
    if os.path.exists(DATA_PATH):
        # حساب الإحصائيات بشكل سريع وخفيف
        df_stats = pd.read_csv(DATA_PATH, usecols=["company_name", "job_title"])
        total_rows = len(df_stats)
        unique_companies = df_stats["company_name"].nunique()
        unique_jobs = df_stats["job_title"].nunique()
        
        # قراءة عينة خفيفة وتنظيفها من الـ NaN
        df_sample = pd.read_csv(DATA_PATH, nrows=5).fillna("")
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