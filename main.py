"""
Specialty Coffee Inventory API
==============================

A FastAPI service exposing a seeded, in-memory catalogue of specialty coffee
lots behind OAuth2 Password Bearer (JWT) authentication.

Run locally:
    uvicorn main:app --reload

Interactive docs:
    http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import hashlib
import math
import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Security configuration
#
# NOTE: SECRET_KEY is hard-coded here so the demo runs out of the box. In any
# real deployment load it from the environment (e.g. os.environ["SECRET_KEY"])
# and never commit it.
# ---------------------------------------------------------------------------

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

_PWD_SALT = b"specialty-coffee-demo-salt"


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 hash. Stdlib-only so the demo needs no extra dependency."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _PWD_SALT, 100_000).hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return secrets.compare_digest(hash_password(plain_password), hashed_password)


# Demo user store. Replace with a real database in production.
FAKE_USERS_DB: dict[str, dict[str, Any]] = {
    "asher": {
        "username": "asher",
        "full_name": "Asher Pham",
        "email": "asher@example.com",
        "hashed_password": hash_password("testpassword123"),
        "disabled": False,
    }
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ---------------------------------------------------------------------------
# Pydantic v2 models
# ---------------------------------------------------------------------------


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds.")


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    disabled: bool = False


class UserInDB(User):
    hashed_password: str


class CoffeeLot(BaseModel):
    """A single green-coffee lot held in inventory."""

    id: int = Field(description="Stable inventory identifier.", examples=[1])
    name: str = Field(description="Lot name: farm or washing station plus variety and harvest.")
    origin_country: str
    region: str
    variety: str
    process: str
    altitude_masl: int = Field(description="Growing altitude in metres above sea level.")
    cupping_score: float = Field(description="SCA cupping score; 80+ is specialty grade.")
    stock_bags: int = Field(description="Bags on hand (60 kg each).")
    price_per_kg_usd: float = Field(description="Wholesale price per kilogram in USD.")


class PaginatedInventory(BaseModel):
    page: int
    limit: int
    total_records: int
    total_pages: int
    data: list[CoffeeLot]


# ---------------------------------------------------------------------------
# Seeded in-memory dataset
# ---------------------------------------------------------------------------

TOTAL_RECORDS = 120
RANDOM_SEED = 42

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

    The same `seed` always yields the same records, so clients and tests can
    rely on stable IDs and values across restarts.
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


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------


def get_user(username: str) -> Optional[UserInDB]:
    record = FAKE_USERS_DB.get(username)
    return UserInDB(**record) if record else None


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = get_user(username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user(token_data.username or "")
    if user is None:
        raise credentials_exception
    return User(**user.model_dump(exclude={"hashed_password"}))


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Specialty Coffee Inventory API",
    description=(
        "OAuth2 Password Bearer (JWT) protected access to a seeded catalogue of "
        f"{TOTAL_RECORDS} specialty coffee lots.\n\n"
        "**Demo credentials:** `asher` / `testpassword123`\n\n"
        "Use the **Authorize** button above, or POST form-encoded credentials "
        "to `/token`."
    ),
    version="1.0.0",
    contact={"name": "PhamThuyAnh", "url": "https://github.com/PhamThuyAnh"},
)


@app.get("/", tags=["meta"], summary="Service metadata")
async def root() -> dict[str, Any]:
    return {
        "service": app.title,
        "version": app.version,
        "records": len(INVENTORY),
        "docs": "/docs",
        "token_url": "/token",
    }


@app.get("/health", tags=["meta"], summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/token", response_model=Token, tags=["auth"], summary="Exchange credentials for a JWT")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """OAuth2 password flow. Send `username` and `password` as **form data**."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.get("/api/v1/users/me", response_model=User, tags=["auth"], summary="Current token owner")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user


@app.get(
    "/api/v1/inventory",
    response_model=PaginatedInventory,
    tags=["inventory"],
    summary="List coffee lots (paginated, filterable)",
)
async def list_inventory(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Records per page (max 100).")] = 10,
    country: Annotated[
        Optional[str],
        Query(description="Exact origin country, case-insensitive, e.g. `Ethiopia`."),
    ] = None,
    min_score: Annotated[
        Optional[float],
        Query(ge=0, le=100, description="Only lots with `cupping_score` >= this value."),
    ] = None,
    search: Annotated[
        Optional[str],
        Query(
            min_length=1,
            description="Case-insensitive substring match across name, region, "
            "variety, process and origin country.",
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
        page=page,
        limit=limit,
        total_records=total_records,
        total_pages=total_pages,
        data=results[start : start + limit],
    )


@app.get(
    "/api/v1/inventory/{item_id}",
    response_model=CoffeeLot,
    tags=["inventory"],
    summary="Fetch a single coffee lot by ID",
    responses={404: {"description": "No lot with that ID."}},
)
async def get_inventory_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CoffeeLot:
    lot = INVENTORY_BY_ID.get(item_id)
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item {item_id} not found",
        )
    return lot


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
