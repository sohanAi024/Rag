from sqlalchemy import Column, Integer, String, LargeBinary, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector


Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    documents = relationship("Document", back_populates="user")
    chat_history = relationship("ChatHistory", back_populates="user")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    chunk = Column(String, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    source = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="documents")


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="chat_history")  # 🔧 Removed the comma
