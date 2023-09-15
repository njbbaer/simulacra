from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship

from .base import Base


class Prompt(Base):
    __tablename__ = 'prompt'

    id = Column(Integer, primary_key=True)
    chat_prompt = Column(Text, nullable=False)
    integration_prompt = Column(Text, nullable=False)
    conversations = relationship("Conversation", back_populates="prompt", cascade="all, delete-orphan")
