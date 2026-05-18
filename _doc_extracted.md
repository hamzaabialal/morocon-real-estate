
REAL ESTATE SAAS PLATFORM
Complete Technical Build Document
Django + DRF + PostgreSQL + n8n + AI Media Generation
Version 2.0  |  Sarouty-First Architecture
May 2026  |  Hamza & Joseph
CHANGE LOG v2.0: Sarouty.ma replaces PropertyFinder cross-matching. One source = listing data + agency contacts. No matching algorithm needed.


# 1. Project Overview
This document describes the complete architecture, implementation steps, and technical decisions required to build a production-ready Real Estate SaaS platform for the Moroccan market. The platform aggregates property listings from Sarouty.ma (primary source), enriches them with financial data from the Yakeey dataset, generates automated AI media content, distributes it across social channels, and converts agency attention into paying subscriptions.


## 1.1 What We Are Building


## 1.2 Business Model



# 2. Data Strategy — Sarouty-First Architecture
KEY DECISION v2.0: Sarouty.ma is the single primary scrape source. It provides both listing data AND agency contacts in one record. Yakeey is used only for financial data enrichment. No cross-dataset matching is needed.


## 2.1 Why Sarouty.ma is the Primary Source
Joseph correctly identified that there is no shared property ID between Yakeey and Sarouty/PropertyFinder. Attempting to match them by price + area + neighborhood would produce unreliable results (~30% error rate). Sarouty.ma solves this problem entirely:


## 2.2 Revised Data Architecture — Two Roles


## 2.3 Sarouty.ma Structure
Sarouty.ma (formerly PropertyFinder.ma — redirects to sarouty.ma) is the leading agency-based portal in Morocco. Key structural facts:
- Listing URL format: sarouty.ma/property-details/?listing_id=902701
- listing_id is a sequential integer — scrapeable by range
- Agency directory: sarouty.ma/trouver-une-agence/ — lists all registered agencies
- Each listing page shows: property details, photos, agency name, phone, WhatsApp button
- Pages are partially server-rendered (some data in HTML, some loaded via API calls)
- Playwright required for full data extraction due to JS-rendered contact buttons


## 2.4 Yakeey Enrichment Strategy
Joseph's Yakeey parquet file has unique financial data not available on Sarouty. We use it to add value to our platform that competitors cannot match:

Yakeey enrichment is OPTIONAL per listing. If a Sarouty listing has no Yakeey match, we still display it — just without the fee breakdown. No data is blocked behind enrichment.


## 2.5 Yakeey-to-Sarouty Enrichment Matching
Since we no longer need to match for agency contacts, the Yakeey match is now low-stakes — it only adds financial data. We can afford to be conservative:
- Match criteria: same city + same neighborhood + same property type + area within 3% + price within 5%
- If all 5 match: apply enrichment (high confidence)
- If 4 of 5 match: apply enrichment with a flag (medium confidence — show disclaimer)
- If fewer than 4 match: do NOT enrich — leave financial fields empty
- Store enrichment_confidence (HIGH/MEDIUM/NONE) and yakeey_id on Property model
A wrong enrichment (showing incorrect fees for a different property) is worse than no enrichment. Be conservative. Only enrich on HIGH confidence matches.



# 3. Full Technology Stack



# 4. Database Schema
Below is the complete database design. Every table maps to a Django model. Schema is updated to reflect Sarouty as primary source and Yakeey as enrichment.

## 4.1 Property Model (Updated)


## 4.2 Agency Model (Updated — Now Primary Data)
Agency is now a first-class model populated directly from Sarouty scraping. Every listing has a guaranteed real agency.


## 4.3 PropertyImage


## 4.4 PropertyFeatures (OneToOne with Property)
One row per property storing all boolean amenities as BooleanFields. Fields sourced from both Sarouty scrape and Yakeey enrichment: elevator, underground_parking, outdoor_parking, terrace, balcony, garden, private_garden, pool, private_pool, gym, sauna, security_guard, intercom, gated_community, equipped_kitchen, american_kitchen, laundry_room, storage_space, concierge, janitor, fiber, air_conditioning, central_heating, electric_water_heater, gas_water_heater, fireplace, maid_room, and 20+ more.

## 4.5 Location Models


## 4.6 Analytics & Tracking


## 4.7 Scraper State Tracking


## 4.8 Subscription & Payments



# 5. Django Project Structure


