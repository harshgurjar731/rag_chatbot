import os
import psycopg2
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

bot_id = "a0cc917c-fe76-4bd9-a244-e55b6f8c20bd"

with conn.cursor() as cur:
    cur.execute("SELECT chatbot_id, llm_provider, llm_model FROM chatbotsettings WHERE chatbot_id = %s", (bot_id,))
    row = cur.fetchone()
    if row:
        print(f"Chatbot ID: {row[0]}")
        print(f"LLM Provider: {row[1]}")
        print(f"LLM Model: {row[2]}")
    else:
        print(f"No settings found for bot {bot_id}")

conn.close()
