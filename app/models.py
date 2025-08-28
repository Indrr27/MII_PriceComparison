# app/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    website = Column(String(255))
    location = Column(String(255))
    store_type = Column(String(100))  # "Indian Grocery", "Supermarket", etc.
    is_primary = Column(Boolean, default=False)  # True for Made in India Grocery
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    products = relationship("Product", back_populates="store")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    name = Column(String(500), nullable=False)
    brand = Column(String(255))
    size = Column(String(100))
    category = Column(String(255))
    url = Column(Text)
    sku = Column(String(100))  # Store's internal SKU if available
    barcode = Column(String(50))  # UPC/EAN if available
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="products")
    prices = relationship("Price", back_populates="product")
    product_matches = relationship("ProductMatch", foreign_keys="ProductMatch.primary_product_id")

class Price(Base):
    __tablename__ = "prices"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    sale_price = Column(Float)  # If on sale
    is_on_sale = Column(Boolean, default=False)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="prices")

class ProductMatch(Base):
    """Stores AI-matched products between stores"""
    __tablename__ = "product_matches"
    
    id = Column(Integer, primary_key=True, index=True)
    primary_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)  # Made in India product
    matched_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)  # Competitor product
    confidence_score = Column(Float, nullable=False)  # AI matching confidence (0.0-1.0)
    match_type = Column(String(50))  # "exact", "similar", "substitute"
    verified = Column(Boolean, default=False)  # Manual verification
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    primary_product = relationship("Product", foreign_keys=[primary_product_id])
    matched_product = relationship("Product", foreign_keys=[matched_product_id])