from fastapi import FastAPI, Header, Response, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uuid import uuid4
import base64
import math
import time

app = FastAPI()

# ----------------------------
# CORS
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# CONFIG
# ----------------------------
TOTAL_ORDERS = 57
RATE_LIMIT = 15
WINDOW = 10

orders_catalog = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

idempotency_store = {}
client_requests = {}

# ----------------------------
# ROOT
# ----------------------------
@app.get("/")
def root():
    return {
        "status": "running",
        "service": "Orders API"
    }

# ----------------------------
# RATE LIMIT MIDDLEWARE
# ----------------------------
@app.middleware("http")
async def rate_limit(request: Request, call_next):

    client_id = request.headers.get("x-client-id")

    if client_id:
        now = time.time()

        bucket = client_requests.setdefault(client_id, [])

        # Remove expired timestamps
        bucket[:] = [t for t in bucket if now - t < WINDOW]

        if len(bucket) >= RATE_LIMIT:
            retry_after = max(
                1,
                math.ceil(WINDOW - (now - bucket[0]))
            )

            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded"
                },
                headers={
                    "Retry-After": str(retry_after)
                }
            )

        bucket.append(now)

    response = await call_next(request)
    return response

# ----------------------------
# IDEMPOTENT POST
# ----------------------------
@app.post("/orders", status_code=201)
def create_order(
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid4())
    }

    idempotency_store[idempotency_key] = order

    return order

# ----------------------------
# CURSOR PAGINATION
# ----------------------------
@app.get("/orders")
def get_orders(
    limit: int = 10,
    cursor: str | None = None
):

    if limit < 1:
        limit = 1

    start = 0

    if cursor:
        try:
            start = int(
                base64.b64decode(cursor).decode()
            )
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid cursor"
            )

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
