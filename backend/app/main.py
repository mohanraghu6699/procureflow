import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.logging_config import configure_logging
from app.routers import auth, dashboard, deliveries, master_data, purchase_orders, purchase_requests

configure_logging()
logger = logging.getLogger("procureflow.http")

app = FastAPI(
    title="ProcureFlow API",
    description="Purchase-to-Pay management API: Purchase Request -> Approval -> Purchase Order -> Delivery -> Completion.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("[%s] %s %s crashed", request_id, request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id

    level = logging.ERROR if response.status_code >= 500 else logging.INFO
    if request.url.path == "/api/health":
        level = logging.DEBUG  # probes would otherwise drown out real traffic
    logger.log(
        level, "[%s] %s %s -> %d (%.0f ms)", request_id, request.method, request.url.path, response.status_code, elapsed_ms
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # errors() can hold Decimals (gt=0) or exception objects (custom validators), which plain JSON can't encode.
    errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
    return JSONResponse(status_code=422, content={"detail": "Validation error", "errors": errors})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(master_data.router)
app.include_router(purchase_requests.router)
app.include_router(purchase_orders.router)
app.include_router(deliveries.router)
app.include_router(dashboard.router)
