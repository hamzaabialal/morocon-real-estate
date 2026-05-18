# Yakeey — How the product actually works

A working walkthrough of every flow in the system, mapped to the real code that runs it.
This is the operator's manual, not a marketing doc.

---

## 1. The 30-second story

Yakeey is a SaaS for Moroccan real estate agencies. Every night a scraper pulls listings from Sarouty / PropertyFinder, every new listing gets AI-generated French + Arabic captions and short video reels, and the videos get auto-posted to Instagram / Facebook / TikTok / YouTube Shorts at 10am/1pm/5pm. Buyers tap call or WhatsApp on a listing → a `LeadEvent` fires → the agency sees it in their dashboard and pays a Stripe subscription to unlock full lead history + listing boosts.

---

## 2. End-to-end data flow

```
                       ┌──────────────────────────────┐
                       │  3am — Celery beat (daily)   │
                       │  scrape_propertyfinder       │
                       │  (currently a placeholder)   │
                       └──────────────┬───────────────┘
                                      │
                                      ▼
              ┌─────────────────────────────────────────┐
              │   apps/scraper/services/                │
              │   PropertyFinderCollector               │
              │   → httpx + BeautifulSoup (Playwright   │
              │     fallback for JS pages)              │
              │   → writes CollectedAgency, Property    │
              └──────────────┬──────────────────────────┘
                             │
                             ▼  (post_save signal)
              ┌─────────────────────────────────────────┐
              │   celery_tasks.media.                   │
              │   generate_media_for_property(id)       │
              │   ┌─────────────────────────────────┐   │
              │   │ 1. caption_generator.py         │   │
              │   │    OpenAI GPT-4 → JSON          │   │
              │   │    {caption_fr, caption_ar,     │   │
              │   │     hashtags, headline}         │   │
              │   ├─────────────────────────────────┤   │
              │   │ 2. video_generator.py           │   │
              │   │    FFmpeg + Ken Burns →         │   │
              │   │    reel_1080x1920.mp4 +         │   │
              │   │    square_1080x1080.mp4         │   │
              │   ├─────────────────────────────────┤   │
              │   │ 3. storage.upload_media_to_s3   │   │
              │   │    → Cloudflare R2              │   │
              │   ├─────────────────────────────────┤   │
              │   │ 4. media_status = "ready"       │   │
              │   └─────────────────────────────────┘   │
              └──────────────┬──────────────────────────┘
                             │
                             ▼
                  ┌─────────────────────────┐
                  │  9am — Celery beat      │
                  │  schedule_social_posts  │
                  │  picks top 3 ready      │
                  │  properties by views    │
                  │  → 3 SocialPost rows    │
                  │     at 10am/1pm/5pm     │
                  └────────────┬────────────┘
                               │
                               ▼  (Celery ETA)
              ┌─────────────────────────────────────────┐
              │  post_property_to_platform(post_id)     │
              │  → post_to_instagram()                  │
              │  → post_to_facebook()                   │
              │  → TikTok / YouTube: NotImplementedError│
              └─────────────────────────────────────────┘
                               │
                               ▼
              ┌─────────────────────────────────────────┐
              │  Public buyer → /properties → click     │
              │  call / WhatsApp on detail page →       │
              │  PropertyClick + LeadEvent rows         │
              └──────────────┬──────────────────────────┘
                             │
                             ▼
              ┌─────────────────────────────────────────┐
              │  Agency dashboard (/dashboard/leads):   │
              │  sees masked-phone lead row             │
              │  + optional WhatsApp/email push         │
              │  (notifications app empty for now)      │
              └─────────────────────────────────────────┘
```

---

## 3. Daily clockwork (the Celery beat schedule)

Defined in [celery_app.py:28-45](celery_app.py).

| Time (Africa/Casablanca) | Task | What it does |
|---|---|---|
| **00:00** | `aggregate_daily_analytics` | Precomputes the `AgencyAnalyticsSummary` rows. **Status:** stub — analytics are still computed on-demand by the API. |
| **03:00** | `scrape_propertyfinder` | Runs nightly scrape. **Status:** placeholder returning `{"status": "disabled_placeholder"}`. Gate flag: `CELERY_SCRAPE_PROPERTYFINDER_ENABLED` in `.env`. |
| **09:00** | `schedule_social_posts` | Selects top 3 properties with `media_status="ready"` that haven't been posted today, creates `SocialPost` rows scheduled at 10am/1pm/5pm. **Status:** implemented, see [celery_tasks/social.py:17-45](celery_tasks/social.py). |
| **10:00, 13:00, 17:00** | `post_property_to_platform` (ETA-fired per row) | Calls Meta Graph API to publish the reel. **Status:** Instagram + Facebook work; TikTok + YouTube raise `NotImplementedError`. |

