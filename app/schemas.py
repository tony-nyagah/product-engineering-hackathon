from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProductBase(BaseModel):
    name: str
    price: float
    category: str
    sku: str
    stock_quantity: int = 99999


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: int
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: int = 1


class SaleItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float
    model_config = {"from_attributes": True}


class SaleCreate(BaseModel):
    cashier_id: int
    items: list[SaleItemCreate]


class SaleResponse(BaseModel):
    id: int
    cashier_id: int
    total: float
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class InventoryItem(BaseModel):
    id: int
    name: str
    sku: str
    stock_quantity: int
    model_config = {"from_attributes": True}


class InventoryUpdate(BaseModel):
    stock_quantity: int


class UserCreate(BaseModel):
    username: str
    role: str = "cashier"


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
