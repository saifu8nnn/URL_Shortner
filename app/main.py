# app/main.py
from fastapi import FastAPI

app = FastAPI(
    title="Pro URL Shortener",
    description="A highly scalable, production-ready URL shortener API",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "API is up and running"}