**On-demand (not on schedule):**
- `generate_media_for_property(id)` — fires when a property is created or queued
- `generate_media_batch(limit=50)` — bulk queue, called via `python manage.py generate_media`

---

## 4. Three ways a property enters the system

### Path A — Agent self-submits (works today, end-to-end)

1. Agent signs in at `/login`, hits `/dashboard/listings`, clicks **+ New listing**.
2. Fills the modal: reference code, transaction (Sale/Rent), category (Villa/Riad/etc.), city, price, area, beds/baths, optional cover image URL, description.
3. JS submits to `POST /api/v1/properties/` with the form payload. The view's `perform_create` auto-binds the row to `request.user.agency` ([apps/properties/views.py:58-63](apps/properties/views.py)).
4. Backend returns the created `Property` with a UUID.
5. The dashboard listings table refreshes; the property is immediately visible at `/properties/<uuid>`.

**What's NOT yet wired:** the `post_save` signal that should auto-queue `generate_media_for_property`. Right now manually-created listings don't get AI media unless you run `python manage.py generate_media` or call the Celery task by hand. Hooking up the signal is a one-liner.

### Path B — Nightly scrape from Sarouty / PropertyFinder

1. 3am Celery beat fires `celery_tasks.scraper.scrape_propertyfinder`.
2. The task should call `apps.scraper.services.PropertyFinderCollector` which:
   - Visits Sarouty agency pages with httpx + a random user-agent, 2-5s delay
   - Falls back to Playwright for JS-rendered detail pages
   - Parses with BeautifulSoup, writes `CollectedAgency` + `Property` rows
   - Logs the run in `CollectionRun` with pages_visited / agencies_found counters
3. Each new `Property` would trigger the same media pipeline as Path A.

**Status:** collector class is built; the Celery task is a placeholder. Flipping it on means:
- replace the stub in [celery_tasks/scraper.py](celery_tasks/scraper.py)
- set `CELERY_SCRAPE_PROPERTYFINDER_ENABLED=True` in `.env`
- run a Celery worker + beat

### Path C — Yakeey Parquet bulk import (one-time / occasional)

The doc references a Yakeey dataset (Parquet files) used as enrichment for matched listings — adds `registration_fees`, `total_acquisition_cost`, etc. A bulk import script would read the Parquet, match rows to existing `Property` records by city+neighborhood+type+area±3%+price±5%, and update them. This isn't wired in the codebase yet — would live as a `manage.py` command.

---

## 5. What happens after a property is created (the AI media pipeline)

[celery_tasks/media.py:18-67](celery_tasks/media.py) runs once per property:

```python
property.media_status = "generating"
# Step 1 — captions
captions = generate_captions(property)  # OpenAI GPT-4, returns {caption_fr, caption_ar, hashtags}
# Step 2 — videos
reel_path, square_path = generate_property_video(property)  # FFmpeg, Ken Burns
# Step 3 — upload
property.reel_url = upload_media_to_s3(reel_path, property.id, "reel.mp4")
property.square_video_url = upload_media_to_s3(square_path, property.id, "square.mp4")
property.media_status = "ready"
property.media_generated_at = now()
```

If any step throws, `media_status` is flipped to `"failed"` and the temp dir is cleaned up. `OPENAI_API_KEY` and `AWS_*` settings need to be filled in `.env` for this to actually work — without them, captions degrade gracefully (empty) and S3 upload fails.

---

## 6. The social posting cadence

Each agency gets up to 3 posts per day, one per scheduled slot.

```
9:00am  beat:  schedule_social_posts
              └─ picks top 3 ready properties by view_count
              └─ creates 3 SocialPost rows (status="scheduled"):
                  - prop A → scheduled_at = today 10:00
                  - prop B → scheduled_at = today 13:00
                  - prop C → scheduled_at = today 17:00
              └─ each enqueues post_property_to_platform with eta=scheduled_at

10:00   worker: post_property_to_platform(A)
              ├─ builds caption (caption_fr + hashtags joined)
              ├─ calls post_to_instagram() → Meta Graph API v18.0:
              │   1. create reel container with video_url + caption
              │   2. POST /{ig_account_id}/media_publish to publish
              │   3. fetch permalink
              ├─ on success: status="posted", post_url=permalink, posted_at=now()
              └─ on error: status="failed", error_message=str(exc)
13:00   worker: post_property_to_platform(B)   # same as above
17:00   worker: post_property_to_platform(C)   # same as above
```

Instagram + Facebook implementations live at [apps/social/instagram.py](apps/social/instagram.py) and [apps/social/facebook.py](apps/social/facebook.py). TikTok and YouTube currently raise `NotImplementedError` inside `post_property_to_platform` — adding them means writing two files following the same shape: take `(property, video_url, caption)`, return a `post_url` string.

