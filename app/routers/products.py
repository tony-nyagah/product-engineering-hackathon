from cache import cache_delete_pattern, cache_get, cache_set
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Response
from models import Product
from schemas import ProductCreate, ProductResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/", response_model=list[ProductResponse])
async def list_products(response: Response, db: AsyncSession = Depends(get_db)):
    cached = await cache_get("products:all")
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached
    result = await db.execute(select(Product).order_by(Product.id))
    products = result.scalars().all()
    data = [ProductResponse.model_validate(p).model_dump(mode="json") for p in products]
    await cache_set("products:all", data, ttl=300)
    response.headers["X-Cache"] = "MISS"
    return data


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int, response: Response, db: AsyncSession = Depends(get_db)
):
    cached = await cache_get(f"products:{product_id}")
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    data = ProductResponse.model_validate(product).model_dump(mode="json")
    await cache_set(f"products:{product_id}", data, ttl=300)
    response.headers["X-Cache"] = "MISS"
    return data


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(product_in: ProductCreate, db: AsyncSession = Depends(get_db)):
    product = Product(**product_in.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    await cache_delete_pattern("products:*")
    return product
