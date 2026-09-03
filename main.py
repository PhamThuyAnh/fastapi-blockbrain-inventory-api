"""
Specialty Coffee & Inventory API
================================

A FastAPI service exposing a seeded, in-memory catalogue of specialty coffee
lots behind HTTP Basic Authentication, built to be registered as a custom
External API on the Blockbrain platform.

The OpenAPI 3.1 document at /openapi.json carries explicit operation IDs,
endpoint summaries and per-parameter descriptions so Blockbrain agents can
discover, route and execute tool calls accurately.

Run locally:
    uvicorn main:app --reload

Interactive docs:
    http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import math
import os
import random
import secrets
from collections import defaultdict
from typing import Annotated, Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Authentication
#
# HTTP Basic, which is what the Blockbrain External API registry sends when
# its "Authentication" field is set to `Basic`. Credentials are overridable
# per environment; the defaults match the values registered in the README.
# ---------------------------------------------------------------------------

BASIC_AUTH_USERNAME = os.environ.get("BASIC_AUTH_USERNAME", "asher")
BASIC_AUTH_PASSWORD = os.environ.get("BASIC_AUTH_PASSWORD", "testpassword123")

security = HTTPBasic()


def require_basic_auth(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    """Validate HTTP Basic credentials and return the authenticated username.

    Both comparisons use `secrets.compare_digest` so a wrong username and a
    wrong password take the same time to reject.
    """
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf-8"), BASIC_AUTH_USERNAME.encode("utf-8")
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf-8"), BASIC_AUTH_PASSWORD.encode("utf-8")
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


AuthenticatedUser = Annotated[str, Depends(require_basic_auth)]


# ---------------------------------------------------------------------------
# Pydantic v2 models
# ---------------------------------------------------------------------------


class CoffeeLot(BaseModel):
    """A single green-coffee lot held in inventory."""

    id: int = Field(description="Stable inventory identifier, 1 through 100.", examples=[7])
    name: str = Field(
        description="Lot name: farm or washing station, variety and harvest year.",
        examples=["Finca Deborah Typica 22/23"],
    )
    origin_country: str = Field(description="Producing country.", examples=["Panama"])
    region: str = Field(description="Growing region within the origin country.", examples=["Boquete"])
    variety: str = Field(description="Coffee cultivar.", examples=["Gesha"])
    process: str = Field(
        description="Post-harvest processing method.",
        examples=["Washed", "Natural", "Anaerobic Natural"],
    )
    altitude_masl: int = Field(description="Growing altitude in metres above sea level.", examples=[1950])
    cupping_score: float = Field(
        description="SCA cupping score. 80 and above is specialty grade; 90+ is exceptional.",
        examples=[87.75],
    )
    stock_bags: int = Field(description="Bags currently on hand; one bag is 60 kg.", examples=[97])
    price_per_kg_usd: float = Field(description="Wholesale price per kilogram in USD.", examples=[24.23])


class PaginatedInventory(BaseModel):
    """One page of inventory records plus the counts needed to page through."""

    total_records: int = Field(description="Records matching the filters, across all pages.")
    page: int = Field(description="The page number returned.")
    page_size: int = Field(description="Maximum records per page, echoing the `limit` parameter.")
    total_pages: int = Field(description="Number of pages available for the current filters.")
    data: list[CoffeeLot] = Field(description="The records on this page.")


class CountryBreakdown(BaseModel):
    """Aggregated inventory figures for one origin country."""

    origin_country: str = Field(description="Producing country.")
    lot_count: int = Field(description="Number of distinct lots from this country.")
    total_stock_bags: int = Field(description="Bags on hand across the country's lots.")
    average_cupping_score: float = Field(description="Mean SCA score, rounded to two decimals.")
    average_price_per_kg_usd: float = Field(description="Mean price per kilogram in USD.")


class InventoryStatistics(BaseModel):
    """Portfolio-wide aggregates over the whole inventory."""

    total_lots: int = Field(description="Total number of coffee lots held.")
    total_stock_bags: int = Field(description="Total bags on hand across every lot.")
    total_stock_kg: float = Field(description="Total green weight in kilograms, at 60 kg per bag.")
    average_cupping_score: float = Field(description="Mean SCA score across all lots.")
    highest_cupping_score: float = Field(description="Best SCA score in the inventory.")
    lowest_cupping_score: float = Field(description="Lowest SCA score in the inventory.")
    average_price_per_kg_usd: float = Field(description="Mean price per kilogram in USD.")
    total_inventory_value_usd: float = Field(
        description="Sum of stock_bags * 60 kg * price_per_kg_usd across all lots."
    )
    country_count: int = Field(description="Number of distinct origin countries represented.")
    country_breakdown: list[CountryBreakdown] = Field(
        description="Per-country aggregates, ordered by lot count descending."
    )


# ---------------------------------------------------------------------------
# Seeded in-memory dataset
# ---------------------------------------------------------------------------

TOTAL_RECORDS = 100
RANDOM_SEED = 42
KG_PER_BAG = 60

# origin_country -> regions / varieties / farms / altitude band / score band / processes
ORIGINS: dict[str, dict[str, Any]] = {
    "Ethiopia": {
        "regions": ["Yirgacheffe", "Sidamo", "Guji", "Harrar", "Limu", "Jimma"],
        "varieties": ["Heirloom", "74110", "74112", "Kurume", "Gesha"],
        "farms": ["Konga Washing Station", "Chelbesa Mill", "Hambela Estate",
                  "Aricha Mill", "Bombe Sholi", "Adado Cooperative", "Duromina Cooperative"],
        "altitude": (1750, 2300),
        "score": (85.0, 92.5),
        "processes": ["Washed", "Natural", "Anaerobic Natural", "Honey"],
    },
    "Kenya": {
        "regions": ["Nyeri", "Kirinyaga", "Embu", "Muranga", "Kiambu"],
        "varieties": ["SL28", "SL34", "Ruiru 11", "Batian"],
        "farms": ["Kiambu Factory AA", "Gichathaini Factory", "Karimikui Factory",
                  "Thiriku Factory", "Ndaroini Factory", "Gatomboya Factory"],
        "altitude": (1550, 2100),
        "score": (84.5, 91.5),
        "processes": ["Washed", "Natural", "Anaerobic Natural"],
    },
    "Colombia": {
        "regions": ["Huila", "Narino", "Tolima", "Antioquia", "Cauca", "Quindio"],
        "varieties": ["Caturra", "Castillo", "Colombia", "Pink Bourbon", "Gesha", "Typica"],
        "farms": ["Finca La Esperanza", "Finca El Mirador", "Finca Los Naranjos",
                  "Hacienda La Pradera", "Finca El Diviso", "Finca Buenos Aires"],
        "altitude": (1450, 2050),
        "score": (83.0, 91.0),
        "processes": ["Washed", "Honey", "Natural", "Carbonic Maceration",
                      "Yeast-Inoculated Washed", "Anaerobic Natural"],
    },
    "Brazil": {
        "regions": ["Cerrado Mineiro", "Sul de Minas", "Mogiana", "Chapada Diamantina"],
        "varieties": ["Yellow Bourbon", "Mundo Novo", "Catuai", "Icatu", "Acaia"],
        "farms": ["Fazenda Santa Ines", "Fazenda Rainha", "Fazenda Sertao",
                  "Fazenda California", "Fazenda Passeio"],
        "altitude": (900, 1350),
        "score": (80.5, 87.5),
        "processes": ["Natural", "Pulped Natural", "Honey", "Washed"],
    },
    "Guatemala": {
        "regions": ["Antigua", "Huehuetenango", "Atitlan", "Coban", "Fraijanes"],
        "varieties": ["Bourbon", "Caturra", "Catuai", "Pacamara", "Typica"],
        "farms": ["Finca El Injerto", "Finca La Soledad", "Finca Santa Clara",
                  "Finca El Socorro", "Finca Bella Vista"],
        "altitude": (1350, 1950),
        "score": (83.0, 90.5),
        "processes": ["Washed", "Honey", "Natural", "Anaerobic Natural"],
    },
    "Costa Rica": {
        "regions": ["Tarrazu", "West Valley", "Central Valley", "Brunca", "Tres Rios"],
        "varieties": ["Caturra", "Villa Sarchi", "Catuai", "Gesha", "SL28"],
        "farms": ["Finca Don Mayo", "Las Lajas Micromill", "Finca La Pastora",
                  "Cerro San Luis", "Finca Genesis"],
        "altitude": (1200, 1900),
        "score": (84.0, 91.0),
        "processes": ["Washed", "Black Honey", "Red Honey", "Natural",
                      "Anaerobic Natural", "Carbonic Maceration"],
    },
    "Panama": {
        "regions": ["Boquete", "Volcan Candela", "Piedra de Candela"],
        "varieties": ["Gesha", "Catuai", "Typica", "Pacamara"],
        "farms": ["Hacienda La Esmeralda", "Finca Deborah", "Elida Estate",
                  "Finca Sophia", "Janson Family Estate"],
        "altitude": (1400, 1950),
        "score": (87.0, 94.5),
        "processes": ["Washed", "Natural", "Honey", "Carbonic Maceration"],
    },
    "Rwanda": {
        "regions": ["Nyamasheke", "Huye", "Gakenke", "Kirehe"],
        "varieties": ["Red Bourbon", "Jackson", "Mibirizi"],
        "farms": ["Gitesi Washing Station", "Nyarusiza Station", "Bumbogo Station",
                  "Kinini Washing Station"],
        "altitude": (1600, 2050),
        "score": (84.0, 90.0),
        "processes": ["Washed", "Natural", "Honey"],
    },
    "Burundi": {
        "regions": ["Kayanza", "Ngozi", "Muyinga", "Gitega"],
        "varieties": ["Red Bourbon", "Jackson", "Mibirizi"],
        "farms": ["Gaharo Hill Station", "Mpanga Station", "Nemba Washing Station",
                  "Yandaro Station"],
        "altitude": (1500, 1900),
        "score": (83.0, 89.0),
        "processes": ["Washed", "Natural", "Anaerobic Natural"],
    },
    "Indonesia": {
        "regions": ["Aceh Gayo", "Toraja", "Bali Kintamani", "Flores Bajawa", "Java Preanger"],
        "varieties": ["Typica", "Ateng", "S795", "Tim Tim", "Bourbon"],
        "farms": ["Gayo Highlands Cooperative", "Sapan Minanga Estate", "Kintamani Estate",
                  "Bajawa Cooperative", "Preanger Estate"],
        "altitude": (1100, 1750),
        "score": (82.0, 88.5),
        "processes": ["Wet-Hulled", "Washed", "Natural", "Honey"],
    },
    "Honduras": {
        "regions": ["Marcala", "Santa Barbara", "Copan", "Comayagua", "El Paraiso"],
        "varieties": ["Parainema", "Bourbon", "Catuai", "Lempira", "Pacas"],
        "farms": ["Finca El Puente", "Finca Los Andes", "Finca San Jeronimo",
                  "Beneficio Santa Rosa", "Finca La Union"],
        "altitude": (1200, 1800),
        "score": (82.0, 89.5),
        "processes": ["Washed", "Honey", "Natural", "Anaerobic Natural"],
    },
    "Peru": {
        "regions": ["Cajamarca", "Amazonas", "Cusco", "Junin", "San Martin"],
        "varieties": ["Typica", "Bourbon", "Caturra", "Pache", "Gesha"],
        "farms": ["Finca Churupampa", "Cenfrocafe Cooperative", "Finca Rodriguez de Mendoza",
                  "Valle Alto Cooperative", "Finca Tunki"],
        "altitude": (1300, 1950),
        "score": (82.0, 88.5),
        "processes": ["Washed", "Honey", "Natural"],
    },
    "El Salvador": {
        "regions": ["Apaneca-Ilamatepec", "Chalatenango", "Santa Ana", "Alotepec"],
        "varieties": ["Pacamara", "Bourbon", "Pacas", "Kenia", "Cuscatleco"],
        "farms": ["Finca Los Nogales", "Finca Malacara", "Finca Siberia",
                  "Finca El Carmen", "Finca La Ilusion"],
        "altitude": (1200, 1750),
        "score": (83.0, 90.0),
        "processes": ["Washed", "Honey", "Natural", "Anaerobic Natural"],
    },
    "Mexico": {
        "regions": ["Chiapas", "Oaxaca", "Veracruz", "Puebla"],
        "varieties": ["Typica", "Bourbon", "Mundo Novo", "Garnica", "Marsellesa"],
        "farms": ["Finca Argovia", "Finca Nueva Linda", "Finca Cafeteca",
                  "Union Ramal Santa Cruz", "Finca La Providencia"],
        "altitude": (1100, 1700),
        "score": (81.0, 87.5),
        "processes": ["Washed", "Natural", "Honey"],
    },
    "Yemen": {
        "regions": ["Haraaz", "Bani Matar", "Ismaili"],
        "varieties": ["Udaini", "Dawairi", "Tuffahi", "Jaadi"],
        "farms": ["Haraaz Highlands", "Bani Matar Terraces", "Al Mahwit Grove"],
        "altitude": (1800, 2400),
        "score": (85.0, 92.0),
        "processes": ["Natural", "Washed", "Anaerobic Natural"],
    },
    "Ecuador": {
        "regions": ["Loja", "Pichincha", "Zamora-Chinchipe"],
        "varieties": ["Sidra", "Typica Mejorado", "Bourbon", "Gesha"],
        "farms": ["Finca Maputo", "Hacienda La Papaya", "Finca Soledad", "Finca Cruz Loma"],
        "altitude": (1400, 2050),
        "score": (84.0, 91.5),
        "processes": ["Washed", "Natural", "Anaerobic Natural", "Carbonic Maceration"],
    },
    "Tanzania": {
        "regions": ["Mbeya", "Kilimanjaro", "Ruvuma", "Kigoma"],
        "varieties": ["Kent", "N39", "Bourbon", "Compact"],
        "farms": ["Ilomba Estate", "Blackburn Estate", "Mbimba Station", "Kanji Lalji Estate"],
        "altitude": (1400, 1900),
        "score": (83.0, 89.0),
        "processes": ["Washed", "Natural", "Honey"],
    },
    "Nicaragua": {
        "regions": ["Jinotega", "Matagalpa", "Nueva Segovia", "Dipilto"],
        "varieties": ["Maracaturra", "Java", "Caturra", "Pacamara", "Catuai"],
        "farms": ["Finca La Bastilla", "Finca Un Regalo de Dios", "Finca Los Congos",
                  "Finca El Suyatal", "Finca Mierisch"],
        "altitude": (1100, 1700),
        "score": (82.0, 89.0),
        "processes": ["Washed", "Honey", "Natural", "Anaerobic Natural"],
    },
}

HARVEST_YEARS = ["22/23", "23/24", "24/25"]

# Varieties and processes that carry a market premium.
PREMIUM_VARIETIES = {"Gesha", "Pacamara", "Sidra", "Pink Bourbon", "Maracaturra"}
PREMIUM_PROCESSES = {"Carbonic Maceration", "Anaerobic Natural", "Yeast-Inoculated Washed"}


def generate_inventory(total: int = TOTAL_RECORDS, seed: int = RANDOM_SEED) -> list[CoffeeLot]:
    """Build a deterministic dataset of specialty coffee lots.

    The same `seed` always yields the same records, so a Blockbrain agent gets
    identical answers across restarts and across serverless cold starts.
    """
    rng = random.Random(seed)
    countries = list(ORIGINS)
    lots: list[CoffeeLot] = []

    for item_id in range(1, total + 1):
        # Round-robin the origins so every country is represented.
        country = countries[(item_id - 1) % len(countries)]
        spec = ORIGINS[country]

        region = rng.choice(spec["regions"])
        variety = rng.choice(spec["varieties"])
        process = rng.choice(spec["processes"])
        farm = rng.choice(spec["farms"])

        alt_low, alt_high = spec["altitude"]
        altitude_masl = rng.randrange(alt_low, alt_high + 1, 10)

        score_low, score_high = spec["score"]
        cupping_score = round(rng.uniform(score_low, score_high) * 4) / 4  # quarter points

        # Price tracks cup score, with a premium for rare varieties and
        # experimental processing.
        premium = rng.uniform(1.6, 2.4) if variety in PREMIUM_VARIETIES else 1.0
        if process in PREMIUM_PROCESSES:
            premium *= rng.uniform(1.15, 1.35)
        base_price = 4.20 + (cupping_score - 80.0) ** 1.9 * 0.42
        price_per_kg_usd = round(base_price * premium * rng.uniform(0.94, 1.08), 2)

        # Volumes get scarcer as quality climbs.
        max_bags = 420 if cupping_score < 86 else 140 if cupping_score < 90 else 40
        stock_bags = rng.randint(4, max_bags)

        lots.append(
            CoffeeLot(
                id=item_id,
                name=f"{farm} {variety} {rng.choice(HARVEST_YEARS)}",
                origin_country=country,
                region=region,
                variety=variety,
                process=process,
                altitude_masl=altitude_masl,
                cupping_score=cupping_score,
                stock_bags=stock_bags,
                price_per_kg_usd=price_per_kg_usd,
            )
        )

    return lots


INVENTORY: list[CoffeeLot] = generate_inventory()
INVENTORY_BY_ID: dict[int, CoffeeLot] = {lot.id: lot for lot in INVENTORY}


def compute_statistics(lots: list[CoffeeLot]) -> InventoryStatistics:
    """Aggregate a list of lots into portfolio-wide and per-country figures."""
    scores = [lot.cupping_score for lot in lots]
    prices = [lot.price_per_kg_usd for lot in lots]
    total_bags = sum(lot.stock_bags for lot in lots)
    total_value = sum(lot.stock_bags * KG_PER_BAG * lot.price_per_kg_usd for lot in lots)

    grouped: dict[str, list[CoffeeLot]] = defaultdict(list)
    for lot in lots:
        grouped[lot.origin_country].append(lot)

    breakdown = [
        CountryBreakdown(
            origin_country=country,
            lot_count=len(country_lots),
            total_stock_bags=sum(lot.stock_bags for lot in country_lots),
            average_cupping_score=round(
                sum(lot.cupping_score for lot in country_lots) / len(country_lots), 2
            ),
            average_price_per_kg_usd=round(
                sum(lot.price_per_kg_usd for lot in country_lots) / len(country_lots), 2
            ),
        )
        for country, country_lots in grouped.items()
    ]
    # Biggest holdings first, then alphabetically so the order is stable.
    breakdown.sort(key=lambda entry: (-entry.lot_count, entry.origin_country))

    return InventoryStatistics(
        total_lots=len(lots),
        total_stock_bags=total_bags,
        total_stock_kg=round(total_bags * KG_PER_BAG, 2),
        average_cupping_score=round(sum(scores) / len(scores), 2),
        highest_cupping_score=max(scores),
        lowest_cupping_score=min(scores),
        average_price_per_kg_usd=round(sum(prices) / len(prices), 2),
        total_inventory_value_usd=round(total_value, 2),
        country_count=len(grouped),
        country_breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Specialty Coffee & Inventory API",
    description=(
        "Custom testing API with 100+ seeded specialty coffee inventory records "
        "and HTTP Basic Authentication.\n\n"
        "Registered as a custom External API on the Blockbrain platform. Every "
        "`/api/v1/*` endpoint requires HTTP Basic credentials; send them with the "
        "`Authorization: Basic <base64(username:password)>` header, which the "
        "Blockbrain registry does automatically when its Authentication field is "
        "set to `Basic`.\n\n"
        "The dataset is generated deterministically from a fixed seed, so the "
        "same query always returns the same records."
    ),
    # 2.0.0: HTTP Basic replaced OAuth2 Bearer, and the list response renamed
    # `limit` to `page_size` - both breaking changes for earlier clients.
    version="2.0.0",
    contact={
        "name": "PhamThuyAnh",
        "url": "https://github.com/PhamThuyAnh/fastapi-blockbrain-inventory-api",
    },
    openapi_tags=[
        {
            "name": "inventory",
            "description": "Browse and inspect individual specialty coffee lots.",
        },
        {
            "name": "statistics",
            "description": "Aggregated figures across the whole inventory.",
        },
    ],
)

# When PUBLIC_BASE_URL is set, advertise it in the OpenAPI `servers` block so a
# consumer that fetches /openapi.json knows the absolute base URL to call.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
if PUBLIC_BASE_URL:
    app.servers = [{"url": PUBLIC_BASE_URL, "description": "Public base URL"}]


# Kept out of the OpenAPI schema on purpose: the document that Blockbrain reads
# should contain only the three callable tools, so agent routing stays sharp.
@app.get("/", include_in_schema=False)
async def root() -> dict[str, Any]:
    return {
        "service": app.title,
        "version": app.version,
        "records": len(INVENTORY),
        "authentication": "HTTP Basic",
        "openapi": "/openapi.json",
        "docs": "/docs",
    }


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/v1/inventory",
    response_model=PaginatedInventory,
    operation_id="listInventory",
    tags=["inventory"],
    summary="List specialty coffee lots with pagination, filtering and search",
    description=(
        "Returns a page of specialty coffee inventory records. Combine `country`, "
        "`min_score` and `search` to narrow the results; the filters are applied "
        "together (logical AND). Use `page` and `limit` to walk through the "
        "matches, and read `total_pages` from the response to know when to stop."
    ),
    responses={401: {"description": "Missing or invalid HTTP Basic credentials."}},
)
async def list_inventory(
    username: AuthenticatedUser,
    page: Annotated[
        int,
        Query(ge=1, description="Page number to return, starting at 1."),
    ] = 1,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum records per page, between 1 and 100."),
    ] = 10,
    country: Annotated[
        Optional[str],
        Query(
            description=(
                "Filter by producing country, matched exactly but case-insensitively. "
                "Examples: Ethiopia, Kenya, Colombia, Panama, Brazil, Guatemala."
            ),
            examples=["Ethiopia"],
        ),
    ] = None,
    min_score: Annotated[
        Optional[float],
        Query(
            ge=0,
            le=100,
            description=(
                "Return only lots whose SCA cupping score is greater than or equal "
                "to this value. Specialty grade starts at 80; use 88 or above for "
                "the top of the portfolio."
            ),
            examples=[88.0],
        ),
    ] = None,
    search: Annotated[
        Optional[str],
        Query(
            min_length=1,
            description=(
                "Free-text search. Case-insensitive substring match against lot "
                "name, region, variety, process and origin country. Examples: "
                "gesha, anaerobic, yirgacheffe."
            ),
            examples=["gesha"],
        ),
    ] = None,
) -> PaginatedInventory:
    results = INVENTORY

    if country:
        needle = country.strip().casefold()
        results = [lot for lot in results if lot.origin_country.casefold() == needle]

    if min_score is not None:
        results = [lot for lot in results if lot.cupping_score >= min_score]

    if search:
        term = search.strip().casefold()
        results = [
            lot
            for lot in results
            if term in lot.name.casefold()
            or term in lot.region.casefold()
            or term in lot.variety.casefold()
            or term in lot.process.casefold()
            or term in lot.origin_country.casefold()
        ]

    total_records = len(results)
    total_pages = math.ceil(total_records / limit) if total_records else 0
    start = (page - 1) * limit

    return PaginatedInventory(
        total_records=total_records,
        page=page,
        page_size=limit,
        total_pages=total_pages,
        data=results[start : start + limit],
    )


@app.get(
    "/api/v1/statistics",
    response_model=InventoryStatistics,
    operation_id="getInventoryStatistics",
    tags=["statistics"],
    summary="Aggregated statistics across the whole coffee inventory",
    description=(
        "Returns portfolio-wide totals - lot count, bags and green weight on hand, "
        "average, highest and lowest cupping scores, average price per kilogram "
        "and total inventory value - together with the same figures broken down "
        "per origin country, ordered by lot count descending. Takes no parameters "
        "and always covers the entire inventory."
    ),
    responses={401: {"description": "Missing or invalid HTTP Basic credentials."}},
)
async def get_inventory_statistics(username: AuthenticatedUser) -> InventoryStatistics:
    return compute_statistics(INVENTORY)


@app.get(
    "/api/v1/inventory/{item_id}",
    response_model=CoffeeLot,
    operation_id="getInventoryItem",
    tags=["inventory"],
    summary="Retrieve a single coffee lot by its numeric ID",
    description=(
        "Fetches one specialty coffee lot by its integer identifier. Valid IDs run "
        "from 1 to 100. Use `listInventory` first if you need to discover an ID."
    ),
    responses={
        401: {"description": "Missing or invalid HTTP Basic credentials."},
        404: {"description": "No coffee lot exists with the requested ID."},
    },
)
async def get_inventory_item(
    username: AuthenticatedUser,
    item_id: Annotated[
        int,
        Path(
            ge=1,
            description="Identifier of the coffee lot to retrieve, between 1 and 100.",
            examples=[7],
        ),
    ],
) -> CoffeeLot:
    lot = INVENTORY_BY_ID.get(item_id)
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item {item_id} not found. Valid IDs are 1 to {len(INVENTORY)}.",
        )
    return lot


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