Required `.env` keys for social to work: `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN`.

---

## 7. Buyer journey (no auth needed)

```
1. Buyer lands on /properties (or arrives via social → /properties/<uuid>)

2. /properties grid:
   - JS calls GET /api/v1/properties/?status=LISTED&search=...&city=...
   - Renders the 4:5 cards with cover image, price, location, beds/baths

3. Buyer clicks a card → /properties/<uuid>
   - JS calls GET /api/v1/properties/<uuid>
   - Renders title, price, description, agency card, contact buttons
   - JS fires POST /api/v1/properties/<uuid>/track_view/ in the background
     → creates a PropertyView row

4. Buyer clicks "Call" or "WhatsApp"
   - Anchor href is tel: or wa.me/<number> (so the click also opens the app)
   - JS fires POST /api/v1/properties/<uuid>/track_click/ with click_type
     → creates a PropertyClick row
     → which creates a LeadEvent row (via the signal in apps/analytics/)
        with source=call|whatsapp|email and a hashed phone

5. (NOT WIRED YET) The agency should get notified:
   - email via Mailgun
   - WhatsApp push via Twilio / direct
   The notifications app is empty — this is Phase-2 work.
```

---

## 8. Agency journey (the dashboard user)

```
1. /signup
   - 5 fields: agency name, your name, work email, password, phone
   - POST /api/v1/auth/register/ creates BOTH the User and the Agency
     in one DB transaction (apps/agencies/views.py:33-67)
   - Response includes access + refresh JWTs → stored in localStorage
   - JS redirects to /dashboard

2. /dashboard (overview)
   - JS calls /agencies/me/, /agencies/me/analytics?period=30d, /agencies/me/listings/
   - Shows: pipeline MAD value (sum of LISTED prices), total views, leads, clicks
   - Recent listings list sorted by views

3. /dashboard/listings
   - Real listings table from /agencies/me/listings/
   - "+ New listing" modal: 10-field form, POST /api/v1/properties/
   - View → /properties/<uuid> in a new tab

4. /dashboard/analytics
   - 4 tiles + period switcher (7d/30d/90d)
   - SVG line chart of views & clicks over time (vanilla, no chart lib)
   - Top listings by views
   - Traffic by source (instagram/facebook/tiktok/youtube/direct)

5. /dashboard/leads
   - Real LeadEvent rows from /agencies/me/leads/
   - Source badge (call/whatsapp/email) + masked phone (****1234)
   - "View listing" link

6. /dashboard/billing
   - Current plan + features (or "Free" if none)
   - All plans loaded from /subscriptions/plans/
   - "Choose plan" → POST /subscriptions/subscribe/ → Stripe Checkout URL
     → browser redirects to checkout.stripe.com
   - "Cancel subscription" → POST /subscriptions/cancel/

7. Logout button in the header clears the JWT and redirects to /
```

---

## 9. Billing & Stripe flow

```
                            User clicks "Choose Pro"
                                       │
                                       ▼
              POST /api/v1/subscriptions/subscribe/  body={plan_slug}
                                       │
                  ┌────────────────────┴────────────────────┐
                  │                                         │
              free plan?                              paid plan?
                  │                                         │
              create AgencySubscription                Stripe Checkout
              status="active" immediately              session.create
              return success                           return checkoutUrl
                  │                                         │
                  │                                         ▼
                  │                          browser.location = checkoutUrl
                  │                                         │
                  │                                         ▼
                  │                          User pays at checkout.stripe.com
                  │                                         │
                  │                                         ▼
                  │                          Stripe → webhook:
                  │                          POST /api/v1/webhooks/stripe/
                  │                          ├ checkout.session.completed
                  │                          │   → activate AgencySubscription
                  │                          │   → create Payment row
                  │                          ├ customer.subscription.updated
                  │                          ├ customer.subscription.deleted
                  │                          └ invoice.payment_failed
                  ▼
              dashboard reloads → shows new current plan
```

Stripe webhook handler: [apps/subscriptions/views.py](apps/subscriptions/views.py). Required `.env` keys: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`. In dev, point Stripe CLI at `http://localhost:8000/api/v1/webhooks/stripe/` and `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe/`.

The subscription plans themselves are seeded in [apps/subscriptions/migrations/0003_seed_subscription_plans.py](apps/subscriptions/migrations/0003_seed_subscription_plans.py) — runs automatically on `manage.py migrate`.

---

## 10. The "Add listing" UI flow (now actually works)

[templates/dashboard/listings.html](templates/dashboard/listings.html) + [templates/assets/yk-dashboard-listings.js](templates/assets/yk-dashboard-listings.js).

