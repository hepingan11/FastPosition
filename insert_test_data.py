from app.database import SessionLocal
from app.models.models import Position

def insert_test_data():
    db = SessionLocal()
    try:
        test_positions = [
            Position(
                name="后端开发工程师",
                location="北京",
                jd="负责公司核心业务系统的后端开发工作，使用Java、Python等技术栈。",
                salary="25k-45k",
                company="字节跳动",
                source="测试数据"
            ),
            Position(
                name="前端开发工程师",
                location="上海",
                jd="负责Web前端开发，使用React、Vue等框架，要求有3年以上经验。",
                salary="20k-40k",
                company="阿里巴巴",
                source="测试数据"
            ),
            Position(
                name="产品经理",
                location="深圳",
                jd="负责产品规划和设计，推动产品迭代优化。",
                salary="30k-50k",
                company="腾讯",
                source="测试数据"
            ),
            Position(
                name="数据分析师",
                location="杭州",
                jd="负责业务数据的分析和挖掘，为决策提供数据支持。",
                salary="18k-35k",
                company="美团",
                source="测试数据"
            ),
            Position(
                name="AI算法工程师",
                location="北京",
                jd="负责机器学习和深度学习算法研发，NLP方向优先。",
                salary="35k-60k",
                company="百度",
                source="测试数据"
            ),
            Position(
                name="全栈开发工程师",
                location="广州",
                jd="负责前后端全栈开发，熟悉Node.js和React。",
                salary="22k-42k",
                company="网易",
                source="测试数据"
            ),
            Position(
                name="测试工程师",
                location="成都",
                jd="负责软件质量保证，自动化测试经验优先。",
                salary="15k-30k",
                company="小米",
                source="测试数据"
            ),
            Position(
                name="运维工程师",
                location="武汉",
                jd="负责服务器运维和监控，熟悉K8s优先。",
                salary="18k-32k",
                company="京东",
                source="测试数据"
            )
        ]
        
        for pos in test_positions:
            existing = db.query(Position).filter(
                Position.name == pos.name,
                Position.company == pos.company
            ).first()
            if not existing:
                db.add(pos)
        
        db.commit()
        print("✓ 测试数据插入成功！")
        
    except Exception as e:
        print(f"✗ 插入失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    insert_test_data()
