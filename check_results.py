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
    result = session.exec(text("SELECT id, evaluation_id, created_at, framework, is_valid FROM evaluation_result ORDER BY created_at DESC LIMIT 5;"))
    rows = result.all()
    if not rows:
        print("No evaluation results found.")
    for row in rows:
        print(row)