```
1. User on /dashboard/listings clicks "+ New listing"
   → JS calls openModal() → modal becomes visible

2. Modal mounts and JS fetches /api/v1/locations/cities/ (16 Morocco cities,
   seeded by `manage.py seed_morocco_cities`)
   → populates the city <select>

3. User fills:
   - Reference code * (yakeey_ref, must be unique)
   - Transaction * (SALE / RENT)
   - Category * (VILLA / HOUSE / FLAT / RIAD / OFFICE / TERRAIN / COMMERCIAL)
   - Type (APARTMENT / STUDIO / DUPLEX / TRIPLEX / RIAD / OFFICE / ...)
   - City * (dropdown)
   - Price MAD *
   - Area m² *
   - Bedrooms, Bathrooms
   - Cover image URL
   - Description (textarea)

4. Submit:
   - JS reads FormData, numerics coerced to Number()
   - POST /api/v1/properties/ with the payload
   - Auth header carries the JWT

5. Backend (apps/properties/views.py):
   - PropertyDetailSerializer validates fields
   - perform_create() saves with agency=request.user.agency
   - returns 201 with the new row

6. JS on success:
   - closes modal, resets form, refreshes the listings table
   - row appears with status=LISTED, views=0, clicks=0, days=0d

7. Listing is now public at /properties/<new-uuid>
   - shows in the /properties browse grid
   - counts toward agency's pipeline MAD value
```

Validated end-to-end against the smoke test account — 201 response, row appears in both `/agencies/me/listings/` and the public `/properties/` list within the same session.

---

## 11. Honest status — what works vs what's wired but inert

### Working today (you can demo it)
- Signup + login + logout (JWT, localStorage)
- Dashboard overview, analytics, leads, listings, billing — all show real DB data
- Public properties browse + filters
- Public property detail page at `/properties/<uuid>` with track-view and track-click
- Add listing UI → property in DB
- Stripe Checkout redirect (with real keys)

### Wired but needs an `.env` key to do anything
- OpenAI caption generation (`OPENAI_API_KEY`)
- R2 / S3 upload (`AWS_*`)
- Instagram + Facebook publishing (`INSTAGRAM_*`, `FACEBOOK_*`)
- Stripe (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`)
- Mailgun emails (`EMAIL_HOST_*`)

### Built but inert (stubs / placeholders)
- `scrape_propertyfinder` Celery task returns `{"status": "disabled_placeholder"}` — wire to the existing `PropertyFinderCollector` class
- `aggregate_daily_analytics` Celery task — analytics still computed on-demand
- TikTok + YouTube publishers raise `NotImplementedError`
- post-create signal that auto-queues `generate_media_for_property` — not connected, so manually-created listings have `media_status="pending"` forever until the batch command runs

### Not built at all
- `apps/notifications/` is empty — lead alerts (email + WhatsApp) need to be implemented here
- Agency claim flow (OTP-based) for scraped agencies to take ownership of their auto-created `CollectedAgency` profile
- Property image upload endpoint (right now images are URL-only via `cover_image_url`)
- Yakeey Parquet bulk import command
- Real charts on `/dashboard/analytics` (currently a vanilla SVG line chart — fine for MVP, swap for Recharts/Chart.js if needed)

---

## 12. Running it locally

```powershell
# one-time
python -m venv venv               # Python 3.12 — 3.14 lacks wheels for psycopg2-binary
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_morocco_cities

# everyday
python manage.py runserver        # http://127.0.0.1:8000
```

Two more commands worth knowing:
```powershell
python manage.py createsuperuser              # to access /admin
python manage.py generate_media               # batch-queue media for pending properties
```

For Celery (when you want the schedule to actually fire):
```powershell
celery -A celery_app worker -l info           # worker
celery -A celery_app beat -l info             # scheduler
```

Stripe webhooks in dev:
```powershell
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe/
```

---

## 13. Map of the codebase (where to look when something breaks)

| Area | File / dir |
|---|---|
| URL routes (incl. frontend templates) | [config/urls.py](config/urls.py) |
| Property model + create endpoint | [apps/properties/](apps/properties/) |
| Auth + agency profile + analytics endpoints | [apps/agencies/](apps/agencies/) |
| Subscriptions + Stripe webhooks | [apps/subscriptions/](apps/subscriptions/) |
| Media generation (captions + videos + S3) | [apps/media_engine/](apps/media_engine/) |
| Social publishers (IG, FB) | [apps/social/](apps/social/) |
| Scraper collector | [apps/scraper/](apps/scraper/) |
| Lead events + click tracking | [apps/analytics/](apps/analytics/) |
| Public market stats | [common/views.py](common/views.py) |
| Celery beat schedule | [celery_app.py](celery_app.py) |
| Celery task implementations | [celery_tasks/](celery_tasks/) |
| Frontend JS (all `/templates/assets/yk-*.js`) | [templates/assets/](templates/assets/) |

That's the whole moving map — every notable piece of behavior lives in one of those locations.
