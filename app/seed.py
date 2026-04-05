import asyncio
import random

from database import Base
from faker import Faker
from models import Product, Sale, SaleItem, User
from settings import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

fake = Faker()
CATEGORIES = [
    "beverages",
    "snacks",
    "electronics",
    "clothing",
    "fresh-produce",
    "dairy",
    "bakery",
]


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        print("Seeding users...")
        for i in range(1, 6):
            session.add(User(username=f"cashier_{i}", role="cashier"))
        session.add(User(username="admin", role="admin"))
        await session.commit()

        cashiers_q = await session.execute(select(User).where(User.role == "cashier"))
        cashiers = cashiers_q.scalars().all()

        print("Seeding 50 products...")
        for i in range(1, 51):
            session.add(
                Product(
                    name=f"{fake.word().capitalize()} {fake.word().capitalize()}",
                    price=round(random.uniform(0.99, 149.99), 2),
                    category=random.choice(CATEGORIES),
                    sku=f"SKU-{i:04d}",
                    stock_quantity=99999,
                )
            )
        await session.commit()

        products_q = await session.execute(select(Product))
        products = products_q.scalars().all()

        print("Seeding 2,000 historical sales (makes /reports/summary expensive)...")
        BATCHES, PER_BATCH = 20, 100
        for batch in range(BATCHES):
            for _ in range(PER_BATCH):
                cashier = random.choice(cashiers)
                chosen = random.sample(products, k=random.randint(1, 4))
                sale = Sale(cashier_id=cashier.id, total=0.0)
                session.add(sale)
                await session.flush()
                total = 0.0
                for product in chosen:
                    qty = random.randint(1, 3)
                    session.add(
                        SaleItem(
                            sale_id=sale.id,
                            product_id=product.id,
                            quantity=qty,
                            unit_price=product.price,
                        )
                    )
                    total += product.price * qty
                sale.total = round(total, 2)
            await session.commit()
            print(f"   Batch {batch + 1}/{BATCHES} done")

        print("\nSeed complete: 6 users, 50 products, 2,000 historical sales")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
