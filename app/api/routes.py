# app/api/routes.py
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.url import URL
from app.schemas.url import URLCreate, URLResponse

# Create the router (This is like a mini-FastAPI app we can plug into the main one)
router = APIRouter()

# 1. The POST endpoint to create a URL
# Notice we use response_model=URLResponse to force Pydantic to filter the output!
@router.post("/shorten", response_model=URLResponse)
def create_short_url(url_data: URLCreate, db: Session = Depends(get_db)):
    
    
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    random_code = "".join(secrets.choice(chars) for _ in range(6))
    
    # 2. Package the data into our SQLAlchemy Model
    # We must convert the HttpUrl object back to a standard string for the database
    new_url = URL(
        original_url=str(url_data.original_url), 
        short_code=random_code
    )
    
    # 3. Save it to the database
    db.add(new_url)     # Stage the data
    db.commit()         # Actually push it to PostgreSQL
    db.refresh(new_url) # Grab the fresh data back (so we have the generated 'id' and 'created_at')
    
    # 4. Return it to the user!
    return new_url