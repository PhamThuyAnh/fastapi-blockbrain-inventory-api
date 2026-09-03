# Specialty Coffee & Inventory API

## Purpose

A custom **External API** for the **Blockbrain** platform.

It serves a seeded, in-memory catalogue of **100 specialty coffee lots** behind **HTTP Basic
Authentication**, and publishes an **OpenAPI 3.1** specification at `/openapi.json` that Blockbrain
reads to discover, route and execute tool calls.

Built to be easy for an agent to call correctly:

- **One security scheme** (`HTTPBasic`) — no ambiguity about how to authenticate.
- **Explicit operation IDs** — `listInventory`, `getInventoryItem`, `getInventoryStatistics`.
- **Described parameters** with examples and bounds, so calls are valid on the first try.
- **A tight schema** — `/` and `/health` are excluded, leaving only the three callable tools.
- **Deterministic data** (`random.Random(42)`) — the same question always returns the same numbers.

Stack: Python 3.10+ · FastAPI · Uvicorn · Pydantic v2

### Tools exposed to the agent

| Operation ID | Endpoint | Description |
| :--- | :--- | :--- |
| `listInventory` | `GET /api/v1/inventory` | Paginated lot list; filter by `country`, `min_score`, `search` |
| `getInventoryItem` | `GET /api/v1/inventory/{item_id}` | One lot by ID (1–100) |
| `getInventoryStatistics` | `GET /api/v1/statistics` | Totals, score range, inventory value, per-country breakdown |

---

## Blockbrain setup

### 1. Get a public HTTPS URL

Blockbrain must be able to reach the API, so it needs to be hosted. Import the repo at
<https://vercel.com/new> with **Application Preset** `FastAPI` and **Root Directory** `./` — not
`api`, or the build misses `requirements.txt` and `main.py`.

To run it locally first:

```bash
python -m venv venv
source venv/Scripts/activate      # .\venv\Scripts\Activate.ps1 on PowerShell
pip install -r requirements.txt
uvicorn main:app --reload         # http://127.0.0.1:8000/docs
```

### 2. Register the External API

In Blockbrain, add a custom External API with these values:

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

`/openapi.json` and `/docs` are public on purpose, so the registry can fetch the specification
without credentials. Every `/api/v1/*` endpoint requires the Basic credentials.

Override the credentials per environment with `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD`.

### 3. Confirm it works

```bash
curl -u asher:testpassword123 https://<your-host>/api/v1/statistics
```

Then ask an agent something like *"Which Ethiopian coffee lots cup above 88?"* or *"How many bags do
we hold, and what is the inventory worth?"*

### If something fails

| Symptom | Fix |
| :--- | :--- |
| Registry cannot fetch the spec | `https://<host>/openapi.json` must return 200 without credentials |
| Agent calls return `401` | Registry Authentication must be `Basic`, not Bearer |
| Registry rejects the schema | The document is OpenAPI 3.1.0; if only 3.0.x is accepted, set `app.openapi_version = "3.0.3"` in [main.py](main.py) |
| Every request returns a FastAPI `404` | A host rewrite is mangling the request path — the app must receive the original path, not a rewritten one |
