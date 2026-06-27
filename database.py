import os
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME", "nigeria_infrastructure")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_PORT = os.environ.get("DB_PORT")

try:
    print(f"Initializing pool with Host={DB_HOST}, Name={DB_NAME}, User={DB_USER}, Port={DB_PORT}, PassPresent={DB_PASS is not None}")
    db_pool = pool.SimpleConnectionPool(
        1, 20, # Min and max connections
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    print("PostgreSQL connection pool established successfully.")
except Exception as e:
    print(f"Error creating database connection pool: {e}")
    db_pool = None

def get_db_connection():
    if db_pool:
        return db_pool.getconn()
    return None

def release_db_connection(conn):
    if db_pool and conn:
        db_pool.putconn(conn)