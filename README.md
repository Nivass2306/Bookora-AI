# Bookora AI

Bookora AI is a bookstore-first Django demonstration with an online catalogue, simulated checkout, authorized digital reading, optional Premium demo subscriptions, audiobook metadata, and server-side Gemini book assistance.

## Features

- Responsive editorial storefront, database-backed search and category filters, sorting, pagination, featured books, best sellers, new arrivals, free reads, Premium Reads, and audiobook discovery.
- Customer registration and login, account details, private order history, persistent wishlists, subscription status, and reading history.
- Combined customer/admin login at `/login/` using Django authentication, plus a permission-checked, Bookora-branded `/staff/` management portal. Staff manage catalogue listings, customers, demo orders, subscriptions, refund reviews, and recorded activity.
- Session shopping bag with server-side price snapshots, quantity validation, and idempotent transactional demo checkout. Stock values are preserved and never block physical demo purchases. No card data or payment processing.
- Free, separately entitled digital purchases, and selected subscription-library access are enforced in Django views. A physical print order never grants reading access. Subscription books are explicitly selected and require available authorized digital content.
- Reader supports authorized section text, UTF-8 TXT, and protected PDF. Reading progress is private to the customer and resumes on return.
- Optional ₹99/month (30-day term) online-reading plan with manual renewals, a three-day grace period, payment-attempt history, separate refund requests, book entitlements, and immediate audited revocation. Development payment simulation is clearly labeled and never moves money; payment verification is required for activation.
- Audiobook listings, authorized sample and full-player routes, and unavailable-recording states. The demo catalogue does not claim unverified recordings are playable.
- Gemini summary endpoint with cached results, timeout/error states, and server-only API key. A catalogue-grounded read-only chatbot validates links against actual database records and falls back to local matching. The Reading Companion works without Gemini.
- Newsletter validation and duplicate prevention. Subscriber records are available in Django Admin; no email delivery is configured.

## Stack and structure

Python 3.13, Django 6.1, SQLite, Django templates, CSS, and JavaScript. Gemini uses the `generateContent` REST endpoint through `requests`.

```text
config/       Django settings and URL configuration
store/        Models, views, Gemini helper, management commands, migrations, tests
templates/    Shared storefront, reader, account, staff, and admin pages
static/store/ Responsive styles and frontend interactions
```

## Setup

In a fresh virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a unique `DJANGO_SECRET_KEY`. Set `GEMINI_API_KEY` to enable AI summaries and chatbot responses. `GEMINI_MODEL` defaults to `gemini-3.8-flash`. Keep `.env` private and do not place the key in client-side code.

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_books
python manage.py seed_audiobooks
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Customer and admin options share `/login/`; authorized staff can also retain the internal `/staff/login/` route and use `/staff/`. To set or replace the local `admin` password, run `python manage.py changepassword admin` and enter a unique password interactively; never put it in source or shell history. `seed_books` creates 12 fictional demo titles, four categories, and the default ₹99 INR plan. It is repeatable and does not overwrite existing books or categories. No full digital text is bundled. `seed_audiobooks` creates metadata-only listings. Rerunning either command is safe.

Staff can add verified metadata, authorized excerpts/reader text, and licensed media through the admin. Private uploads accept PDF up to 30 MB, UTF-8 TXT up to 2 MB, and MP3/OGG/WAV up to 100 MB; extension, signature, and size are checked in the admin form. Files are stored in `private_uploads/`, outside `MEDIA_ROOT`, and streamed only through access-checked views. Configure deployment servers so `private_uploads/` is never publicly served. A reader page has no digital edition until staff supply authorized content. Audiobook listings remain unavailable until a recording is supplied and activated.

The subscription plan costs ₹99 for each 30-day period. Price is snapshotted per payment attempt; a changed plan price cancels an unconfirmed attempt so the user can review and choose the new amount. The local simulator can simulate success, decline, or cancellation but does not connect to a payment provider or collect money. Only a simulated success in DEBUG mode creates a paid-period record, and the UI states that it is simulated. In production, no subscription activation is available until a real payment provider and verified callback are configured. Subscription refunds remain pending/approved unless a separately confirmed refund is recorded; physical-order refund requests are stored separately. Neither workflow marks a real refund without confirmation.

Books must be marked `Premium digital access`, selected as `Included in Online Subscription`, and have authorized digital content before they appear in the Online Library. Existing legacy demo subscriptions are preserved as `Legacy demo (unpaid)` and do not grant access. Newsletter emails are stored for staff review; no newsletters are sent. Seeded book descriptions and titles are fictional sample data.

## Deployment and verification

For deployment, set `DJANGO_DEBUG=False`, a strong unique `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS`. Production settings enable HTTPS redirect (configurable with `DJANGO_SECURE_SSL_REDIRECT`), secure cookies, HSTS, content-type protection, and a same-origin referrer policy. Ensure HTTPS and a shared cache backend are configured for multi-worker deployments.

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Gemini tests use mocked responses; live generation requires a configured key and network access. The chatbot is read-only and keeps session conversation history in Django's session store. AI failure falls back to catalogue search; newsletter delivery, real payment provider callbacks, and recurring billing are not configured. Subscription renewal is always user-initiated. Store activity logs begin recording supported events after migration; historical events are not reconstructed.
