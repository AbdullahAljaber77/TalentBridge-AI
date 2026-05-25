import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ==========================================
# DATABASE CONFIGURATION & INITIALIZATION
# ==========================================

# Neon PostgreSQL connection URL - Ensure this is correctly bound in your .env file
DATABASE_URL = "postgresql://neondb_owner:npg_xCH2VhAQSi6j@ep-fancy-mountain-al2pkwvp-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Create the SQLAlchemy engine with connection pooling parameters for production stability
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True  # Automatically checks and repairs broken connections
)

# Configure the session factory for handling database transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ==========================================
# CORE DATABASE OPERATIONS (CRUD FOR AGENTS)
# ==========================================

def get_pending_jobs(limit: int = 5):
    """
    Fetches a batch of unanalyzed jobs from the database for the Researcher Agent.
    Filters by status 'Pending_Analysis' to prevent processing duplication.
    """
    session = SessionLocal()
    try:
        query = text("""
            SELECT id, title, company_name, description, status 
            FROM jobs 
            WHERE status = 'Pending_Analysis' 
            LIMIT :limit;
        """)
        result = session.execute(query, {"limit": limit})
        # Convert rows into a clean, readable list of dictionaries
        jobs = [dict(row._mapping) for row in result]
        return jobs
    except Exception as e:
        print(f"[ERROR] Failed to fetch pending jobs: {e}")
        return []
    finally:
        session.close()  # Always release the connection back to the pool


def update_job_status(job_id: int, new_status: str):
    """
    Updates the execution status of a specific job profile.
    Common statuses: 'Pending_Analysis', 'Analyzing', 'Ready_For_Outreach', 'Completed'.
    """
    session = SessionLocal()
    try:
        query = text("""
            UPDATE jobs 
            SET status = :status 
            WHERE id = :id;
        """)
        session.execute(query, {"status": new_status, "id": job_id})
        session.commit()  # Persist changes to the cloud database
        print(f"[SUCCESS] Job ID {job_id} status updated to '{new_status}'")
        return True
    except Exception as e:
        session.rollback()  # Rollback transaction in case of failure to maintain data integrity
        print(f"[ERROR] Failed to update job ID {job_id}: {e}")
        return False
    finally:
        session.close()


# Self-test block to verify connection and CRUD functions independently
if __name__ == "__main__":
    print("⏳ Testing database connection and pipeline functions...")
    sample_jobs = get_pending_jobs(limit=2)
    print(f"📊 Test Query Result: Found {len(sample_jobs)} pending jobs available for processing.")