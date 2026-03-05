import os
from sqlmodel import create_engine, text, Session
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv('.env.local', override=True)
except:
    pass

DB_USER = os.getenv('DB_USER', 'user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'chatbot_db')
DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'

engine = create_engine(DATABASE_URL)
with Session(engine) as session:
    result = session.exec(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'evaluation_result';"))
    print(result.all())
