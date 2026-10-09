from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

app = FastAPI(
    title="University Regulations API",
    version="1.0.0",
    description="Regulations and Forms Management System"
)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "university-regulations-api"
    }

@app.get("/health/db")
def database_health_check(
    db: Session = Depends(get_db)
):
    result = db.execute(text("SELECT 1"))

    return {
        "status": "connected",
        "database": "PostgreSQL",
        "result": result.scalar_one()
    }