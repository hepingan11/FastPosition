from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class MessageRole(enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Position(Base):
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="职位名称")
    location = Column(String(100), nullable=True, comment="工作地点")
    jd = Column(Text, nullable=True, comment="职位描述")
    salary = Column(String(50), nullable=True, comment="薪资范围")
    link = Column(String(500), nullable=True, comment="投递链接")
    company = Column(String(200), nullable=True, comment="公司名称")
    source = Column(String(100), nullable=True, comment="来源")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), ForeignKey("chat_sessions.session_id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    session = relationship("ChatSession", back_populates="messages")


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    resumes = relationship("Resume", back_populates="user")


class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_url = Column(String(1000), nullable=True)
    content = Column(Text, nullable=True)
    parsed_info = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="resumes")


class CompanyLink(Base):
    __tablename__ = "company_link"
    
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(150), nullable=False, comment="公司名称")
    link = Column(Text, nullable=False, comment="链接")
    type = Column(String(20), nullable=True, comment='类型("校招","实习","应届","社招","其它")')
    create_at = Column(DateTime, nullable=False, comment="创建时间")
