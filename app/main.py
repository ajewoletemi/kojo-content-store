from fastapi import FastAPI
from app.database import Base, engine
import app.models  # <-- THIS LINE CREATES USERS + PRODUCTS TABLES

app = FastAPI(title="Kojo Content Store API")

# THIS CREATES ALL TABLES ON STARTUP IF THEY DON'T EXIST
Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "Kojo Content Store API is running", "status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
