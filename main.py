from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import time
import base64
import math

app = FastAPI()

# ------------------------
# CORS
# ------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# CONFIG
# ------------------------

TOTAL_ORDERS = 57
RATE_LIMIT = 15
WINDOW = 10

orders_catalog = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# idempotency store
idempotency_store = {}

# rate limit buckets
client_buckets = {}


# ==========================================================
# 1. IDEMPOTENT POST
# ==========================================================

@app.post("/orders", status_code=201)
def create_order(
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid4())
    }

    idempotency_store[idempotency_key] = order

    return order


# ==========================================================
# 2. CURSOR PAGINATION
# ==========================================================

@app.get("/orders")
def get_orders(limit: int = 10, cursor: str = None):

    limit = max(1, limit)

    if cursor is None:
        start = 0
    else:
        try:
            start = int(
                base64.b64decode(cursor.encode()).decode()
            )
        except:
            raise HTTPException(400, "Invalid Cursor")

    end = min(start + limit, TOTAL_ORDERS)

    items = orders_catalog[start:end]

    if end >= TOTAL_ORDERS:
        next_cursor = ""
    else:
        next_cursor = base64.b64encode(
            str(end).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }


# ==========================================================
# 3. RATE LIMIT
# ==========================================================

@app.middleware("http")
async def rate_limit(request, call_next):

    client = request.headers.get("x-client-id")

    if client:

        now = time.time()

        bucket = client_buckets.setdefault(client, [])

        bucket[:] = [t for t in bucket if now - t < WINDOW]

        if len(bucket) >= RATE_LIMIT:

            retry_after = math.ceil(WINDOW - (now - bucket[0]))

            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={
                    "Retry-After": str(retry_after)
                }
            )

        bucket.append(now)

    return await call_next(request)
