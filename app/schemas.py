from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class User(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True

class Product(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price_usd: float
    image_url: Optional[str] = None

    class Config:
        from_attributes = True

class Order(BaseModel):
    id: int
    amount_usd: float
    notes: Optional[str] = None
    status: str
    product: Product

    class Config:
        from_attributes = True
