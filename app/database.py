from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("⚠️  DATABASE_URL not set – falling back to SQLite")
    DATABASE_URL = "sqlite:///./kojo_store.db"

# Fix old postgres:// scheme
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Works correctly with psycopg2-binary + Supabase
    connect_args = {
        "sslmode": "require",
        "connect_timeout": 15,
    }

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "connect_args": connect_args,
}

# Important for Supabase pooler (port 6543)
if "pooler.supabase.com" in DATABASE_URL or ":6543" in DATABASE_URL:
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
