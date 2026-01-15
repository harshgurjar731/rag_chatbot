"""
Database Models Module

This module defines the SQLAlchemy models for the worker pool database, including
Bots and WorkerPools. It also handles database initialization and connection.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
import enum

Base = declarative_base()

class BotStatus(enum.Enum):
    """Enumeration of possible bot statuses."""
    PENDING = "pending"
    ACTIVE = "active"
    STOPPED = "stopped"
    ERROR = "error"

class Bot(Base):
    """
    Represents a RAG Chatbot instance.
    
    Attributes:
        id (int): Primary Key.
        bot_id (str): Unique identifier for the bot (e.g., UUID).
        bot_name (str): Human-readable name of the bot.
        datastore_id (int): ID of the associated vector datastore.
        status (BotStatus): Current lifecycle status of the bot.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        pool_id (str): ID of the worker pool managing this bot.
    """
    __tablename__ = 'bots'

    id = Column(Integer, primary_key=True)
    bot_id = Column(String, unique=True, nullable=False)
    bot_name = Column(String, nullable=False)
    datastore_id = Column(Integer, nullable=False)
    status = Column(Enum(BotStatus), default=BotStatus.PENDING, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    pool_id = Column(String, ForeignKey('worker_pools.id'), nullable=True, index=True) # ID of the worker pool managing this bot

class WorkerPool(Base):
    """
    Represents a Worker Pool instance managed by a specific host/process.
    
    Attributes:
        id (str): Unique identifier (hostname or UUID).
        last_heartbeat (datetime): Timestamp of the last heartbeat signal.
        active_workers (int): Number of active bot workers in this pool.
    """
    __tablename__ = 'worker_pools'

    id = Column(String, primary_key=True) # hostname or unique ID
    last_heartbeat = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    active_workers = Column(Integer, default=0)

def get_db_url() -> str:
    """
    Construct the database connection URL from environment variables.
    
    Returns:
        str: The PostgreSQL connection string.
    """
    user = os.getenv("DB_USER", "user")
    password = os.getenv("DB_PASSWORD", "password")
    host = os.getenv("DB_HOST", "db")
    dbname = os.getenv("DB_NAME", "chatbot_db")
    return f"postgresql://{user}:{password}@{host}/{dbname}"

def init_db():
    """
    Initialize the database, create tables, and return a session factory.
    
    Returns:
        sessionmaker: A SQLAlchemy session factory bound to the engine.
    """
    engine = create_engine(get_db_url())
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
