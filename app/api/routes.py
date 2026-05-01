import logging
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.url import URL
from app.schemas.url import URLAnalytics, URLCreate, URLResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["URL Shortener"])

_ALPHABET = string.ascii_letters + string.digits


def _generate_short_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(settings.SHORT_CODE_LENGTH))


def _build_short_url(short_code: str) -> str:
    return f"{settings.BASE_URL}/{short_code}"


@router.post(
    "/shorten",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shortened URL",
)
def create_short_url(url_data: URLCreate, db: Session = Depends(get_db)):
    for attempt in range(1, settings.SHORT_CODE_MAX_RETRIES + 1):
        short_code = _generate_short_code()
        new_url = URL(
            original_url=str(url_data.original_url),
            short_code=short_code,
        )
        db.add(new_url)
        try:
            db.commit()
            db.refresh(new_url)
            logger.info("Created short URL: code=%s", short_code)
            response = URLResponse.model_validate(new_url)
            response.short_url = _build_short_url(short_code)
            return response
        except IntegrityError:
            db.rollback()
            logger.warning("Collision on attempt %d: code=%s", attempt, short_code)

    logger.error("Failed to generate unique short code after %d attempts", settings.SHORT_CODE_MAX_RETRIES)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not generate a unique short code. Please try again.",
    )


@router.get(
    "/r/{short_code}",
    summary="Redirect to original URL",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
)

def redirect_to_url(short_code: str, db: Session = Depends(get_db)):
    if not (1 <= len(short_code) <= 20 and all(c in _ALPHABET for c in short_code)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid short code format.",
        )
    
    # 2. Fetch the entry
    url_entry = db.query(URL).filter(URL.short_code == short_code).first()

    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found.")

    if not url_entry.is_active:
        raise HTTPException(status_code=410, detail="URL deactivated.")

    # 3. Update clicks using the object (Reliable)
    url_entry.clicks += 1
    db.commit() # Save the click!
    
    destination_url = str(url_entry.original_url).strip()
    
    logger.info(f"Attempting redirect to: {destination_url}")
    
    return RedirectResponse(
        url=destination_url, 
        status_code=status.HTTP_302_FOUND
    )
    
####################


@router.get(
    "/analytics/{short_code}",
    response_model=URLAnalytics,
    summary="Get analytics for a short URL",
)
def get_analytics(short_code: str, db: Session = Depends(get_db)):
    url_entry = db.query(URL).filter(URL.short_code == short_code).first()

    if not url_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found.")

    response = URLAnalytics.model_validate(url_entry)
    response.short_url = _build_short_url(short_code)
    return response


@router.patch(
    "/{short_code}/deactivate",
    response_model=URLAnalytics,
    summary="Deactivate a short URL",
)
def deactivate_url(short_code: str, db: Session = Depends(get_db)):
    url_entry = db.query(URL).filter(URL.short_code == short_code).first()

    if not url_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found.")

    if not url_entry.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="URL is already deactivated.")

    url_entry.is_active = False
    db.commit()
    db.refresh(url_entry)

    logger.info("Deactivated short URL: code=%s", short_code)
    response = URLAnalytics.model_validate(url_entry)
    response.short_url = _build_short_url(short_code)
    return response