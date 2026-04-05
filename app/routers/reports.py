from datetime import date

from cache import cache_get, cache_set
from database import get_db
from fastapi import APIRouter, Depends, Response
from models import Product, Sale, SaleItem
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/summary")
async def get_summary(response: Response, db: AsyncSession = Depends(get_db)):
    cached = await cache_get("reports:summary")
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached
    today = date.today()
    totals = await db.execute(
        select(func.count(Sale.id), func.coalesce(func.sum(Sale.total), 0.0)).where(
            func.date(Sale.created_at) == today
        )
    )
    count, revenue = totals.one()
    top = await db.execute(
        select(
            Product.name,
            func.sum(SaleItem.quantity).label("units_sold"),
            func.sum(SaleItem.quantity * SaleItem.unit_price).label("revenue"),
        )
        .join(SaleItem, Product.id == SaleItem.product_id)
        .group_by(Product.id, Product.name)
        .order_by(desc("units_sold"))
        .limit(5)
    )
    top_products = [
        {
            "name": r.name,
            "units_sold": int(r.units_sold),
            "revenue": round(float(r.revenue), 2),
        }
        for r in top.all()
    ]
    data = {
        "date": str(today),
        "sales_today": int(count),
        "revenue_today": round(float(revenue), 2),
        "top_products": top_products,
    }
    await cache_set("reports:summary", data, ttl=60)
    response.headers["X-Cache"] = "MISS"
    return data
