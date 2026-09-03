# Specialty Coffee & Inventory API

A FastAPI service that exposes a seeded, in-memory catalogue of **100 specialty coffee lots** behind
**HTTP Basic Authentication**, built to be registered as a custom **External API** on the
**Blockbrain** platform.

Python 3.10+ · FastAPI · Uvicorn · Pydantic v2

Live: <https://fastapi-oauth2-inventory-api.vercel.app>

---

## Blockbrain Registry Configuration

Paste these values into the Blockbrain **External API** registry.

| Field | Value |
| :--- | :--- |
| **Name** | `Specialty Coffee & Inventory API` |
| **Description** | `Custom testing API with 100+ seeded specialty coffee inventory records and HTTP Basic Authentication.` |
| **API Specification** | `https://<your-host>/openapi.json` (or upload `openapi.json`) |
| **API Base URL** | `https://<your-host>` |
| **Type** | `Open API` |
| **Logo URL** | `https://cdn-icons-png.flaticon.com/512/924/924514.png` |
| **Authentication** | `Basic` (Username: `asher`, Password: `testpassword123`) |
| **Custom Headers** | `Accept: application/json` |

Filled in for the current deployment:

| Field | Value |
| :--- | :--- |
| **API Specification** | `https://fastapi-oauth2-inventory-api.vercel.app/openapi.json` |
| **API Base URL** | `https://fastapi-oauth2-inventory-api.vercel.app` |

### Why this API is agent-friendly

- **One security scheme.** The OpenAPI document declares exactly one — `HTTPBasic` — so there is no
  ambiguity about how an agent should authenticate.
- **Explicit operation IDs.** `listInventory`, `getInventoryItem`, `getInventoryStatistics` become
  clean, readable tool names.
- **Described parameters.** Every query parameter carries a description with example values, and
  bounds (`ge` / `le`) are in the schema, so an agent can construct valid calls on the first try.
- **A tight schema.** `/` and `/health` exist for humans and uptime checks but are excluded from
  `/openapi.json`, so the document contains only the three callable tools.
- **Deterministic answers.** The dataset is seeded, so the same question always yields the same
  numbers.

---

## Setup

```bash
git clone https://github.com/PhamThuyAnh/fastapi-oauth2-inventory-api.git
cd fastapi-oauth2-inventory-api

python -m venv venv

source venv/Scripts/activate      # Git Bash on Windows
# .\venv\Scripts\Activate.ps1     # PowerShell
# source venv/bin/activate        # macOS / Linux

pip install -r requirements.txt

uvicorn main:app --reload
```

- API: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

`python main.py` works too — it starts Uvicorn on `127.0.0.1:8000` with reload enabled.

---

## Authentication

HTTP Basic on every `/api/v1/*` endpoint. Blockbrain sends the header automatically when its
**Authentication** field is set to `Basic`.

| Item | Value |
| :--- | :--- |
| Scheme | HTTP Basic (`fastapi.security.HTTPBasic`) |
| Username | `asher` |
| Password | `testpassword123` |
| Header | `Authorization: Basic YXNoZXI6dGVzdHBhc3N3b3JkMTIz` |

```bash
curl -u asher:testpassword123 http://127.0.0.1:8000/api/v1/inventory
```

A missing or wrong credential returns `401` with `WWW-Authenticate: Basic`. Both the username and
the password are compared with `secrets.compare_digest`, so a wrong username and a wrong password
take the same time to reject.

> **Security note:** these credentials are public — they are in this README, in a public repository.
> The dataset is synthetic, so nothing sensitive is exposed, but override the credentials with the
> environment variables below before putting anything real behind them.

### Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `BASIC_AUTH_USERNAME` | `asher` | Basic auth username |
| `BASIC_AUTH_PASSWORD` | `testpassword123` | Basic auth password |
| `PUBLIC_BASE_URL` | *(unset)* | When set, added to the OpenAPI `servers` block as the absolute base URL |

---

## Endpoints

