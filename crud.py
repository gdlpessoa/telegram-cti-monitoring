from sqlalchemy.orm import Session
from models import Message, Alert


def create_message(db: Session, msg: Message) -> Message:
    """
    Persist a new message to the database.
    
    Args:
        db: Database session
        msg: Message object to save
        
    Returns:
        Saved message with generated ID
    """
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def create_alert(db: Session, message: Message, keyword: str) -> Alert:
    """
    Create a security alert linked to a specific message.
    
    Args:
        db: Database session
        message: The message that triggered the alert
        keyword: The keyword that was detected
        
    Returns:
        Created alert with generated ID
    """
    db_alert = Alert(message_id=message.id, keyword_found=keyword)
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert