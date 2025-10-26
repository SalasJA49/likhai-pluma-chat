import os
from .repo_django import DjangoRepo
from .repo_cosmos import CosmosRepo

def get_repo():
    # Prefer explicit DATA_STORE setting. If not provided, but Cosmos env variables
    # are present, default to Cosmos so the migrated frontend sees the same data
    # as the old Streamlit app.
    mode = (os.getenv("DATA_STORE") or "").lower()
    if mode == "cosmos":
        from .repo_cosmos import CosmosRepo  # ← lazy import
        return CosmosRepo()
    if mode == "":
        # auto-detect: prefer Cosmos when configured
        if os.getenv("AZURE_COSMOS_ENDPOINT") and os.getenv("AZURE_COSMOS_KEY") and os.getenv("AZURE_COSMOS_DATABASE"):
            from .repo_cosmos import CosmosRepo
            return CosmosRepo()
    return DjangoRepo()

