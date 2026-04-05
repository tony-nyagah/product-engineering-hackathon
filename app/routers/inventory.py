from cache import cache_delete_pattern, cache_get, cache_set
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Response
from models import Product
from schemas import InventoryItem, InventoryUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/", response_model=list[InventoryItem])
async def get_inventory(response: Response, db: AsyncSession = Depends(get_db)):
    cached = await cache_get("inventory:all")
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached
    result = await db.execute(
        select(Product.id, Product.name, Product.sku, Product.stock_quantity).order_by(
            Product.id
        )
    )
    data = [
        {"id": r.id, "name": r.name, "sku": r.sku, "stock_quantity": r.stock_quantity}
        for r in result.all()
    ]
    await cache_set("inventory:all", data, ttl=30)
    response.headers["X-Cache"] = "MISS"
    return data


@router.patch("/{product_id}", response_model=InventoryItem)
async def update_stock(
    product_id: int, update: InventoryUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.stock_quantity = update.stock_quantity
    await db.commit()
    await db.refresh(product)
    await cache_delete_pattern("inventory:*")
    await cache_delete_pattern(f"products:{product_id}")
    await cache_delete_pattern("products:all")
    return product
