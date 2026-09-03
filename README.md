# Specialty Coffee & Inventory API

A shared **test API** for verifying the **External API** feature on the **Blockbrain** platform.

It is already deployed and open for any QA on the team to register in Blockbrain — nothing to host,
nothing to install. Every value below can be copy-pasted as-is.

**Live base URL:** <https://fastapi-blockbrain-inventory-api.vercel.app>
**Credentials:** `asher` / `testpassword123` (HTTP Basic)

> These credentials are deliberately public. This project holds no real data — it serves 100
> deterministically generated coffee lots so every QA gets identical numbers.

---

## Blockbrain setup

### 1. Register the External API

In Blockbrain → add a custom External API, and fill in exactly these values:

| Field | Value |
| :--- | :--- |
| **Name** | `Specialty Coffee & Inventory API` |
| **Description** | `Custom testing API with 100 seeded specialty coffee inventory records and HTTP Basic Authentication.` |
| **Type** | `Open API` |
| **API Specification** | `https://fastapi-blockbrain-inventory-api.vercel.app/openapi.json` |
| **API Base URL** | `https://fastapi-blockbrain-inventory-api.vercel.app` |
| **Logo URL** | `https://cdn-icons-png.flaticon.com/512/924/924514.png` |
| **Authentication** | `Basic` |
| **Username** | `asher` |
| **Password** | `testpassword123` |
| **Custom Headers** | `Accept: application/json` |

If the registry asks for a raw header instead of a username/password pair:

```
Authorization: Basic YXNoZXI6dGVzdHBhc3N3b3JkMTIz
```

`/openapi.json` and `/docs` are public on purpose, so the registry can fetch the specification
without credentials. Every `/api/v1/*` endpoint requires the Basic credentials.

### 2. Confirm the API answers before you register it

```bash
curl -u asher:testpassword123 https://fastapi-blockbrain-inventory-api.vercel.app/api/v1/statistics
```

Expected — 100 lots across 18 countries:

```json
{"total_lots":100,"total_stock_bags":10544,"total_stock_kg":632640.0,"average_cupping_score":86.68,
 "highest_cupping_score":92.0,"lowest_cupping_score":81.0,"average_price_per_kg_usd":29.84,
 "total_inventory_value_usd":13400256.6,"country_count":18,"country_breakdown":[...]}
```

PowerShell version:

```powershell
curl.exe -u asher:testpassword123 https://fastapi-blockbrain-inventory-api.vercel.app/api/v1/statistics
```

Interactive docs (no login needed to open, click **Authorize** to call): <https://fastapi-blockbrain-inventory-api.vercel.app/docs>

### 3. Ask the agent something

Prompts that exercise all three tools:

- *"Which Ethiopian coffee lots cup above 88?"* → `listInventory`
- *"Show me lot 37."* → `getInventoryItem`
- *"How many bags do we hold, and what is the inventory worth?"* → `getInventoryStatistics`

Because the data is seeded with a fixed random seed, the answers never change — *"Which Ethiopian
lots cup above 88?"* returns 4 lots, the first being **Hambela Estate Heirloom 24/25** (id `37`,
Yirgacheffe, Natural, 89.5 points), every single time. That makes it easy to tell a Blockbrain
routing bug apart from changing data.

---

## Tools exposed to the agent

| Operation ID | Endpoint | Description |
| :--- | :--- | :--- |
| `listInventory` | `GET /api/v1/inventory` | Paginated lot list; filter by `country`, `min_score`, `search`; page with `page`, `limit` |
| `getInventoryItem` | `GET /api/v1/inventory/{item_id}` | One lot by ID (1–100) |
| `getInventoryStatistics` | `GET /api/v1/statistics` | Totals, score range, inventory value, per-country breakdown |

Ready-to-run calls:

```bash
BASE=https://fastapi-blockbrain-inventory-api.vercel.app
AUTH="asher:testpassword123"

curl -u "$AUTH" "$BASE/api/v1/inventory?page=1&limit=5"
curl -u "$AUTH" "$BASE/api/v1/inventory?country=Ethiopia&min_score=88"
curl -u "$AUTH" "$BASE/api/v1/inventory?search=gesha"
curl -u "$AUTH" "$BASE/api/v1/inventory/37"
curl -u "$AUTH" "$BASE/api/v1/statistics"

# Should return 401 — use this to verify the registry is actually sending credentials
curl -i "$BASE/api/v1/statistics"
```

---

## Why the API is shaped this way

Built so an agent calls it correctly on the first try:

- **One security scheme** (`HTTPBasic`) — no ambiguity about how to authenticate.
- **Explicit operation IDs** — `listInventory`, `getInventoryItem`, `getInventoryStatistics`.
- **Described parameters** with examples and bounds, so calls are valid on the first try.
- **A tight schema** — `/` and `/health` are excluded, leaving only the three callable tools.
- **Deterministic data** (`random.Random(42)`) — the same question always returns the same numbers.

Stack: Python 3.10+ · FastAPI · Uvicorn · Pydantic v2 · deployed on Vercel · OpenAPI 3.1.0

---

## If something fails

| Symptom | Fix |
| :--- | :--- |
| Registry cannot fetch the spec | `https://fastapi-blockbrain-inventory-api.vercel.app/openapi.json` must return `200` without credentials — open it in a browser to check |
| Agent calls return `401` | Authentication must be `Basic`, not Bearer. Verify with `curl -u asher:testpassword123 .../api/v1/statistics` |
| Registry rejects the schema | The document is OpenAPI 3.1.0; if only 3.0.x is accepted, set `app.openapi_version = "3.0.3"` in [main.py](main.py) and redeploy |
| Every request returns a FastAPI `404` | A host rewrite is mangling the request path — the app must receive the original path, not a rewritten one |
| The whole host returns `404` | The deployment was removed or renamed. Redeploy your own copy (below) and swap the base URL |

---

## Run your own copy (optional)

Only needed if you want to change the data or the schema — the deployment above is enough for
normal Blockbrain testing.

Deploy: import <https://github.com/PhamThuyAnh/fastapi-blockbrain-inventory-api> at
<https://vercel.com/new> with **Application Preset** `FastAPI` and **Root Directory** `./` — not
`api`, or the build misses `requirements.txt` and `main.py`.

Run it on your machine:

```bash
python -m venv venv
source venv/Scripts/activate      # .\venv\Scripts\Activate.ps1 on PowerShell
pip install -r requirements.txt
uvicorn main:app --reload
```

Environment variables, all optional:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `BASIC_AUTH_USERNAME` | `asher` | Basic Auth username |
| `BASIC_AUTH_PASSWORD` | `testpassword123` | Basic Auth password |
| `PUBLIC_BASE_URL` | *(unset)* | Advertised in the OpenAPI `servers` block, for registries that need an absolute server URL |
