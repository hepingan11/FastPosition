from pathlib import Path
from typing import Optional
import chromadb
from chromadb.errors import InvalidArgumentError
from app.models.models import Position
from app.services.llm_service import llm_service


class VectorService:
    def __init__(self):
        store_dir = Path(__file__).resolve().parents[2] / "vector_store" / "chroma"
        store_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(store_dir))
        self.collection_name = "positions"
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def reset_collection(self) -> None:
        try:
            self.client.delete_collection(name=self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def build_position_text(self, position: Position) -> str:
        parts = [
            f"职位名称：{position.name or ''}",
            f"公司：{position.company or ''}",
            f"地点：{position.location or ''}",
            f"职位描述：{position.jd or ''}",
            f"薪资：{position.salary or ''}",
        ]
        return "\n".join(parts)

    def build_resume_text(self, resume_info: dict) -> str:
        target_positions = resume_info.get("target_positions") or []
        skills = resume_info.get("skills") or []
        if isinstance(target_positions, str):
            target_positions = [target_positions]
        if isinstance(skills, str):
            skills = [skills]

        parts = [
            f"目标岗位：{' '.join(target_positions)}",
            f"技能：{' '.join(skills)}",
            f"经历：{resume_info.get('experience', '')}",
            f"学历：{resume_info.get('education', '')}",
            f"地点：{resume_info.get('location', '')}",
            f"简介：{resume_info.get('summary', '')}",
        ]
        return "\n".join(parts)

    def index_positions(self, positions: list[Position]) -> None:
        if not positions:
            return

        ids = [str(position.id) for position in positions]
        documents = [self.build_position_text(position) for position in positions]
        embeddings = [llm_service.get_embeddings(document) for document in documents]
        metadatas = [
            {
                "position_id": position.id,
                "name": position.name or "",
                "company": position.company or "",
                "location": position.location or "",
            }
            for position in positions
        ]

        try:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
        except InvalidArgumentError as exc:
            if "dimension" not in str(exc).lower():
                raise
            self.reset_collection()
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )

    def rebuild_position_index(self, positions: list[Position]) -> None:
        try:
            existing = self.collection.get(include=[])
            existing_ids = existing.get("ids", [])
            if existing_ids:
                self.collection.delete(ids=existing_ids)
        except InvalidArgumentError as exc:
            if "dimension" not in str(exc).lower():
                raise
            self.reset_collection()
        self.index_positions(positions)

    def query_positions(self, resume_info: dict, limit: int = 20) -> list[dict]:
        query_text = self.build_resume_text(resume_info)
        query_embedding = llm_service.get_embeddings(query_text)
        try:
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit
            )
        except InvalidArgumentError as exc:
            if "dimension" not in str(exc).lower():
                raise
            self.reset_collection()
            return []

        ids = result.get("ids", [[]])
        distances = result.get("distances", [[]])
        if not ids or not ids[0]:
            return []

        items = []
        for index, position_id in enumerate(ids[0]):
            distance = distances[0][index] if distances and distances[0] and len(distances[0]) > index else None
            items.append(
                {
                    "position_id": int(position_id),
                    "distance": distance,
                }
            )
        return items


vector_service = VectorService()
