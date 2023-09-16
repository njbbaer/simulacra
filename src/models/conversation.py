from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base, Session
from .message import Message


class Conversation(Base):
    __tablename__ = 'conversations'

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey('prompt.id'), nullable=False)
    user_id = Column(Integer, nullable=False)
    memory_state = Column(Text, nullable=False)
    prompt = relationship("Prompt", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    @classmethod
    def create_conversation(cls, prompt_id, user_id, memory_state):
        new_conversation = cls(prompt_id=prompt_id, user_id=user_id, memory_state=memory_state)
        Session.add(new_conversation)
        Session.commit()

    @classmethod
    def get_latest_conversation(cls, prompt_id, user_id):
        return (Session.query(cls)
                .filter_by(prompt_id=prompt_id, user_id=user_id)
                .order_by(cls.id.desc())
                .first())

    def add_message(self, role, content):
        new_message = Message(conversation_id=self.id, role=role, content=content)
        Session.add(new_message)
        Session.commit()

    def get_messages(self):
        return Session.query(Message).filter(Message.conversation_id == self.id).all()
