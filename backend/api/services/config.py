# backend/api/services/config.py
import os, json
from pathlib import Path
from dotenv import load_dotenv
from django.conf import settings

load_dotenv()

# manage.py sits in backend/, so repo root is one level up
REPO_ROOT = settings.BASE_DIR.parent
LOCAL_DATA_PATH = REPO_ROOT / "data" / "local_data.json"

def load_locals():
    try:
        with open(LOCAL_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

LLM_LOCALS = load_locals()

AZURE_OAI = {
    "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
    "api_key": os.getenv("AZURE_OPENAI_KEY"),
    "api_version": os.getenv("AZURE_OPENAI_API_VERSION"),
    "deployment": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
}