## 5.1 settings.py Key Configuration
- base.py — shared settings for all environments
- development.py — DEBUG=True, local PostgreSQL, local Redis, no R2
- production.py — DEBUG=False, R2 storage, Sentry, Redis cache, strict CORS
Critical settings:
INSTALLED_APPS += [rest_framework, corsheaders, django_filters, celery, storages, drf_spectacular]
REST_FRAMEWORK: JWT default auth, CursorPagination (for large datasets), request throttling
DATABASES: PostgreSQL 16 with CONN_MAX_AGE=600 for connection pooling
CACHES: RedisCache backend, TIMEOUT=300 for listing list cache
CELERY_BROKER_URL: redis://localhost:6379/0
CELERY_RESULT_BACKEND: redis://localhost:6379/1
DEFAULT_FILE_STORAGE: storages.backends.s3boto3.S3Boto3Storage (Cloudflare R2)
AWS_S3_ENDPOINT_URL: https://<accountid>.r2.cloudflarestorage.com
CORS_ALLOWED_ORIGINS: [https://yourplatform.ma, https://www.yourplatform.ma]



# 6. Complete API Endpoints (DRF)
All endpoints follow REST conventions. Version prefix: /api/v1/. Authenticated endpoints require: Authorization: Bearer <access_token>

## 6.1 Properties API


## 6.2 Filter Parameters


## 6.3 Agency & Auth API


## 6.4 Scraper Admin API (Internal Use Only)


## 6.5 Subscriptions & Payments API


## 6.6 Location & Market Stats API



# 7. Sarouty.ma Scraper — Primary Data Source
Sarouty is now the ONLY scraper we need for complete data. One scrape gives us: property details + images + agency name + agency phone + agency WhatsApp.


## 7.1 Scraper Architecture


## 7.2 Step-by-Step Sarouty Scrape Process

### Phase A — Agency Directory Scrape (Run First, Monthly)
- Fetch sarouty.ma/trouver-une-agence/ — paginate through all pages
- For each agency card: extract name, phone, logo, profile URL, sarouty_agency_id
- Upsert into Agency model (create if new, update if existing)
- Result: complete Agency table before any listing scrape
Scraping the agency directory first means every listing we scrape later can be linked to an already-existing Agency record by name match — fast and clean.


### Phase B — Listing Discovery (Run Daily)
- Fetch listing index pages: sarouty.ma/acheter/ and sarouty.ma/louer/ paginated
- Extract all listing_id values from href attributes
- Check Redis SET sarouty:scraped_ids — skip IDs already scraped
- Add new IDs to scrape queue (Redis LIST or Celery chord)
- Log total new listings found in ScrapeJob record


### Phase C — Individual Listing Scrape
- For each listing_id in queue: fetch sarouty.ma/property-details/?listing_id={id}
- Try httpx first (fast). If contact info missing: fallback to Playwright
- Extract all fields — see Section 7.3 for full field list
- Match agency by name to existing Agency record (case-insensitive)
- If agency not found: create new Agency record with scraped data
- Save Property record with sarouty_id + agency FK
- Save PropertyImage records for each photo URL found
- Add sarouty_id to Redis SET sarouty:scraped_ids (expire after 30 days)
- Update ScrapeJob.records_scraped counter
- On error: save ScrapeError record — do not crash, continue to next listing


## 7.3 Fields to Extract from Each Sarouty Listing



# 8. Yakeey Dataset — Enrichment Pipeline
The Yakeey parquet file provided by Joseph is used to add financial data (registration fees, total acquisition cost) to matching Sarouty listings. This is a one-time import that runs after the Sarouty scrape has populated the main data.

## 8.1 Step-by-Step Yakeey Enrichment Process
- pip install pandas pyarrow ftfy
- python manage.py enrich_from_yakeey --file=Yakeey.parquet
- Command logic:
- Read parquet with pandas into DataFrame
- Fix UTF-8 encoding issues using ftfy library (Ã© → é, Ã€ → À)
- For each Yakeey row: extract city, neighborhood, property_type, area, price, priceDetails fields
- Query our DB: find Property records matching city + neighborhood + type + area(±3%) + price(±5%)
- If HIGH confidence match found: update Property with all priceDetails fields + set yakeey_id
- If MEDIUM confidence match found: update with flag enrichment_confidence=MEDIUM
- If no match: skip — do not create new records from Yakeey (Sarouty is authoritative)
- Run enrichment in batches of 200 rows with transaction.atomic()
- Log: total rows processed, HIGH matches, MEDIUM matches, unmatched, errors


## 8.2 Enrichment Fields Written to Property

Enrichment data appears on the listing page as a unique 'Full Cost Breakdown' section. This is a competitive advantage — neither Sarouty nor Yakeey shows buyers the total acquisition cost in one clear view.



# 9. Celery Background Tasks
All heavy, slow, or scheduled work runs as Celery tasks — never in the request/response cycle.



# 10. AI Media Generation Engine
Every property gets automatically generated media. This is what drives social growth without manual content creation.

## 10.1 Pipeline per New Property
- Trigger: post_save signal fires when new Property saved with status=SCRAPED
- Task: download_property_images — download all images from Sarouty CDN to R2
- Task: generate_social_caption — call GPT-4o with property details:
- Input JSON: type, area, rooms, neighborhood, city, price, features list, description
- Output JSON: caption_fr (Instagram <150 chars), caption_ar (Facebook), headline_fr, description_seo_fr, hashtags (10 tags)
- Save all to Property model fields
- Task: generate_listing_video — FFmpeg slideshow:
- Download top 5 images from R2 to temp /tmp/{property_id}/
- Apply Ken Burns effect: slow zoom + pan per image
- Overlay: neighborhood name, price (e.g. 1,600,000 DH), area (m2), rooms, brand watermark
- Add royalty-free background music track
- Output 1: 1080x1920 vertical (30s) → reel.mp4 — for Instagram/TikTok/Shorts
- Output 2: 1080x1080 square (30s) → square.mp4 — for Facebook feed
- Upload both to R2: media/videos/{property_id}/reel.mp4 and square.mp4
- Update Property.reel_url, Property.square_video_url, Property.media_generated_at
- Task: schedule_social_posts — add to platform posting queues


## 10.2 FFmpeg Command — Vertical Reel
ffmpeg -framerate 1/6 -pattern_type glob -i '/tmp/{id}/images/*.jpg' \
- vf 'zoompan=z=if(lte(zoom,1.0),1.05,max(1.001,zoom-0.0015)):
x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=180:s=1080x1920,
drawtext=text={NEIGHBORHOOD}:fontsize=52:fontcolor=white:x=60:y=1700,
drawtext=text={PRICE} DH:fontsize=48:fontcolor=yellow:x=60:y=1770' \
- c:v libx264 -t 30 -pix_fmt yuv420p -shortest output_reel.mp4


## 10.3 GPT-4o Caption Prompt
System: You are a real estate content writer for the Moroccan market. Write engaging social media captions in French and Arabic. Always include price, area, neighborhood. Keep caption_fr under 150 characters for Instagram. Include exactly 10 relevant Moroccan real estate hashtags. Respond ONLY in valid JSON with keys: caption_fr, caption_ar, headline_fr, description_seo_fr, hashtags.



# 11. Social Media Distribution System

## 11.1 Platform Strategy


## 11.2 Daily Posting Schedule (PKT Timezone)


## 11.3 APIs Required

Start with Instagram + Facebook (same Meta App) in Phase 3. Add TikTok and YouTube once Meta is working. n8n monitors posting jobs and retries failures after 1 hour.



# 12. Agency Dashboard
Agencies discover they're getting leads from our platform before they even register. The dashboard is the upsell tool — it shows them what they're missing by not being on a paid plan.

## 12.1 Agency Claim Flow
- Agency finds their listings on our platform (via social or direct search)
- They see a banner: 'This agency has 24 listings on our platform. Claim your profile to see analytics.'
- Click: goes to /claim-agency — enter phone number we already have
- OTP sent to that phone — verify identity
- Account created — agency linked to their existing scraped profile
- Free tier dashboard unlocked immediately — paid upgrade prompt shown


## 12.2 Dashboard Sections



# 13. Build Phases & Milestones

## Phase 1 — Foundation (Weeks 1-3)


## Phase 2 — Public Platform (Weeks 4-6)


## Phase 3 — Media & Social (Weeks 7-10)


## Phase 4 — Monetization (Weeks 11-14)



# 14. Deployment & Infrastructure

## 14.1 Server Setup


## 14.2 Docker Compose Services
version: '3.9'
services:
web:          # Gunicorn serving Django — port 8000
celery:       # Celery worker (scraping, media gen, social)
celery-beat:  # Celery Beat scheduler (cron jobs)
db:           # PostgreSQL 16
redis:        # Redis 7
nginx:        # Reverse proxy — port 80/443


## 14.3 GitHub Actions CI/CD
- On push to main branch: run pytest + flake8 linting
- If tests pass: SSH into Hetzner VPS
- On VPS: git pull → docker compose up --build -d
- Run: python manage.py migrate
- Run: python manage.py collectstatic --no-input
- Reload Gunicorn: kill -HUP <pid>
- Send success/failure notification to Slack or WhatsApp



# 15. Security Checklist



# 16. Joseph's Responsibilities



# 17. Monthly Cost Estimate (At Launch)

Break-even point: 1 agency at 1,500 MAD/month (~$150 USD) covers 3+ months of infrastructure. Profitable at 2 agencies. By Month 6 target of 15 paying agencies = 22,500 MAD/mo (~$2,250 USD) vs $42 infra cost.



# 18. KPIs & Success Metrics



# 19. Immediate Next Steps This Week

End of Document — Version 2.0 — May 2026  |  Sarouty-First Architecture

[TABLE 1]
Layer | What It Does
Listing Platform | Public-facing website with property search, filters, detail pages, map view
Agency Dashboard | Private portal for agencies to see analytics, manage listings, pay for promotion
Data Pipeline | Automated ingestion from Sarouty.ma (listings + agency contacts) + Yakeey parquet (enrichment)
Media Engine | AI-generated property videos, reels, captions, and social posts per listing
Distribution System | Scheduled posting to Instagram, TikTok, Facebook, YouTube Shorts
Admin Panel | Internal control panel to manage listings, users, payments, scraping jobs
REST API (DRF) | All backend logic exposed as API — consumed by frontend and mobile apps

[TABLE 2]
Revenue Stream | How It Works | Price
Free Listing | All scraped properties listed free to build inventory | Free
Priority Listing | Agency pays to appear at top of search results | 500–2,000 MAD/mo
Verified Badge | Agency pays for trust badge + contact highlight | 300 MAD/mo
Lead Notifications | Agency gets notified when someone views/calls their listing | 800 MAD/mo
Social Boost | Listing gets posted to all social channels with AI video | 200 MAD/listing
Agency Subscription | Full dashboard + analytics + all features bundled | 1,500–5,000 MAD/mo

[TABLE 3]
Data Point | Yakeey | Sarouty.ma
Property details (area, rooms, price) | YES — very rich | YES — complete
Property images | YES — Yakeey CDN | YES — Sarouty CDN
GPS coordinates | YES — precise lat/lng | YES
Agency name | NO — Yakeey staff only | YES — real agency name
Agency phone | NO — Yakeey staff only | YES — direct agency phone
Agency WhatsApp | NO | YES — often listed
Agency logo | NO | YES
Agency profile page | NO | YES — sarouty.ma/trouver-une-agence/
Registration fees breakdown | YES — priceDetails fields | NO — not exposed
Total acquisition cost | YES — calculated | NO
Sarouty listing ID (in URL) | NO | YES — ?listing_id=902701

[TABLE 4]
Source | Role | When Used | What We Extract
Sarouty.ma (scraper) | PRIMARY — listing + agency | Daily, ongoing | All listing data + agency name, phone, WhatsApp, logo, profile URL
Yakeey parquet (Joseph's file) | ENRICHMENT only | One-time + occasional refresh | Registration fees, acquisition cost, detailed financial breakdown
Sarouty Agency Directory | Agency seed data | One-time + monthly refresh | Pre-built list of all agencies before scraping individual listings

[TABLE 5]
Yakeey-Only Data | How We Use It on Platform | Buyer Value
priceDetails_registrationFees | Show exact registration cost on listing page | Buyer knows total cost upfront
priceDetails_totalPrice | Show true acquisition cost (price + all fees) | Full transparency — unique feature
priceDetails_notaryFeesWithoutTaxes | Itemized fee breakdown table | No hidden costs surprise
priceDetails_landRegistrationFees | Included in fee breakdown | Full transparency
priceDetails_acquisitionCosts | Highlight total outlay needed | Buyer can plan finances
features_ columns (50+ booleans) | Rich amenity filters + icons | Better search experience

[TABLE 6]
Category | Technology | Purpose
Backend Framework | Django 5.x + DRF | Core API, business logic, admin panel
Database | PostgreSQL 16 | Primary data store for all listings, users, analytics
Cache / Queue | Redis 7 | Caching, Celery task queue, rate limiting, scraper deduplication
Task Queue | Celery + Celery Beat | Async jobs: scraping, media gen, social posting
Search | PostgreSQL Full-Text Search (Phase 1), Elasticsearch (Phase 2) | Property search with filters
Web Scraping | Playwright + httpx + BeautifulSoup4 | Sarouty.ma scraping (JS-rendered pages)
File Storage | Cloudflare R2 (S3-compatible) | Images, videos, generated media — free egress
CDN | Cloudflare | Serve media fast globally
Automation | n8n (self-hosted, existing server) | Scraping orchestration, webhook triggers, alerts
AI Captions | OpenAI GPT-4o | Generate captions in French + Arabic
Video Generation | FFmpeg (self-hosted) | Property slideshow videos — no API cost
Frontend | Next.js 14 (separate repo) | Public listing site + agency dashboard
Auth | Django SimpleJWT | JWT-based authentication for API
Payments | Stripe | Subscription billing (international cards + links)
Email | Mailgun | Transactional emails (reuse existing RabbitFunding setup)
Hosting | Hetzner VPS (backend) + Vercel (frontend) | Cost-efficient production hosting
CI/CD | GitHub Actions | Auto-deploy on push to main
Containerization | Docker + Docker Compose | Consistent local and prod environments
Monitoring | Sentry + UptimeRobot | Error tracking and uptime alerts

[TABLE 7]
Field | Type | Description
id | UUID (PK) | Primary key, auto-generated
sarouty_id | IntegerField unique | Sarouty listing_id from URL e.g. 902701 — PRIMARY source ID
yakeey_id | CharField(20) nullable | Yakeey ID e.g. CA008888 — only set if enrichment match found
enrichment_confidence | CharField | HIGH / MEDIUM / NONE — confidence of Yakeey match
listing_type | CharField | SALE or RENT
property_type | CharField | FLAT, TERRAIN, COMMERCIAL, VILLA, RIAD, PENTHOUSE, DUPLEX
status | CharField | LISTED, SOLD, RENTED, ARCHIVED
price | DecimalField | Price in MAD
currency | CharField(5) | DH default
area | DecimalField | Total area in m2
living_area | DecimalField nullable | Habitable area in m2
rooms | IntegerField | Number of bedrooms
bathrooms | IntegerField | Number of bathrooms
floor | IntegerField nullable | Unit floor number
total_floors | IntegerField nullable | Total floors in building
construction_year | IntegerField nullable | Year built
furnished | BooleanField | Is furnished
is_new | BooleanField | New construction project
description | TextField | Full description text (French/Arabic)
general_state | CharField | GOOD, FAIR, TO_BE_RENOVATED, NEW
latitude | DecimalField(9,6) | GPS latitude
longitude | DecimalField(9,6) | GPS longitude
city | ForeignKey -> City | City reference
district | ForeignKey -> District nullable | District reference
neighborhood | ForeignKey -> Neighborhood nullable | Neighborhood reference
main_address | CharField | Street address text
agency | ForeignKey -> Agency | Owning agency — scraped from Sarouty listing page
source_url | URLField | Original Sarouty listing URL
is_featured | BooleanField default False | Priority listing (paid upgrade)
is_verified | BooleanField default False | Agency claimed and verified listing
views_count | IntegerField default 0 | Page view counter (denormalized for speed)
registration_fees | DecimalField nullable | From Yakeey enrichment only
land_registration_fees | DecimalField nullable | From Yakeey enrichment only
notary_fees | DecimalField nullable | From Yakeey enrichment only
total_acquisition_cost | DecimalField nullable | Full buyer cost — from Yakeey enrichment
scrape_status | CharField | PENDING, SCRAPED, ENRICHED, FAILED
last_scraped_at | DateTimeField nullable | Last time we re-scraped this listing
created_at | DateTimeField auto_now_add | Record creation timestamp
updated_at | DateTimeField auto_now | Last update timestamp

[TABLE 8]
Field | Type | Description
id | UUID (PK) | Primary key
sarouty_agency_id | CharField nullable | Agency ID from Sarouty directory
sarouty_profile_url | URLField nullable | Agency profile URL on Sarouty
name | CharField(200) | Agency name — scraped from Sarouty
phone | CharField(20) | Primary contact phone — scraped from Sarouty
whatsapp | CharField(20) nullable | WhatsApp number — scraped from Sarouty
email | EmailField nullable | Agency email if visible on Sarouty
website | URLField nullable | Agency website
logo_url | URLField nullable | Agency logo from Sarouty
city | ForeignKey -> City | Primary city of operation
total_listings | IntegerField default 0 | Count of listings on our platform
is_claimed | BooleanField default False | Agency has registered on our platform
is_verified | BooleanField default False | Identity verified
subscription_plan | ForeignKey -> SubscriptionPlan nullable | Active paid plan
subscription_expires_at | DateTimeField nullable | Plan expiry
platform_user | OneToOneField -> User nullable | If agency has logged into dashboard
created_at | DateTimeField auto_now_add | When we first scraped this agency
updated_at | DateTimeField auto_now | Last scrape refresh

[TABLE 9]
Field | Type | Description
id | UUID (PK) | Primary key
property | ForeignKey -> Property | Parent property
original_url | URLField | Source URL from Sarouty CDN
r2_key | CharField nullable | Our Cloudflare R2 storage key after download
r2_url | URLField nullable | Our CDN URL for the image
order | IntegerField default 0 | Display order
is_main | BooleanField default False | Is the cover/hero image
created_at | DateTimeField auto_now_add | Upload timestamp

[TABLE 10]
Model | Fields | Notes
Country | id, name, code (MA) | Morocco only initially
City | id, name, country, latitude, longitude, slug | Casablanca, Rabat, Marrakech, Tanger...
District | id, name, city, slug | Maarif, Gauthier, Ain Sebaa...
Neighborhood | id, name, district, slug, latitude, longitude | Finest granularity for map search

[TABLE 11]
Model | Key Fields | Purpose
PropertyView | property, ip_address, user_agent, referrer, created_at | Track every listing page view
PropertyClick | property, click_type (call/whatsapp/email), agency, created_at | Track contact button clicks
AgencyAnalyticsSummary | agency, date, views, clicks, leads, top_property_id | Daily aggregated stats for dashboard
SocialPost | property, platform, post_url, posted_at, likes, shares, views | Track social media performance
LeadEvent | property, agency, phone_hash, source, created_at | Inbound lead tracking (phone hashed for privacy)

[TABLE 12]
Model | Key Fields | Purpose
ScrapeJob | id, source (sarouty/yakeey), status, started_at, finished_at, records_scraped, errors_count | Track each scrape run
ScrapeError | job, listing_id, url, error_message, created_at | Log individual scrape failures for retry
AgencyScrapeRecord | agency, last_scraped_at, listings_found, scrape_job | Track per-agency scrape history

[TABLE 13]
Model | Key Fields | Purpose
SubscriptionPlan | id, name, price_monthly, features (JSON), max_listings, has_analytics, has_social_boost | Plan definitions
AgencySubscription | agency, plan, status, started_at, expires_at, stripe_sub_id | Active subscriptions
Payment | agency, amount, currency, status, gateway, gateway_payment_id, created_at | Payment records

[TABLE 14]
App / Directory | Responsibility
config/ | settings.py, urls.py, wsgi.py, asgi.py — project config + env loading
apps/properties/ | Property + PropertyImage + PropertyFeatures models, serializers, viewsets, filters
apps/agencies/ | Agency model, User model, auth endpoints, agency profile management
apps/locations/ | Country, City, District, Neighborhood models + slug generation
apps/analytics/ | View/click tracking endpoints, aggregation tasks, dashboard data endpoints
apps/media_engine/ | FFmpeg video generation, GPT-4 caption generation, R2 upload tasks
apps/social/ | Instagram, Facebook, TikTok posting logic, scheduling, performance sync
apps/subscriptions/ | Plans, billing, Stripe webhook handlers, feature permission gating
apps/scraper/ | Sarouty scraper (primary), Yakeey parquet importer (enrichment), state tracking
apps/notifications/ | Email via Mailgun, WhatsApp via Twilio or direct link, push notifications
apps/admin_panel/ | Custom Django admin views, bulk operations, scrape job monitoring
common/ | Shared utilities: pagination, permissions, mixins, validators, throttling
celery_app.py | Celery app config, task routing, beat schedule

[TABLE 15]
Method | Endpoint | Auth | Description
GET | /api/v1/properties/ | Public | List properties — paginated, filterable, sortable
GET | /api/v1/properties/{id}/ | Public | Full property detail with agency, images, features, fees
GET | /api/v1/properties/search/ | Public | Full-text search across title, description, address
GET | /api/v1/properties/featured/ | Public | Priority-listed properties (paid placements)
GET | /api/v1/properties/similar/{id}/ | Public | Similar properties by neighborhood + type
GET | /api/v1/properties/map/ | Public | Lightweight list for map pins (id, lat, lng, price, type only)
POST | /api/v1/properties/ | Agency | Manually create listing (for self-listed properties)
PATCH | /api/v1/properties/{id}/ | Agency/Admin | Update own listing
DELETE | /api/v1/properties/{id}/ | Admin | Soft-delete (sets status=ARCHIVED)
POST | /api/v1/properties/{id}/view/ | Public | Record page view event
POST | /api/v1/properties/{id}/click/ | Public | Record contact click (call/whatsapp/email)
POST | /api/v1/properties/{id}/boost/ | Agency | Purchase social media boost for this listing

[TABLE 16]
Parameter | Type | Example
city | String (slug) | ?city=casablanca
district | String (slug) | ?district=maarif
neighborhood | String (slug) | ?neighborhood=gauthier
listing_type | SALE or RENT | ?listing_type=SALE
property_type | String | ?property_type=FLAT
price_min / price_max | Integer (MAD) | ?price_min=500000&price_max=2000000
area_min / area_max | Integer (m2) | ?area_min=80&area_max=200
rooms | Integer | ?rooms=3
furnished | Boolean | ?furnished=true
is_new | Boolean | ?is_new=true
features | Comma-separated | ?features=elevator,pool,parking
has_fees_data | Boolean | ?has_fees_data=true (Yakeey-enriched only)
ordering | Field name | ?ordering=-price or ?ordering=area
is_featured | Boolean | ?is_featured=true
bbox | 4 floats (lon1,lat1,lon2,lat2) | ?bbox=-7.7,33.5,-7.5,33.7 (map bounds)
agency | UUID | ?agency=<agency_id> (all listings by agency)

[TABLE 17]
Method | Endpoint | Auth | Description
POST | /api/v1/auth/register/ | Public | Agency self-registration (claim their scraped agency profile)
POST | /api/v1/auth/login/ | Public | Get JWT access + refresh tokens
POST | /api/v1/auth/refresh/ | Public | Refresh JWT using refresh token
POST | /api/v1/auth/logout/ | Auth | Blacklist refresh token
POST | /api/v1/auth/claim-agency/ | Auth | Link registered user to existing scraped agency
GET | /api/v1/agencies/ | Public | List all agencies with listing counts
GET | /api/v1/agencies/{id}/ | Public | Agency public profile + listings
GET | /api/v1/agencies/me/ | Agency | Current agency full profile
PATCH | /api/v1/agencies/me/ | Agency | Update agency profile (override scraped data)
GET | /api/v1/agencies/me/analytics/ | Agency | Dashboard analytics: views, clicks, leads
GET | /api/v1/agencies/me/analytics/social/ | Agency | Social media performance per post
GET | /api/v1/agencies/me/leads/ | Agency | Inbound leads list with masked phone
GET | /api/v1/agencies/me/listings/ | Agency | All agency listings with per-listing stats

[TABLE 18]
Method | Endpoint | Auth | Description
POST | /api/v1/admin/scrape/sarouty/start/ | Admin | Trigger new Sarouty scrape job
POST | /api/v1/admin/scrape/yakeey/enrich/ | Admin | Run Yakeey enrichment pass on existing properties
GET | /api/v1/admin/scrape/jobs/ | Admin | List scrape jobs with status and stats
GET | /api/v1/admin/scrape/errors/ | Admin | List failed scrape records for retry
POST | /api/v1/admin/scrape/retry/{job_id}/ | Admin | Retry all failed records in a job

[TABLE 19]
Method | Endpoint | Auth | Description
GET | /api/v1/subscriptions/plans/ | Public | List all available subscription plans + features
POST | /api/v1/subscriptions/subscribe/ | Agency | Create Stripe checkout session
POST | /api/v1/subscriptions/cancel/ | Agency | Cancel current subscription (active until period end)
GET | /api/v1/subscriptions/status/ | Agency | Current plan, expiry, usage vs limits
POST | /api/v1/webhooks/stripe/ | Stripe | Stripe payment webhook handler

[TABLE 20]
Method | Endpoint | Auth | Description
GET | /api/v1/locations/cities/ | Public | All cities with property counts + avg price
GET | /api/v1/locations/districts/ | Public | Districts filtered by ?city=
GET | /api/v1/locations/neighborhoods/ | Public | Neighborhoods filtered by ?district=
GET | /api/v1/stats/market/ | Public | Avg price per m2 by city + type — market overview
GET | /api/v1/stats/agency/{id}/ | Public | Public-facing agency stats

[TABLE 21]
Component | Technology | Role
Scheduler | n8n Cron (daily 2 AM PKT) | Triggers scrape job via webhook to Django
HTTP Client | httpx (fast requests) | Fetch static HTML listing pages
JS Renderer | Playwright (headless Chromium) | For pages where contact info loads via JS
Parser | BeautifulSoup4 | Extract structured data from HTML
Rate Limiter | Redis token bucket | Max 1 request per 3 seconds — avoid IP ban
Deduplication | Redis SET of sarouty_ids | Skip listings already scraped today
State Tracking | ScrapeJob + ScrapeError models | Full audit log of every scrape run
Storage | Django management command | Save results directly to DB via Django ORM
Proxy Rotation | Optional Phase 2 | Rotating proxies if Sarouty blocks our VPS IP

[TABLE 22]
Field | Location on Page | Maps to Model
listing_id | URL parameter | Property.sarouty_id
Price (MAD) | Price heading | Property.price
Property type | Type badge/breadcrumb | Property.property_type
Transaction type | Sale/Rent indicator | Property.listing_type
Area (m2) | Details section | Property.area
Rooms | Details section | Property.rooms
Bathrooms | Details section | Property.bathrooms
Floor / Total floors | Details section | Property.floor / total_floors
Construction year | Details section | Property.construction_year
Furnished | Details section | Property.furnished
City + Neighborhood | Breadcrumb / location tag | Property.city + neighborhood
Full address text | Location section | Property.main_address
GPS coordinates | Meta tags or Google Maps embed | Property.latitude + longitude
Description text | Description section | Property.description
Amenities/features | Feature icons list | PropertyFeatures booleans
All photo URLs | Image gallery | PropertyImage records
Agency name | Agency card on listing | Agency.name (match + link)
Agency phone | Call button / visible number | Agency.phone
Agency WhatsApp | WhatsApp button href | Agency.whatsapp
Agency logo URL | Agency card image | Agency.logo_url
Agency profile URL | Agency card link | Agency.sarouty_profile_url

[TABLE 23]
Yakeey Field | Property Model Field | Displayed As
priceDetails_sellerPrice | registration_fees (stored as note) | Seller's net price
priceDetails_registrationFees | registration_fees | Registration fees
priceDetails_landRegistrationFees | land_registration_fees | Land registration fees
priceDetails_notaryFeesWithoutTaxes | notary_fees | Notary fees (excl. VAT)
priceDetails_totalPrice | total_acquisition_cost | Total buyer cost (all fees included)
priceDetails_clientYakeeyFees | stored in JSON extras field | Platform fees (for reference)

[TABLE 24]
Task Name | Trigger | What It Does
run_sarouty_agency_scrape | Monthly cron (1st of month, 1 AM) | Scrape sarouty.ma/trouver-une-agence/ — rebuild Agency table
run_sarouty_listing_discovery | Daily cron 2 AM | Find new listing IDs not yet in our DB
scrape_sarouty_listing | Per listing, chained from discovery | Scrape individual listing — extract all fields + agency
run_yakeey_enrichment | Manual / after major Yakeey file update | Match Yakeey rows to existing properties, write fee data
generate_listing_video | On new property saved (post_save signal) | FFmpeg video from property images
generate_social_caption | On new property saved | GPT-4o generates FR + AR captions + hashtags
download_property_images | On new property saved | Download images from Sarouty CDN → upload to R2
schedule_social_posts | Daily 9 AM | Queue today's social posts across all platforms
post_to_instagram | Per listing, staggered | Post reel + caption to Instagram via Meta Graph API
post_to_facebook | Per listing, staggered | Post video to Facebook page
post_to_tiktok | Per listing, staggered | Post video to TikTok
sync_social_performance | Daily midnight | Fetch likes/views from each platform API → update SocialPost
aggregate_daily_analytics | Daily midnight | Compute AgencyAnalyticsSummary for each agency
send_lead_notification | On PropertyClick event | Email agency: someone clicked call/WhatsApp on their listing
sync_subscription_status | Hourly | Check Stripe for subscription changes, update DB
send_weekly_agency_report | Every Monday 8 AM | Email each agency: views, clicks, leads this week
refresh_stale_listings | Weekly Sunday 3 AM | Re-scrape listings older than 30 days to check if still active
cleanup_old_analytics | Monthly 1st | Archive raw analytics older than 12 months

[TABLE 25]
Platform | Format | Frequency | Best Content
Instagram | Reels (vertical 30s) + Carousels | 3x per day | Luxury listings, prime neighborhoods, price reveals
Facebook | Video + photo album post | 2x per day | Detailed listing with full description + agency contact
TikTok | Short vertical 15-30s | 2x per day | Fast property tour, price comparison, neighborhood tips
YouTube Shorts | Vertical 60s | 1x per day | Property walkthrough with narration
YouTube Long | Neighborhood guide 5-10min | Weekly | Phase 2 — build SEO authority

[TABLE 26]
Time (PKT) | Time (Morocco) | Platform | Content
11:00 AM | 8:00 AM | Instagram | Morning listing reel
12:00 PM | 9:00 AM | Facebook | Detailed listing post
1:00 PM | 10:00 AM | TikTok | Property tour video
4:00 PM | 1:00 PM | Instagram | Neighborhood highlight
6:00 PM | 3:00 PM | YouTube Shorts | Property walkthrough
8:00 PM | 5:00 PM | Facebook | Evening listing post
9:00 PM | 6:00 PM | TikTok | Market insight video
10:00 PM | 7:00 PM | Instagram | Evening listing reel

[TABLE 27]
Platform | API Needed | Approval Difficulty | Timeline
Instagram | Meta Graph API v18 — Reels publishing | Medium — need Meta Business verification | 1-2 weeks
Facebook | Meta Graph API v18 — Page posts | Same Meta App as Instagram | Same as above
TikTok | TikTok Content Posting API | Hard — need developer approval | 2-4 weeks
YouTube | YouTube Data API v3 — videos.insert | Easy — Google Cloud project + OAuth | 1-3 days

[TABLE 28]
Section | Free Tier | Paid Tier
Overview stats | Views this month (blurred after 5) | Full views, clicks, leads with trends
Listings list | See own listings, basic info | Per-listing view + click counts, days on market
Analytics charts | Locked — upgrade prompt | 30-day view history, traffic sources, peak times
Leads | Locked — see count only | Full lead list with masked phone, source, property
Social performance | Locked | Views/likes per post, best performing listings
Promote listings | Available — pay per boost | Discounted boosts + bulk scheduling
Subscription | Upgrade prompt | Current plan, renewal date, invoice history
Profile settings | Edit name, phone, logo | Full profile + WhatsApp + website

[TABLE 29]
Task | Owner | Output
GitHub repo setup + Django project + Docker Compose | Hamza | Local dev environment running
All models created + migrations run | Hamza | Full DB schema live
Sarouty agency directory scraper (Phase A) | Hamza | Agency table populated
Sarouty listing scraper (Phase B + C) | Hamza | 1,000+ listings in DB with agency contacts
Yakeey parquet enrichment command | Hamza | Fee data added where matched
DRF serializers + viewsets for properties, agencies, locations | Hamza | API returning JSON
JWT auth endpoints (register, login, claim-agency) | Hamza | Auth system working
Django admin configured for scrape monitoring | Hamza | Admin panel usable
Deploy to Hetzner VPS with Nginx + Gunicorn + SSL | Hamza | Live staging URL
Joseph shares final Yakeey parquet file | Joseph | Enrichment data available
Create Instagram + Facebook business accounts | Joseph | Accounts ready for API

[TABLE 30]
Task | Owner | Output
Next.js frontend: homepage + search + filters + results | Hamza | Public website live
Property detail page: images, map, features, fee breakdown, agency card | Hamza | Full listing page live
Agency public profile page | Hamza | Agency pages live
Analytics tracking: view + click events stored | Hamza | Event tracking working
Celery + Redis setup with all Phase 1 tasks running | Hamza | Background jobs active
Image download pipeline: Sarouty CDN → R2 | Hamza | Images served from our CDN
Daily re-scrape task for stale listings | Hamza | Listings stay fresh
Joseph: review platform, give feedback on UI | Joseph | Design iteration feedback

[TABLE 31]
Task | Owner | Output
FFmpeg video generation pipeline (all new listings) | Hamza | Videos auto-created per listing
GPT-4o caption generation (FR + AR) | Hamza | Captions auto-generated
R2 storage for all videos + updated CDN URLs in DB | Hamza | Videos served fast
Meta Graph API: Instagram Reels auto-posting | Hamza | Instagram posts going live daily
Meta Graph API: Facebook video posts | Hamza | Facebook posts going live
Social post schedule system with time-staggering | Hamza | Daily posting queue working
n8n: monitor social post failures + retry webhook | Hamza | Automated failure recovery
Joseph: monitor social accounts, engage with comments | Joseph | Community building
YouTube Data API: Shorts upload | Hamza | YouTube channel growing

[TABLE 32]
Task | Owner | Output
Agency claim flow + OTP verification | Hamza | Agencies can self-onboard
Dashboard with free vs paid feature gating | Hamza | Freemium model live
Stripe subscription integration | Hamza | Payments working
Lead notification system (email + WhatsApp message) | Hamza | Agencies get lead alerts
Paid listing boost purchase flow | Hamza | Per-listing payments working
Weekly analytics email to all agencies (free + paid) | Hamza | Retention + upgrade driver
Joseph: contact first 20 agencies shown on platform | Joseph | First beta agency conversations
Joseph: convert 3 agencies to paid beta | Joseph | First MAD revenue
Production hardening: rate limits, security headers, backups | Hamza | Production-ready

[TABLE 33]
Component | Spec / Tool | Notes
VPS | Hetzner CX32 (4 vCPU, 8GB RAM) — ~15 EUR/mo | Same provider as existing workflow.hostyo.com
OS | Ubuntu 24.04 LTS | Standard LTS choice
Web Server | Nginx (reverse proxy + static files) | SSL termination, gzip, rate limiting
App Server | Gunicorn with 4 workers | Django WSGI server
Process Manager | Supervisor | Keeps Gunicorn + Celery + Celery Beat alive
SSL | Let's Encrypt via Certbot | Free HTTPS certificate, auto-renews
Database | PostgreSQL 16 on same VPS (Phase 1) | Move to Hetzner managed DB when revenue allows
Cache + Queue | Redis 7 on same VPS | Celery broker + Django cache
Media Storage | Cloudflare R2 | S3-compatible, free egress, cheap storage
Frontend Hosting | Vercel (free tier) | Next.js with automatic CDN
n8n | Reuse existing workflow.hostyo.com | Scrape scheduling + failure alerts
Monitoring | Sentry (errors) + UptimeRobot (uptime ping) | Free tiers sufficient
Backups | Hetzner snapshot + pg_dump to R2 daily | 30-day retention

[TABLE 34]
Item | Implementation
SECRET_KEY | Stored in .env only, never in code, 50+ char random string
DEBUG=False in production | Environment variable, default False — never hardcode
ALLOWED_HOSTS | Explicit domain list only — never use '*'
HTTPS only | Nginx: redirect all HTTP → HTTPS permanently
JWT expiry | Access token: 15 minutes, Refresh token: 7 days with rotation
API rate limiting | DRF throttling: public 100/hour, authenticated 1000/hour
Scraper rate limiting | Redis token bucket: max 1 request per 3 seconds to Sarouty
SQL injection | Django ORM prevents — never use raw SQL or string formatting in queries
CORS | Only allow production frontend domain — never '*'
Phone number privacy | Store hashed phone in LeadEvent — show masked version in dashboard
File upload validation | MIME type check + max 5MB — reject non-image files
Admin URL | Change /admin/ to custom secret path e.g. /manage-x7k2/
Scraper User-Agent | Use realistic browser user-agent string — rotate occasionally
Environment variables | All secrets in .env, loaded with python-decouple
Database backups | Automated daily pg_dump → R2 bucket with 30-day retention
Dependency audit | pip audit run weekly in CI pipeline — fail on critical vulnerabilities

[TABLE 35]
Task | When | Deliverable
Send complete Yakeey parquet file to Hamza | Week 1 | File transferred
Define target city priority: which city first? | Week 1 | City list in priority order
Create Instagram Business account for platform | Week 2 | Account live, connected to Meta Business
Create Facebook Business Page for platform | Week 2 | Page live, ready for API
Create TikTok account for platform | Week 3 | Account created
Choose and register domain name (.ma or .com) | Week 1 | Domain registered
Review homepage + listing page mockup from Hamza | Week 2 | Feedback within 48 hours
Manually browse Sarouty.ma — confirm which data is visible | Week 1 | Screenshot list of visible fields
Identify top 5 neighborhoods in Casablanca worth targeting first | Week 2 | Neighborhood list with rationale
Define content angles for social posts (luxury? affordable? new builds?) | Week 3 | Content strategy note
Start UK Ltd registration via 1st Formations | Week 4 | Company registration submitted
Contact first 10 agencies shown on platform — inform them they're listed | Week 8 | Agency response log
Convert 3 agencies to paid beta plan (target: 1,500 MAD/mo each) | Week 12 | First revenue: 4,500 MAD/mo
Handle all French/Arabic client-facing communication | Ongoing | Agency relationships managed
Report market feedback weekly: what agencies want, pain points | Ongoing | Weekly voice note or message to Hamza

[TABLE 36]
Service | Cost/Month (USD) | Notes
Hetzner CX32 VPS | ~$15 | Django + PostgreSQL + Redis + Celery + n8n reuse
Cloudflare R2 Storage | ~$5 | 10GB images/videos free, $0.015/GB after
OpenAI API (GPT-4o) | ~$15 | ~1,500 caption generations per month
Mailgun (email) | ~$5 | 1,000/month free — weekly reports + lead alerts
Domain name (.ma) | ~$2 | ~$24/year for .ma domain
Vercel (Next.js frontend) | $0 | Free hobby tier sufficient for Phase 1-2
SSL Certificate | $0 | Let's Encrypt is completely free
UptimeRobot monitoring | $0 | Free tier — 50 monitors
Sentry error tracking | $0 | Free tier — 5,000 errors/month
GitHub Actions CI/CD | $0 | Free tier — 2,000 mins/month
Playwright (self-hosted) | $0 | Runs on same VPS — no API cost
FFmpeg (self-hosted) | $0 | Runs on same VPS — no API cost
TOTAL | ~$42/month | Extremely lean startup cost

[TABLE 37]
Metric | Month 1 | Month 3 | Month 6
Sarouty listings scraped | 5,000+ | 15,000+ | 30,000+
Agencies in DB (with contacts) | 500+ | 1,000+ | 2,000+
Yakeey enrichment coverage | 30% of listings | 50% | 60%
Daily social posts published | 5 | 10 | 15+
Total social followers (all platforms) | 300 | 3,000 | 15,000
Monthly website visitors | 1,000 | 15,000 | 75,000
Agencies contacted by Joseph | 10 | 75 | 200
Agencies that claimed profile (free) | 2 | 20 | 80
Paying agency subscriptions | 0 | 3 | 15
Monthly Recurring Revenue (MAD) | 0 | 4,500 | 22,500
Avg listing views per day | 50 | 500 | 3,000

[TABLE 38]
# | Action | Owner | Deadline
1 | Joseph sends Yakeey parquet file to Hamza | Joseph | Day 1 — Today
2 | Agree on platform domain name | Both | Day 1 — Today
3 | Hamza creates GitHub repo + Django project skeleton + Docker Compose | Hamza | Day 2
4 | Hamza builds all database models + migrations | Hamza | Day 3
5 | Hamza builds Sarouty agency directory scraper + test run | Hamza | Day 4
6 | Hamza builds Sarouty listing scraper — test on 100 listings | Hamza | Day 5
7 | Hamza runs Yakeey enrichment on scraped listings + report match rate | Hamza | Day 5
8 | Joseph: manually verify 5 scraped listings — confirm data accuracy | Joseph | Day 5
9 | Joseph: create Instagram + Facebook Business accounts | Joseph | Day 3
10 | Joseph: browse Sarouty.ma — confirm agency phone is visible on listings | Joseph | Day 2
11 | Both: weekly sync call every Monday 10 AM PKT / 8 AM Morocco | Both | Schedule today