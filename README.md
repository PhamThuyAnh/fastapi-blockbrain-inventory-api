# Specialty Coffee Inventory API

A FastAPI service that exposes a seeded, in-memory catalogue of **120 specialty coffee lots** behind
OAuth2 Password Bearer authentication with JWT tokens.

Built with Python 3.10+, FastAPI, Uvicorn and Pydantic v2.

---

## Features

- **OAuth2 Password flow with JWT** — `POST /token` exchanges form-encoded credentials for a signed HS256 bearer token.
- **Protected, paginated inventory** — `GET /api/v1/inventory` with `page` / `limit` / `total_records` / `total_pages` / `data`.
- **Filtering** — by origin `country`, `min_score` (SCA cupping score), and free-text `search`.
- **Single-record lookup** — `GET /api/v1/inventory/{item_id}`.
- **Deterministic dataset** — generated with `random.Random(42)`, so IDs and values are stable across restarts.
- **Interactive Swagger UI** at `/docs` and ReDoc at `/redoc`, with a working **Authorize** button.

---

## Setup

```bash
# 1. Clone
git clone https://github.com/PhamThuyAnh/fastapi-oauth2-inventory-api.git
cd fastapi-oauth2-inventory-api

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
source venv/Scripts/activate      # Git Bash on Windows
# .\venv\Scripts\Activate.ps1     # PowerShell
# source venv/bin/activate        # macOS / Linux

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run
uvicorn main:app --reload
```

The API is then at <http://127.0.0.1:8000> and the Swagger UI at <http://127.0.0.1:8000/docs>.

`python main.py` also works — it starts Uvicorn on `127.0.0.1:8000` with reload enabled.

---

## Authentication

| Item | Value |
| --- | --- |
| Flow | OAuth2 Password Bearer |
| Token endpoint | `POST /token` (form-encoded, **not** JSON) |
| Algorithm | HS256 |
| Lifetime | 30 minutes |
| Header | `Authorization: Bearer <access_token>` |

**Demo credentials**

| Username | Password |
| --- | --- |
| `asher` | `testpassword123` |

Get a token:

```bash
curl -X POST http://127.0.0.1:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=asher&password=testpassword123"
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

In Swagger UI, click **Authorize**, enter the same username and password, and every protected
endpoint will then send the token for you.

> **Security note:** the fallback `SECRET_KEY` committed in `main.py` is public knowledge, and the
> single user lives in an in-memory dict behind a stdlib PBKDF2 hash. Set a real `SECRET_KEY` in
> every deployed environment (see [Configuration](#configuration)) and back the user store with a
> database before this guards anything.

---

## Configuration

All settings are read from environment variables at import time, with defaults that keep a fresh
clone runnable.

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | the public dev key | HS256 signing key. **Always override when deployed.** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime in minutes |
| `DEMO_USERNAME` | `asher` | Username of the seeded demo account |
| `DEMO_PASSWORD` | `testpassword123` | Password of the seeded demo account |

Generate a signing key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

While the fallback key is in use, `GET /` includes a `warning` field. Once `SECRET_KEY` is set, that
field disappears — a quick way to confirm your deployment picked up the variable.

---

## Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/` | — | Service metadata and record count |
| `GET` | `/health` | — | Liveness probe |
| `POST` | `/token` | — | Exchange credentials for a JWT |
| `GET` | `/api/v1/users/me` | Bearer | The current token's owner |
| `GET` | `/api/v1/inventory` | Bearer | Paginated, filterable lot list |
| `GET` | `/api/v1/inventory/{item_id}` | Bearer | A single lot by ID |
| `GET` | `/docs` | — | Swagger UI |
| `GET` | `/redoc` | — | ReDoc |
| `GET` | `/openapi.json` | — | OpenAPI 3.1 schema |

### Query parameters for `GET /api/v1/inventory`

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `page` | int ≥ 1 | `1` | 1-based page number |
| `limit` | int 1–100 | `10` | Records per page |
| `country` | string | — | Exact origin country match, case-insensitive (e.g. `Ethiopia`) |
| `min_score` | float 0–100 | — | Only lots whose `cupping_score` is ≥ this value |
| `search` | string | — | Case-insensitive substring match across `name`, `region`, `variety`, `process` and `origin_country` |

Filters combine with AND. A `limit` above 100 or a `page` below 1 returns `422`.

---

## Record schema

