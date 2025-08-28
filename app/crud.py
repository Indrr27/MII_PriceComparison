# app/crud.py
from sqlalchemy.orm import Session
from . import models
from typing import List, Optional

class StoreCRUD:
    @staticmethod
    def create_store(db: Session, store_data: dict) -> models.Store:
        db_store = models.Store(**store_data)
        db.add(db_store)
        db.commit()
        db.refresh(db_store)
        return db_store
    
    @staticmethod
    def get_store_by_name(db: Session, name: str) -> Optional[models.Store]:
        return db.query(models.Store).filter(models.Store.name == name).first()
    
    @staticmethod
    def get_primary_store(db: Session) -> Optional[models.Store]:
        return db.query(models.Store).filter(models.Store.is_primary == True).first()

class ProductCRUD:
    @staticmethod
    def create_product(db: Session, product_data: dict) -> models.Product:
        db_product = models.Product(**product_data)
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product
    
    @staticmethod
    def get_product(db: Session, product_id: int) -> Optional[models.Product]:
        """Get a single product by ID"""
        return db.query(models.Product).filter(models.Product.id == product_id).first()
    
    @staticmethod
    def get_products_by_store(db: Session, store_id: int) -> List[models.Product]:
        return db.query(models.Product).filter(
            models.Product.store_id == store_id,
            models.Product.is_active == True
        ).all()
    
    @staticmethod
    def update_product(db: Session, product_id: int, update_data: dict) -> Optional[models.Product]:
        db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
        if db_product:
            for key, value in update_data.items():
                setattr(db_product, key, value)
            db.commit()
            db.refresh(db_product)
        return db_product

class PriceCRUD:
    @staticmethod
    def add_price(db: Session, product_id: int, price: float, sale_price: float = None) -> models.Price:
        db_price = models.Price(
            product_id=product_id,
            price=price,
            sale_price=sale_price,
            is_on_sale=sale_price is not None
        )
        db.add(db_price)
        db.commit()
        db.refresh(db_price)
        return db_price
    
    @staticmethod
    def get_latest_price(db: Session, product_id: int) -> Optional[models.Price]:
        return db.query(models.Price).filter(
            models.Price.product_id == product_id
        ).order_by(models.Price.scraped_at.desc()).first()
    
    @staticmethod
    def get_price_history(db: Session, product_id: int, limit: int = 30) -> List[models.Price]:
        return db.query(models.Price).filter(
            models.Price.product_id == product_id
        ).order_by(models.Price.scraped_at.desc()).limit(limit).all()

class ProductMatchCRUD:
    @staticmethod
    def create_match(db: Session, primary_product_id: int, matched_product_id: int, 
                    confidence_score: float, match_type: str = "similar") -> models.ProductMatch:
        db_match = models.ProductMatch(
            primary_product_id=primary_product_id,
            matched_product_id=matched_product_id,
            confidence_score=confidence_score,
            match_type=match_type
        )
        db.add(db_match)
        db.commit()
        db.refresh(db_match)
        return db_match
    
    @staticmethod
    def get_matches_for_product(db: Session, product_id: int) -> List[models.ProductMatch]:
        return db.query(models.ProductMatch).filter(
            models.ProductMatch.primary_product_id == product_id
        ).order_by(models.ProductMatch.confidence_score.desc()).all()
    
    @staticmethod
    def get_matches_by_store(db: Session, store_id: int) -> List[models.ProductMatch]:
        """Get all matches for products from a specific store"""
        return db.query(models.ProductMatch).join(
            models.Product, models.ProductMatch.primary_product_id == models.Product.id
        ).filter(
            models.Product.store_id == store_id
        ).order_by(models.ProductMatch.confidence_score.desc()).all()
    
    @staticmethod
    def delete_matches_by_store(db: Session, store_id: int) -> int:
        """Delete all existing matches for a store (useful when re-running matching)"""
        deleted_count = db.query(models.ProductMatch).join(
            models.Product, models.ProductMatch.primary_product_id == models.Product.id
        ).filter(
            models.Product.store_id == store_id
        ).delete(synchronize_session=False)
        db.commit()
        return deleted_count
    
    @staticmethod
    def get_match_statistics(db: Session, store_id: int) -> dict:
        """Get matching statistics for a store"""
        matches = ProductMatchCRUD.get_matches_by_store(db, store_id)
        
        stats = {
            'total_matches': len(matches),
            'exact_matches': 0,
            'similar_matches': 0,
            'substitute_matches': 0,
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0
        }
        
        for match in matches:
            # Count by match type
            if match.match_type == 'exact':
                stats['exact_matches'] += 1
            elif match.match_type == 'similar':
                stats['similar_matches'] += 1
            elif match.match_type == 'substitute':
                stats['substitute_matches'] += 1
            
            # Count by confidence level
            if match.confidence_score >= 0.9:
                stats['high_confidence'] += 1
            elif match.confidence_score >= 0.75:
                stats['medium_confidence'] += 1
            else:
                stats['low_confidence'] += 1
        
        return stats