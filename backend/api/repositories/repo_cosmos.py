import os, time
from datetime import datetime
from typing import List, Dict, Any
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from .base import DataRepo

COSMOS_URL   = os.getenv("AZURE_COSMOS_ENDPOINT")
COSMOS_KEY   = os.getenv("AZURE_COSMOS_KEY")
COSMOS_DB    = os.getenv("AZURE_COSMOS_DATABASE")
STYLES_CN    = os.getenv("AZURE_COSMOS_STYLES_CONTAINER",  "styles")
OUTPUTS_CN   = os.getenv("AZURE_COSMOS_OUTPUTS_CONTAINER", "outputs")

_client   = CosmosClient(url=COSMOS_URL, credential=COSMOS_KEY) if COSMOS_URL and COSMOS_KEY else None
_database = _client.get_database_client(COSMOS_DB) if _client and COSMOS_DB else None

def _ensure():
    if not _client or not _database:
        raise RuntimeError("Cosmos client not configured (check AZURE_COSMOS_* env).")

class CosmosRepo(DataRepo):
    def __init__(self):
        _ensure()
        self.styles  = _database.get_container_client(STYLES_CN)
        self.outputs = _database.get_container_client(OUTPUTS_CN)

    # -------- Styles --------
    def list_styles(self) -> List[Dict[str, Any]]:
        items = list(self.styles.query_items(
            query="SELECT * FROM c ORDER BY c.name",
            enable_cross_partition_query=True
        ))
        return [{"id": it["id"], "name": it.get("name",""), "style": it.get("style",""), "example": it.get("example","")}
                for it in items]

    def create_or_update_style(self, name: str, style: str, example: str) -> Dict[str, Any]:
        # Use (name) as unique key in your Cosmos container (as in your old code)
        # Try to find existing
        items = list(self.styles.query_items(
            query="SELECT * FROM c WHERE c.name = @n",
            parameters=[{"name":"@n","value": name}],
            enable_cross_partition_query=True
        ))
        now = datetime.utcnow().isoformat()
        if items:
            doc = items[0]
            doc.update({"style": style, "example": example, "updatedAt": now})
            self.styles.replace_item(item=doc, body=doc)
            return {"id": doc["id"], "name": doc["name"], "style": doc.get("style",""), "example": doc.get("example","")}
        else:
            doc = {
                "id": str(int(time.time()*1000)),
                "name": name,
                "style": style,
                "example": example,
                "updatedAt": now,
            }
            self.styles.create_item(body=doc)
            return {"id": doc["id"], "name": doc["name"], "style": doc["style"], "example": doc["example"]}

    def delete_style(self, style_id: str) -> None:
        items = list(self.styles.query_items(
            query="SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name":"@id","value": style_id}],
            enable_cross_partition_query=True
        ))
        if items:
            it = items[0]
            pk = it.get("user_id") or it.get("name") or it["id"]  # prefer user_id if present
            self.styles.delete_item(item=it["id"], partition_key=pk)


    # -------- Outputs --------
    def list_outputs(self, limit: int = 100) -> List[Dict[str, Any]]:
        query = f"SELECT TOP {int(limit)} * FROM c ORDER BY c.updatedAt DESC"
        items = list(self.outputs.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return [{
            "id": it["id"],
            "style_name": it.get("styleId") or it.get("style_name",""),
            "preview": (it.get("output","")[:280]),
            "created_at": it.get("updatedAt")
        } for it in items]

    def save_output(self, style_name: str, input_text: str, output_text: str) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        doc = {
            "id": str(int(time.time()*1000)),
            "updatedAt": now,
            "content": input_text,
            "styleId": style_name,
            "output": output_text,
        }
        self.outputs.create_item(body=doc)
        return {"id": doc["id"], "style_name": style_name}
