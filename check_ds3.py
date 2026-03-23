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

with conn.cursor() as cur:
    cur.execute("SELECT id, name, embedding_provider, embedding_model, vector_store_provider FROM datastore WHERE id = 3")
    row = cur.fetchone()
    if row:
        print(f"ID: {row[0]}")
        print(f"Name: {row[1]}")
        print(f"Embedding Provider: {row[2]}")
        print(f"Embedding Model: {row[3]}")
        print(f"Vector Store: {row[4]}")
    else:
        print("Datastore 3 not found")

conn.close()
