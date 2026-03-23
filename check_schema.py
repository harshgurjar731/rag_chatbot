import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('.env.local', override=True)

db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "chatbot_db")

conn = psycopg2.connect(
    dbname=db_name,
    user=db_user,
    password=db_pass,
    host=db_host
)

with conn.cursor() as cur:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'chatbotsettings'")
    columns = cur.fetchall()
    print("Columns in chatbotsettings:")
    for col in columns:
        print(f" - {col[0]}")

conn.close()
