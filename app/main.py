# app/main.py
from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Pro URL Shortener")

# Plug our new router into the main app!
app.include_router(router)

@app.get("/health")
def health_check():
    return {"status": "Database and Server are healthy!"}