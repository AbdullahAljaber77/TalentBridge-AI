import os
import pandas as pd
from sqlalchemy import create_engine

# Import the centralized DATABASE_URL from your database configuration file
from database import DATABASE_URL

# ==========================================
# FILE SYSTEM CONFIGURATION
# ==========================================

# Resolve the absolute path dynamically to locate the source CSV dataset
current_dir = os.path.dirname(os.path.abspath(__file__))
csv_file_path = os.path.join(current_dir, "app", "data", "saudi_job_market.csv")

# Fallback path execution framework
if not os.path.exists(csv_file_path):
    csv_file_path = os.path.join(current_dir, "data", "saudi_job_market.csv")


def ingest_full_dataset():
    """
    Executes a high-performance batch data ingestion pipeline.
    Streams raw job market CSV data into the cloud Neon PostgreSQL instance using chunks.
    """
    print(f"[INFO] Initiating data ingestion sequence from: {csv_file_path}")
    try:
        # Initialize the SQLAlchemy connection engine using the imported credential URL
        engine = create_engine(DATABASE_URL)
        
        # Define optimal chunk size for stability and network failure prevention
        chunk_size = 5000
        total_rows_inserted = 0
        
        # Stream specific schema columns to optimize memory consumption
        chunks = pd.read_csv(
            csv_file_path, 
            usecols=['job_title', 'company_name', 'description_text'],
            chunksize=chunk_size
        )
        
        # Explicit target database table mapping configuration
        column_mapping = {
            'job_title': 'title',
            'company_name': 'company_name',
            'description_text': 'description'
        }
        
        print("[PROCESSING] Streaming data packages sequentially to Neon Cloud...")
        
        for i, chunk in enumerate(chunks, 1):
            # 1. Normalize schema header columns
            chunk.rename(columns=column_mapping, inplace=True)
            
            # 2. Enforce data integrity constraints by removing rows with missing core identifiers
            chunk.dropna(subset=['title', 'company_name'], inplace=True)
            
            # 3. Inject baseline execution state workflow flag for the downstream Multi-Agent System
            chunk['status'] = 'Pending_Analysis'
            
            # 4. Commit data block to the cloud repository database table
            chunk.to_sql('jobs', con=engine, if_exists='append', index=False)
            
            total_rows_inserted += len(chunk)
            print(f"[BATCH {i}] Committed {len(chunk)} records. (Total progress: {total_rows_inserted})")
            
        print("\n[SUCCESS] Pipeline operation finalized without execution blockages.")
        print(f"[SUMMARY] Active target dataset records live in Cloud Neon: {total_rows_inserted}")
        
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline execution terminated abruptly: {e}")


if __name__ == "__main__":
    ingest_full_dataset()