| Method | Path | Operation ID | Auth | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/inventory` | `listInventory` | Basic | Paginated, filterable lot list |
| `GET` | `/api/v1/inventory/{item_id}` | `getInventoryItem` | Basic | A single lot by integer ID |
| `GET` | `/api/v1/statistics` | `getInventoryStatistics` | Basic | Portfolio-wide aggregates |
| `GET` | `/openapi.json` | — | — | OpenAPI 3.1 schema |
| `GET` | `/docs` | — | — | Swagger UI |
| `GET` | `/redoc` | — | — | ReDoc |
| `GET` | `/health` | — | — | Liveness probe (not in schema) |

`/openapi.json` and `/docs` are deliberately public so the Blockbrain registry can fetch the
specification without credentials.

### Query parameters for `GET /api/v1/inventory`

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `page` | int ≥ 1 | `1` | Page number, starting at 1 |
| `limit` | int 1–100 | `10` | Maximum records per page |
| `country` | string | — | Exact origin country, case-insensitive (e.g. `Ethiopia`) |
| `min_score` | float 0–100 | — | Only lots with `cupping_score` ≥ this value |
| `search` | string | — | Case-insensitive substring match across `name`, `region`, `variety`, `process`, `origin_country` |

Filters combine with AND. Out-of-range values return `422`.

---

## Response shapes

### `GET /api/v1/inventory`

```json
{
  "total_records": 100,
  "page": 1,
  "page_size": 2,
  "total_pages": 50,
  "data": [
    {
      "id": 1,
      "name": "Adado Cooperative Heirloom 24/25",
      "origin_country": "Ethiopia",
      "region": "Jimma",
      "variety": "Heirloom",
      "process": "Washed",
      "altitude_masl": 1920,
      "cupping_score": 86.75,
      "stock_bags": 30,
      "price_per_kg_usd": 19.2
    }
  ]
}
```

### `GET /api/v1/inventory/{item_id}`

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

### `GET /api/v1/statistics`

```json
{
  "total_lots": 100,
  "total_stock_bags": 10544,
  "total_stock_kg": 632640.0,
  "average_cupping_score": 86.68,
  "highest_cupping_score": 92.0,
  "lowest_cupping_score": 81.0,
  "average_price_per_kg_usd": 29.84,
  "total_inventory_value_usd": 13400256.6,
  "country_count": 18,
  "country_breakdown": [
    {
      "origin_country": "Brazil",
      "lot_count": 6,
      "total_stock_bags": 559,
      "average_cupping_score": 84.62,
      "average_price_per_kg_usd": 13.82
    }
  ]
}
```

`country_breakdown` is ordered by `lot_count` descending, then alphabetically.

---

## Dataset

100 records generated by `generate_inventory()` from `random.Random(42)`, round-robin across 18
producing countries so every origin is represented. Rebuilding on any machine — or on a serverless
cold start — yields byte-identical records.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `id` | int | Stable, `1`–`100` |
| `name` | str | Farm or washing station, variety, harvest year |
| `origin_country` | str | One of 18 producing countries |
| `region` | str | A real growing region within that country |
| `variety` | str | Cultivar, e.g. `SL28`, `Gesha`, `Pacamara`, `Heirloom` |
| `process` | str | `Washed`, `Natural`, `Honey`, `Anaerobic Natural`, `Carbonic Maceration`, `Wet-Hulled`, … |
| `altitude_masl` | int | Metres above sea level, in 10 m steps |
| `cupping_score` | float | SCA score to the nearest quarter point; 80+ is specialty grade |
| `stock_bags` | int | 60 kg bags on hand — scarcer at the top of the quality curve |
| `price_per_kg_usd` | float | Tracks cup score, with a premium for rare varieties and experimental processing |

To resize or reshuffle, change `TOTAL_RECORDS` or `RANDOM_SEED` at the top of the dataset section in
[main.py](main.py), or add a country to the `ORIGINS` dict.

---

## Example requests

```bash
BASE=http://127.0.0.1:8000          # or your public host
AUTH=asher:testpassword123
```

**First page, five per page**

```bash
curl -u $AUTH "$BASE/api/v1/inventory?page=1&limit=5"
```

**Ethiopian lots scoring 88 or better**

```bash
curl -u $AUTH "$BASE/api/v1/inventory?country=Ethiopia&min_score=88"
```

**Every Gesha in the book**

```bash
curl -u $AUTH "$BASE/api/v1/inventory?search=gesha&limit=100"
```

**Anaerobic lots from Colombia**

```bash
curl -u $AUTH "$BASE/api/v1/inventory?country=Colombia&search=anaerobic"
```

**A single lot**

```bash
curl -u $AUTH "$BASE/api/v1/inventory/7"
```

**Portfolio statistics**

```bash
curl -u $AUTH "$BASE/api/v1/statistics"
```

**The specification Blockbrain reads** (no credentials needed)

```bash
curl "$BASE/openapi.json"
```

### Questions a Blockbrain agent can answer with these tools

- "Which Ethiopian lots cup above 88?" → `listInventory(country=Ethiopia, min_score=88)`
- "Show me every Gesha we hold." → `listInventory(search=gesha, limit=100)`
- "What is lot 42?" → `getInventoryItem(item_id=42)`
- "How many bags do we have, and what is the inventory worth?" → `getInventoryStatistics()`
- "Which country has our highest average cupping score?" → `getInventoryStatistics()`, then read
  `country_breakdown`

---

## Status codes

| Code | When |
| :--- | :--- |
| `200` | Success |
| `401` | Missing or invalid HTTP Basic credentials |
| `404` | No coffee lot with the requested ID |
| `422` | A parameter failed validation (e.g. `limit=500`, `item_id=0`) |

---

## Project layout

```text
fastapi-oauth2-inventory-api/
├── main.py            # App, Basic auth, dataset generator, endpoints
├── requirements.txt   # fastapi, uvicorn[standard], pydantic
├── .gitignore
├── .vercelignore
└── README.md
```

---

## Deployment

Blockbrain needs a publicly reachable HTTPS base URL. Any of the following works.

### Option A — Vercel (current deployment)

Import the repo at <https://vercel.com/new>, then:

- **Application Preset:** `FastAPI`
- **Root Directory:** `./` — **not** `api`, or the build misses `requirements.txt` and `main.py`
- **Environment Variables:** `BASIC_AUTH_USERNAME`, `BASIC_AUTH_PASSWORD` (optional but recommended)

Vercel's FastAPI preset detects `app` in `main.py` at the project root and serves every path to it
with the request path preserved. No `vercel.json` and no `api/` wrapper are needed.

> Do **not** add a `vercel.json` that rewrites `/(.*)` to `/api/index`: the function receives the
> destination path, so the ASGI app sees `/api/index`, matches no route, and every request returns
> FastAPI's own 404.

### Option B — Render (free tier)

1. Push this repo to GitHub.
2. At <https://dashboard.render.com> create a **New → Web Service** and connect the repository.
3. Configure:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`
4. Add the environment variables from [Configuration](#configuration).
5. Deploy. The public URL becomes your **API Base URL**.

A free Render instance spins down when idle, so the first request after a quiet spell takes a few
seconds. Point Render's health check at `/health` to keep the check itself cheap.

### Option C — ngrok (local tunnel, for quick testing)

Useful when you want Blockbrain to reach the API running on your own machine.

```bash
# Terminal 1
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2
ngrok http 8000
```

Use the `https://….ngrok-free.app` URL ngrok prints as the **API Base URL**, and
`https://….ngrok-free.app/openapi.json` as the **API Specification**.

Two caveats: a free ngrok URL changes every restart, so you must update the Blockbrain registry each
time; and ngrok's free tier serves a browser warning page on first visit — send
`ngrok-skip-browser-warning: true` as a custom header if the registry trips over it.

### Serverless / free-tier notes

- **Cold starts.** The dataset is rebuilt on each cold start. Because the generator is seeded, every
  instance produces identical records, so IDs stay stable.
- **Stateless.** The inventory is read-only, which suits serverless well. Any future write endpoint
  would need a real database — in-memory mutations would not survive.

---

## Troubleshooting

| Symptom | Cause and fix |
| :--- | :--- |
| Blockbrain cannot fetch the specification | Confirm `https://<host>/openapi.json` returns 200 without credentials. It is public by design. |
| Every request returns FastAPI's own 404 | A rewrite is mangling the request path — see the warning under Option A. |
| Agent calls return `401` | Registry Authentication must be `Basic` with the username and password above, not Bearer. |
| Registry rejects the schema | The document is OpenAPI **3.1.0**. If the registry only parses 3.0.x, set `app.openapi_version = "3.0.3"` in [main.py](main.py) and re-fetch. |
| `422` on an agent call | A parameter is out of bounds — `limit` must be 1–100, `item_id` ≥ 1, `min_score` 0–100. |
