from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base


class Conversation(Base):
    __tablename__ = 'conversation'

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey('prompt.id'), nullable=False)
    user_id = Column(Integer, nullable=False)
    memory = Column(Text, nullable=False)
    prompt = relationship("Prompt", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
