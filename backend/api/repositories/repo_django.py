from .base import DataRepo
from typing import List, Dict, Any
from ..models import Style, Output

class DjangoRepo(DataRepo):
    def list_styles(self) -> List[Dict[str, Any]]:
        return [{"id": s.id, "name": s.name, "style": s.style, "example": s.example}
                for s in Style.objects.order_by("name")]

    def create_or_update_style(self, name: str, style: str, example: str) -> Dict[str, Any]:
        obj, _ = Style.objects.update_or_create(name=name, defaults={"style": style, "example": example})
        return {"id": obj.id, "name": obj.name, "style": obj.style, "example": obj.example}

    def delete_style(self, style_id: str) -> None:
        Style.objects.filter(id=style_id).delete()

    def list_outputs(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = Output.objects.order_by("-created_at")[:limit]
        return [{"id": r.id, "style_name": r.style_name, "preview": r.output_text[:280], "created_at": r.created_at}
                for r in rows]

    def save_output(self, style_name: str, input_text: str, output_text: str) -> Dict[str, Any]:
        rec = Output.objects.create(style_name=style_name, input_text=input_text, output_text=output_text)
        return {"id": rec.id, "style_name": rec.style_name}
