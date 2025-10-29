# backend/api/services/config.py
import os, json
from pathlib import Path
from dotenv import load_dotenv
from django.conf import settings

load_dotenv()

def _resolve_local_data_path() -> Path | None:
    """Find local_data.json in common locations.

    Priority:
    1) APP_LOCAL_DATA_PATH env var (absolute or relative)
    2) <project root>/data/local_data.json
    3) <backend dir>/data/local_data.json
    """
    # 1) explicit env override
    env_path = os.getenv("APP_LOCAL_DATA_PATH", "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            return p

    # 2) repo root: settings.BASE_DIR is backend/, so parent is project root
    root_candidate = (Path(settings.BASE_DIR).parent / "data" / "local_data.json").resolve()
    if root_candidate.exists():
        return root_candidate

    # 3) backend/data
    backend_candidate = (Path(settings.BASE_DIR) / "data" / "local_data.json").resolve()
    if backend_candidate.exists():
        return backend_candidate

    return None


LOCAL_DATA_PATH = _resolve_local_data_path()


def load_locals():
    try:
        if LOCAL_DATA_PATH is None:
            return {}
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
