from sqlalchemy.orm import Session
from rag_pipeline.db.models import Bot, BotStatus, init_db
from sqlalchemy.exc import IntegrityError

class BotManager:
    """
    Manages bot lifecycle via Database.
    Replaces ContainerManager.
    """
    def __init__(self):
        self.SessionLocal = init_db()

    def get_db(self):
        return self.SessionLocal()

    def create_bot(self, bot_id: str,name: str, datastore_id: str) -> tuple[bool, str]:
        db = self.get_db()
        try:
            # Check if exists
            existing = db.query(Bot).filter(Bot.bot_id == bot_id).first()
            if existing:
                return False, f"Bot '{bot_id}' already exists."
            
            new_bot = Bot(bot_id=bot_id,bot_name=name,datastore_id=datastore_id, status=BotStatus.PENDING)
            db.add(new_bot)
            db.commit()
            return True, f"Bot '{bot_id}' scheduled for creation."
        except Exception as e:
            db.rollback()
            return False, f"Error creating bot: {e}"
        finally:
            db.close()

    def delete_bot(self, bot_id: str) -> tuple[bool, str]:
        db = self.get_db()
        try:
            bot = db.query(Bot).filter(Bot.bot_id == bot_id).first()
            if not bot:
                return False, f"Bot '{bot_id}' not found."
            
            # Use 'STOPPED' or delete? If we delete, the pool might not know to kill it immediately
            # if we just remove the row. 
            # Better strategy: Mark STOPPED first, wait for cleanup?
            # For this demo, let's delete the row. 
            # The Worker Pool's 'check_process_health' checks if bot exists in DB. 
            # If not in DB, it kills the process.
            
            db.delete(bot)
            db.commit()
            return True, f"Bot '{bot_id}' deleted."
        except Exception as e:
            return False, f"Error deleting bot: {e}"
        finally:
            db.close()

    def get_bot_status(self, bot_id: str) -> str:
        db = self.get_db()
        try:
            bot = db.query(Bot).filter(Bot.bot_id == bot_id).first()
            return bot.status.value if bot else "unknown"
        finally:
            db.close()

    def get_all_bots(self):
        db = self.get_db()
        try:
            return db.query(Bot).all()
        finally:
            db.close()
