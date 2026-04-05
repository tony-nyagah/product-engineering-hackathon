import asyncio

from cache import cache_delete_pattern
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import Product, Sale, SaleItem
from schemas import SaleCreate, SaleResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/", response_model=SaleResponse, status_code=201)
async def create_sale(sale_data: SaleCreate, db: AsyncSession = Depends(get_db)):
    product_ids = [item.product_id for item in sale_data.items]
    result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products_by_id = {product.id: product for product in result.scalars().all()}

    total = 0.0
    line_items = []
    for item in sale_data.items:
        product = products_by_id.get(item.product_id)
        if not product:
            raise HTTPException(
                status_code=404, detail=f"Product {item.product_id} not found"
            )
        if product.stock_quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock")
        total += product.price * item.quantity
        line_items.append((product, item.quantity))
    sale = Sale(cashier_id=sale_data.cashier_id, total=round(total, 2))
    db.add(sale)
    await db.flush()
    for product, quantity in line_items:
        db.add(
            SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=product.price,
            )
        )
        product.stock_quantity -= quantity
    await db.commit()
    await db.refresh(sale)
    asyncio.create_task(cache_delete_pattern("inventory:*"))
    asyncio.create_task(cache_delete_pattern("reports:*"))
    return sale


@router.get("/", response_model=list[SaleResponse])
async def list_sales(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Sale).order_by(Sale.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(sale_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sale).where(Sale.id == sale_id))
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale
