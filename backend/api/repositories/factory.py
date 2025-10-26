import os
from .repo_django import DjangoRepo
from .repo_cosmos import CosmosRepo

def get_repo():
    mode = (os.getenv("DATA_STORE") or "django").lower()
    if mode == "cosmos":
        from .repo_cosmos import CosmosRepo  # ← lazy import
        return CosmosRepo()
    return DjangoRepo()

