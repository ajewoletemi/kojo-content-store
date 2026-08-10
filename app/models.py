from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, default="")
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    price_btc = Column(Float, nullable=False)          # Price in BTC
    price_usd_approx = Column(Float, default=0.0)       # Optional display only
    category = Column(String, default="document")       # document | software | service
    file_path = Column(String, default="")              # path to uploaded file (empty for services)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="product")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    amount_btc = Column(Float, nullable=False)
    status = Column(String, default="pending")          # pending | paid | cancelled
    tx_id = Column(String, default="")                  # optional Bitcoin tx id provided by user
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")
