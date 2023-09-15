import os
from sqlalchemy import create_engine, event, Column, Integer, ForeignKey, Enum, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, scoped_session

Base = declarative_base()


class Prompt(Base):
    __tablename__ = 'prompt'

    id = Column(Integer, primary_key=True)
    chat_prompt = Column(Text, nullable=False)
    integration_prompt = Column(Text, nullable=False)
    conversations = relationship("Conversation", back_populates="prompt", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = 'conversation'

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey('prompt.id'), nullable=False)
    user_id = Column(Integer, nullable=False)
    memory = Column(Text, nullable=False)
    prompt = relationship("Prompt", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = 'message'

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversation.id'), nullable=False)
    role = Column(Enum("user", "assistant"), nullable=False)
    content = Column(Text, nullable=False)
    conversation = relationship("Conversation", back_populates="messages")


def initialize_db():
    event.listens_for(engine, "connect")(_set_sqlite_pragma)
    Base.metadata.create_all(bind=engine)


# Ensure ForeignKey constraint enforcement
def _set_sqlite_pragma(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


DATABASE_URL = os.getenv('DATABASE_URL', "sqlite:///./development.db")
engine = create_engine(DATABASE_URL)
Session = scoped_session(sessionmaker(bind=engine))
