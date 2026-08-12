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
    credits = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="document")
    price_usd = Column(Float, nullable=False)
    image_url = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="product")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # nullable for pure custom orders
    amount_usd = Column(Float, nullable=False)
    status = Column(String, default="pending")          # pending | paid | credited
    notes = Column(String, nullable=True)               # what the user typed
    payment_type = Column(String, default="btc")        # btc | credits
    delivery_message = Column(Text, nullable=True)      # message admin writes when delivering
    delivery_file = Column(String, nullable=True)       # file admin uploads when delivering
    custom_title = Column(String, nullable=True)        # e.g. "Order SMTP"
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")

class CustomService(Base):
    __tablename__ = "custom_services"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)              # e.g. Order SMTP
    placeholder = Column(String, default="")            # example text shown to user
    price_usd = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