```json
{
  "id": 7,
  "name": "Finca Deborah Typica 22/23",
  "origin_country": "Panama",
  "region": "Boquete",
  "variety": "Typica",
  "process": "Washed",
  "altitude_masl": 1950,
  "cupping_score": 87.75,
  "stock_bags": 97,
  "price_per_kg_usd": 24.23
}
```

| Field | Notes |
| --- | --- |
| `id` | Stable integer, `1`–`120` |
| `name` | Farm or washing station, variety, and harvest year |
| `origin_country` | One of 18 producing countries |
| `region` | A real growing region within that country |
| `variety` | Cultivar, e.g. `SL28`, `Gesha`, `Pacamara`, `Heirloom` |
| `process` | `Washed`, `Natural`, `Honey`, `Anaerobic Natural`, `Carbonic Maceration`, `Wet-Hulled`, … |
| `altitude_masl` | Metres above sea level, in 10 m steps |
| `cupping_score` | SCA score to the nearest quarter point; 80+ is specialty grade |
| `stock_bags` | 60 kg bags on hand — scarcer at the top of the quality curve |
| `price_per_kg_usd` | Tracks cup score, with a premium for rare varieties and experimental processing |

---

## Example requests

Store a token in a shell variable first:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/token \
  -d "username=asher&password=testpassword123" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

**Second page, three per page**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/inventory?page=2&limit=3"
```

**Ethiopian lots scoring 88 or better**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/inventory?country=Ethiopia&min_score=88"
```

**Every Gesha in the book**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/inventory?search=gesha&limit=50"
```

**Anaerobic lots from Colombia**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/inventory?country=Colombia&search=anaerobic"
```

**A single lot**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/inventory/7"
```

**Who am I?**

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/users/me
```

### Response shape for the list endpoint

```json
{
  "page": 2,
  "limit": 3,
  "total_records": 120,
  "total_pages": 40,
  "data": [ { "id": 4, "name": "Fazenda Rainha Catuai 23/24", "...": "..." } ]
}
```

---

## Status codes

| Code | When |
| --- | --- |
| `200` | Success |
| `401` | Missing, malformed, or expired token; or wrong credentials at `/token` |
| `404` | No inventory item with that ID |
| `422` | Query parameter fails validation (e.g. `limit=500`) |

---

## Project layout

```
fastapi-oauth2-inventory-api/
├── main.py            # App, auth, dataset generator, endpoints
├── api/
│   └── index.py       # Vercel serverless entrypoint (re-exports main.app)
├── vercel.json        # Routes every path to the function
├── requirements.txt   # Dependencies
├── .gitignore
├── .vercelignore
└── README.md
```

---

## Deploying to Vercel

The repo is deploy-ready: `api/index.py` exposes the same `app` as local development, and
`vercel.json` rewrites every path to it so `/token`, `/api/v1/...` and `/docs` all work.

### Option A — Vercel dashboard

1. Go to <https://vercel.com/new> and import `PhamThuyAnh/fastapi-oauth2-inventory-api`.
2. Leave the framework preset as **Other** — `vercel.json` supplies the configuration.
3. Add the environment variables from [Configuration](#configuration) (at minimum `SECRET_KEY`).
4. Click **Deploy**.

### Option B — Vercel CLI

```bash
npm i -g vercel

vercel login
vercel link                                    # link this folder to a project

# Set secrets for all three environments
vercel env add SECRET_KEY production
vercel env add SECRET_KEY preview
vercel env add SECRET_KEY development

vercel deploy --prod
```

### Verifying the deployment

```bash
BASE=https://<your-deployment>.vercel.app

# No "warning" field means SECRET_KEY was picked up
curl -s $BASE/

TOKEN=$(curl -s -X POST $BASE/token \
  -d "username=asher&password=testpassword123" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/inventory?limit=3"
```

Swagger UI is at `$BASE/docs`.

### Serverless caveats

- **Cold starts.** The 120-lot dataset is rebuilt on each cold start. Because the generator is seeded
  with `random.Random(42)`, every instance produces byte-identical records — IDs stay stable.
- **Stateless.** There is no shared writable state, so the read-only inventory suits serverless well.
  Any future write endpoint needs a real database; in-memory mutations would not survive.
- **Tokens survive redeploys** only while `SECRET_KEY` stays the same. Rotating it invalidates every
  issued token.

---

## Changing the dataset

Both knobs live at the top of the dataset section in [main.py](main.py):

```python
TOTAL_RECORDS = 120
RANDOM_SEED = 42
```

Add a country to the `ORIGINS` dict — with its regions, varieties, farms, altitude band, score band
and processing methods — and the generator picks it up on the next start.
