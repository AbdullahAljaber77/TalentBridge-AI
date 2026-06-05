"""
TalentBridge AI - Core Configuration Loader
Description: Securely loads, validates, and exposes environment variables for the multi-agent system.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Define directory paths relative to this configuration file
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the root .env file
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    print(f"Critical Error: .env file is missing at expected root path: {env_path}")
    sys.exit(1)

# --- Core LLM Provider API Credentials ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")

# --- Relational Database Infrastructure ---
DATABASE_URL      = os.getenv("DATABASE_URL")

# --- External Intelligence Tools & OSINT APIs ---
TAVILY_API_KEY    = os.getenv("TAVILY_API_KEY")
HUNTER_IO_API_KEY = os.getenv("HUNTER_IO_API_KEY")

# --- Optional Outbound Email Transport Credentials ---
GMAIL_API_KEY     = os.getenv("GMAIL_API_KEY")
SENDGRID_API_KEY  = os.getenv("SENDGRID_API_KEY")

# --- System Deployment & Diagnostics Settings ---
APP_ENV           = os.getenv("APP_ENV", "development").lower()
DEBUG             = os.getenv("DEBUG", "True").upper() == "TRUE"

# --- Runtime Structural Validations ---
if not DATABASE_URL:
    print("Configuration Error: 'DATABASE_URL' environment variable is not set!")
    sys.exit(1)

if not ANTHROPIC_API_KEY and not OPENAI_API_KEY:
    print("Configuration Warning: No LLM provider API keys discovered. Agent runtimes will fail.")