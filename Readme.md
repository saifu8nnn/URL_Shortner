# Pro URL Shortener API

A production-ready URL shortener REST API built with **FastAPI**, **PostgreSQL**, and **SQLAlchemy 2.0**. Designed with real-world backend engineering practices including structured logging, collision-safe code generation, atomic DB operations, and Docker-based deployment.

## Tech Stack

- **FastAPI** — async-capable Python web framework with automatic OpenAPI docs
- **PostgreSQL** — relational database with index-optimized short code lookups
- **SQLAlchemy 2.0** — ORM with modern `Mapped` type annotations
- **Alembic** — database migration management
- **Pydantic v2** — request/response validation and settings management
- **Docker + Docker Compose** — containerized local development

## Features

- Shorten any valid URL to a 6-character alphanumeric code
- Redirect with atomic click tracking (race-condition safe)
- Per-URL analytics endpoint
- Deactivate URLs without deleting them (soft delete pattern)
- Real health check that verifies DB connectivity
- Structured logging across all layers
- Environment-aware configuration (dev/staging/production)

## Project Structure

```
app/
├── api/
│   └── routes.py        # All endpoints
├── core/
│   └── config.py        # Settings via pydantic-settings
├── db/
│   └── session.py       # Engine, session, Base
├── models/
│   └── url.py           # SQLAlchemy URL model
├── schemas/
│   └── url.py           # Pydantic request/response schemas
└── main.py              # App factory, middleware, lifespan
alembic/                 # Database migrations
docker-compose.yml
Dockerfile
requirements.txt
```

## Getting Started

### 1. Clone and configure

```bash
git clone https://github.com/saifu8nnn/URL_Shortner.git
cd URL_Shortner
cp .env.example .env
# Edit .env with your values
```

### 2. Start with Docker Compose

```bash
docker compose up --build
```

### 3. Run migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Access the API

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/shorten` | Create a short URL |
| `GET` | `/api/v1/r/{short_code}` | Redirect to original URL |
| `GET` | `/api/v1/analytics/{short_code}` | Get click analytics |
| `PATCH` | `/api/v1/{short_code}/deactivate` | Deactivate a URL |
| `GET` | `/health` | Server + DB health check |

## Example Usage

```bash
# Shorten a URL
curl -X POST http://localhost:8000/api/v1/shorten \
  -H "Content-Type: application/json" \
  -d '{"original_url": "https://github.com/saifu8nnn"}'

# Response
{
  "id": 1,
  "original_url": "https://github.com/saifu8nnn",
  "short_code": "aB3xYz",
  "short_url": "http://localhost:8000/api/v1/r/aB3xYz",
  "clicks": 0,
  "is_active": true,
  "created_at": "2026-04-24T10:00:00Z"
}

# Get analytics
curl http://localhost:8000/api/v1/analytics/aB3xYz
```