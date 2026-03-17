from app.database import SessionLocal
from app.models.models import Position
from app.services.vector_service import vector_service


def build_position_index():
    db = SessionLocal()
    try:
        positions = db.query(Position).all()
        vector_service.rebuild_position_index(positions)
        print(f"已建立职位向量索引，数量: {len(positions)}")
    finally:
        db.close()


if __name__ == "__main__":
    build_position_index()
