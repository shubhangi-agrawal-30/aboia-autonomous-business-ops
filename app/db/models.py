from sqlalchemy import Column, String, Integer, DateTime, Text
from datetime import datetime
from app.db.database import Base
import uuid


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    episode_id = Column(String, unique=True, index=True)

    reasoning = Column(Text)      # JSON stored as string
    action_plan = Column(Text)    # JSON stored as string

    # Let application control timestamp (simulation aware)
    created_at = Column(DateTime, default=datetime.utcnow)


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(String, unique=True, index=True)

    type = Column(String)
    description = Column(String)
    owner = Column(String)
    priority = Column(String)

    # Lifecycle
    status = Column(String)
    approval_status = Column(String)

    # SLA
    sla_hours = Column(Integer)
    sla_deadline = Column(DateTime, nullable=True)
    sla_status = Column(String)

    # Execution metadata
    created_at = Column(DateTime)
    executed_at = Column(DateTime, nullable=True)

    # Failure info
    error_message = Column(Text, nullable=True)