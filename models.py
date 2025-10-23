from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Message(Base):
    """
    Database model for storing all collected Telegram messages.
    
    This table maintains a complete history of messages from monitored groups,
    including text content, image metadata, and OCR results.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    telegram_message_id = Column(Integer, unique=True, index=True)
    chat_name = Column(String(255), index=True)
    content = Column(Text, nullable=True)
    has_image = Column(Boolean, default=False)
    ocr_text = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    alerts = relationship("Alert", back_populates="message")


class Alert(Base):
    """
    Database model for storing security alerts triggered by keyword detection.
    
    Each alert is linked to a specific message and contains the keywords
    that triggered the security notification.
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"))
    keyword_found = Column(String(255), index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    message = relationship("Message", back_populates="alerts")