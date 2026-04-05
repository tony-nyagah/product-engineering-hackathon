from contextlib import asynccontextmanager

from cache import close_redis, init_redis
from database import Base, engine
from fastapi import FastAPI
from routers import inventory, products, reports, sales, users


@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_redis()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="POS System",
    description="Point of Sale -- Scalability Demo",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(sales.router, prefix="/api/sales", tags=["sales"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(users.router, prefix="/api/users", tags=["users"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
