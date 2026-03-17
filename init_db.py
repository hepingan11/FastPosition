import mysql.connector
from app.config import settings


def init_database():
    print("正在初始化数据库...")
    
    db_url = settings.DATABASE_URL
    
    db_config = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "123456"
    }
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("CREATE DATABASE IF NOT EXISTS susutou CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("✓ 数据库 'susutou' 已创建或已存在")
        
        cursor.execute("USE susutou")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✓ 数据库初始化完成！")
        
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        raise


if __name__ == "__main__":
    init_database()
