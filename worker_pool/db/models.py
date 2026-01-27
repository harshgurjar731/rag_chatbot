from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
import enum

Base = declarative_base()

class BotStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    STOPPED = "stopped"
    ERROR = "error"

class Bot(Base):
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
    __tablename__ = 'worker_pools'

    id = Column(String, primary_key=True) # hostname or unique ID
    last_heartbeat = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    active_workers = Column(Integer, default=0)

def get_db_url():
    user = os.getenv("DB_USER", "user")
    password = os.getenv("DB_PASSWORD", "password")
    # host = os.getenv("DB_HOST", "db")
    host = os.getenv("DB_HOST", "localhost")
    dbname = os.getenv("DB_NAME", "chatbot_db")
    return f"postgresql://{user}:{password}@{host}/{dbname}"

def init_db():
    engine = create_engine(get_db_url())
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
