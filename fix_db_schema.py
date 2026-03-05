import os
from sqlmodel import create_engine, text, Session
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv('.env.local', override=True)
except ImportError:
    print("python-dotenv not installed, relying on existing env vars.")

def check_and_fix():
    DB_USER = os.getenv('DB_USER', 'user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_NAME = os.getenv('DB_NAME', 'chatbot_db')
    DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'

    print(f'Connecting to {DATABASE_URL}...')
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        # Check existing columns
        result = session.exec(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'evaluation_result';
        """))
        columns = [row[0] for row in result]
        print(f"Existing columns: {columns}")
        
        if not columns:
            print("Table 'evaluation_result' not found.")
            return

        if 'meta_info' not in columns:
            print("Adding 'meta_info' column...")
            try:
                session.exec(text("ALTER TABLE evaluation_result ADD COLUMN meta_info JSONB;"))
                session.commit()
                print("Column 'meta_info' added successfully.")
            except Exception as e:
                session.rollback()
                print(f"Error adding column: {e}")
        else:
            print("Column 'meta_info' already exists.")

if __name__ == "__main__":
    check_and_fix()
