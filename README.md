[README.md](https://github.com/user-attachments/files/27954937/README.md)
# 🏠 Yakeey — Moroccan Real Estate SaaS Backend

A production-grade Django REST API powering a real estate SaaS platform for the Moroccan market. Aggregates 2,527+ property listings, generates AI-powered video content, and distributes to social media platforms.

---

## 🚀 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.1 + Django REST Framework |
| Database | PostgreSQL 18 |
| Cache / Queue | Redis 7 |
| Task Queue | Celery + Celery Beat |
| Auth | JWT (djangorestframework-simplejwt) |
| Storage | Cloudflare R2 (S3-compatible) |
| Payments | Stripe |
| AI Captions | OpenAI GPT-4 |
| Video | FFmpeg |
| Data Collection | httpx + BeautifulSoup4 |

---

## 📦 Features

### Phase 1 — Foundation ✅
- Django project with split settings (dev/prod)
- PostgreSQL database with UUID primary keys
- JWT authentication (register, login, refresh, logout)
- Location hierarchy: Country → City → District → Neighborhood
- 16 Moroccan cities seeded
- Property models with 65 feature fields
- Yakeey CSV/Parquet import (2,527 listings, 27,411 images)
- Full REST API with camelCase JSON responses
- Subscription plans (Free / Starter / Pro / Agency)
- 6/6 tests passing

### Phase 2 — Platform Core ✅
- Celery background tasks + Beat scheduler
- PropertyFinder.ma agency data collector
- Full-text search (PostgreSQL SearchVector)
- Map clusters API with GPS coordinates
- Market statistics API (cached via Redis)
- Agency dashboard (analytics, leads, listings)
- Listing boost via Stripe checkout
- Rate limiting (100/hr anon, 1000/hr auth)

### Phase 3 — Media & Social ✅
- FFmpeg video generation (1080x1920 reels + 1080x1080 square)
- GPT-4 captions in French + Arabic with hashtags
- Cloudflare R2 video storage
- Instagram + Facebook posting via Meta Graph API v18
- Celery scheduled social posts (daily at 9 AM)
- Social performance tracking per listing

### Phase 4 — Monetisation 🔄
- Lead notification system (email + WhatsApp)
- Weekly agency reports
- Production hardening + CI/CD
- Nginx + Gunicorn + Systemd setup

---

## 🗂️ Project Structure

```
yakeey-backend/
├── config/                    # Django project config
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   └── urls.py
├── apps/
│   ├── properties/            # Core listing models + API
│   ├── agencies/              # Agency + user models + auth
│   ├── locations/             # City / District / Neighborhood
│   ├── analytics/             # View/click tracking
│   ├── scraper/               # Data import + agency collector
│   ├── subscriptions/         # Stripe billing
│   ├── notifications/         # Email + WhatsApp
│   ├── media_engine/          # FFmpeg + GPT-4
│   └── social/                # Instagram/Facebook posting
├── celery_tasks/              # All Celery task definitions
├── common/                    # Shared views (market stats)
├── tests/                     # pytest test suite
├── celery_app.py
├── manage.py
├── requirements.txt
└── Makefile
```

---

## ⚡ Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 18
- Redis 7
- FFmpeg (for video generation)

### Setup

```bash
# Clone the repo
git clone git@github.com:hamzaabialal/morocon-real-estate.git
cd morocon-real-estate

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create environment file
copy .env.example .env
# Edit .env with your credentials

# Create database
psql -U postgres -c "CREATE DATABASE yakeey;"

# Run migrations
python manage.py migrate

# Seed cities
python manage.py seed_morocco_cities

# Import Yakeey listings
python manage.py import_yakeey --file=data/Yakeey.csv

# Start server
python manage.py runserver
```

---

## 🔑 Environment Variables

```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgresql://postgres:password@localhost:5432/yakeey
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
AWS_ACCESS_KEY_ID=your-r2-key
AWS_SECRET_ACCESS_KEY=your-r2-secret
AWS_STORAGE_BUCKET_NAME=yakeey-media
AWS_S3_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_ACCOUNT_ID=...
FACEBOOK_PAGE_ID=...
FACEBOOK_PAGE_ACCESS_TOKEN=...
```

---

## 📡 API Endpoints

### Properties
```
GET  /api/v1/properties/                    # List with filters
GET  /api/v1/properties/{id}/               # Detail
GET  /api/v1/properties/search/?q=villa     # Full-text search
GET  /api/v1/properties/featured/           # Featured listings
POST /api/v1/properties/{id}/track-view/    # Track view
POST /api/v1/properties/{id}/track-click/   # Track click
POST /api/v1/properties/{id}/boost/         # Boost listing (Stripe)
```

### Auth
```
POST /api/v1/auth/register/
POST /api/v1/auth/login/
POST /api/v1/auth/refresh/
POST /api/v1/auth/logout/
```

### Locations
```
GET /api/v1/locations/cities/
GET /api/v1/locations/districts/
GET /api/v1/locations/neighborhoods/
GET /api/v1/locations/map-clusters/?bbox=lng1,lat1,lng2,lat2
```

### Agency Dashboard
```
GET  /api/v1/agencies/me/
GET  /api/v1/agencies/me/analytics/?period=30d
GET  /api/v1/agencies/me/leads/
GET  /api/v1/agencies/me/listings/
GET  /api/v1/agencies/me/social/
```

### Market Stats
```
GET /api/v1/stats/market/
GET /api/v1/stats/market/?city=casablanca&transaction_type=SALE
```

### Subscriptions
```
GET  /api/v1/subscriptions/plans/
POST /api/v1/subscriptions/subscribe/
POST /api/v1/subscriptions/cancel/
POST /api/v1/webhooks/stripe/
```

---

## 🛠️ Makefile Commands

```bash
make run       # Start Django server
make migrate   # Run migrations
make seed      # Seed Morocco cities
make import    # Import Yakeey CSV
make test      # Run pytest
make shell     # Django shell
make celery    # Start Celery worker
make beat      # Start Celery Beat scheduler
make scrape    # Collect agencies from PropertyFinder.ma
make match     # Match collected agencies
```

---

## 📊 Data

- **2,527** property listings imported from Yakeey
- **27,411** property images
- **39** cities across Morocco
- **87** districts, **380** neighborhoods
- Median property price: **1,490,000 MAD**
- Coverage: Casablanca (1,555), Marrakech (360), Dar Bouazza (124)

---

## 🧪 Tests

```bash
pytest
# 6 passed
```

---

## 👥 Team

Built by **Hamza** (Technical) & **Joseph** (Business)

---

## 📄 License

Private — All rights reserved © 2026 Yakeey
