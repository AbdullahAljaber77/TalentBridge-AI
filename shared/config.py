"""
TalentBridge AI — Configuration Loader
Loads and validates all environment variables from .env
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    print(f"Warning: .env file not found at {env_path}. Falling back to system environment.")

# --- LLM APIs ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")

# --- Database ---
DATABASE_URL      = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/talentbridge")

# --- Search & Contact Discovery ---
TAVILY_API_KEY    = os.getenv("TAVILY_API_KEY")
HUNTER_IO_API_KEY = os.getenv("HUNTER_IO_API_KEY")

# --- Email (stretch goal) ---
GMAIL_API_KEY    = os.getenv("GMAIL_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# --- App Settings ---
APP_ENV = os.getenv("APP_ENV", "development").lower()
DEBUG   = os.getenv("DEBUG", "True").upper() == "TRUE"

# --- Validations (warn, don't crash — dev machines may not have all keys) ---
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set. Database calls will fail.")

if not ANTHROPIC_API_KEY and not OPENAI_API_KEY:
    print("WARNING: No LLM API key found. Agent calls will fail.")