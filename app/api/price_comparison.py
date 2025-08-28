# app/api/price_comparison.py
# API endpoints for the price comparison dashboard with categories and normalized prices

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime
import re
from app.database import get_db
from app.models import Store, Product, Price, ProductMatch
from app.crud import StoreCRUD, ProductCRUD, PriceCRUD

router = APIRouter(prefix="/api/price-comparison", tags=["price-comparison"])

def extract_normalized_price(product_name: str, price: float) -> Dict:
    """Extract size and calculate normalized price per 100g/100ml"""
    
    # patterns for different size formats
    patterns = [
        (r'(\d+(?:\.\d+)?)\s*kg\b', 1000, 'g'),
        (r'(\d+(?:\.\d+)?)\s*g\b', 1, 'g'),
        (r'(\d+(?:\.\d+)?)\s*lb\b', 453.592, 'g'),
        (r'(\d+(?:\.\d+)?)\s*oz\b', 28.3495, 'g'),
        (r'(\d+(?:\.\d+)?)\s*l\b', 1000, 'ml'),
        (r'(\d+(?:\.\d+)?)\s*ml\b', 1, 'ml'),
        (r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(g|ml|kg|l)', None, None),  # multi-pack
    ]
    
    normalized_price = None
    unit = None
    extracted_size = None
    
    name_lower = product_name.lower()
    
    for pattern, multiplier, unit_type in patterns:
        match = re.search(pattern, name_lower)
        if match:
            if pattern.startswith(r'(\d+)\s*x'):  # multi-pack
                quantity = float(match.group(1))
                size_per_item = float(match.group(2))
                item_unit = match.group(3)
                
                # convert to base unit
                if item_unit in ['kg', 'l']:
                    total_size = quantity * size_per_item * 1000
                else:
                    total_size = quantity * size_per_item
                
                unit = 'g' if item_unit in ['g', 'kg'] else 'ml'
                normalized_price = (price / total_size) * 100
                extracted_size = f"{match.group(1)}x{match.group(2)}{match.group(3)}"
            else:
                size = float(match.group(1))
                total_grams = size * multiplier
                normalized_price = (price / total_grams) * 100 if total_grams > 0 else None
                unit = unit_type
                extracted_size = f"{match.group(0)}"
            break
    
    return {
        "normalized_price": normalized_price,
        "unit": unit,
        "size": extracted_size
    }

def categorize_product(product_name: str, category: str = None) -> str:
    """Categorize products based on name and existing category"""
    
    name_lower = product_name.lower()
    
    # category keywords
    categories = {
        'Rice & Grains': ['rice', 'basmati', 'quinoa', 'oats', 'barley', 'wheat', 'grain'],
        'Flour': ['flour', 'atta', 'besan', 'maida', 'chakki'],
        'Dals & Lentils': ['dal', 'lentil', 'toor', 'urad', 'moong', 'chana', 'rajma', 'masoor'],
        'Spices & Masala': ['spice', 'masala', 'powder', 'turmeric', 'cumin', 'coriander', 'chili', 'pepper', 'garam'],
        'Oil & Ghee': ['oil', 'ghee', 'vanaspati', 'butter'],
        'Snacks': ['chips', 'namkeen', 'bhujia', 'mixture', 'papad', 'cookies', 'biscuit'],
        'Sauces & Pickles': ['sauce', 'chutney', 'pickle', 'achaar', 'paste', 'ketchup'],
        'Beverages': ['tea', 'coffee', 'juice', 'drink', 'lassi', 'soda'],
        'Sweets': ['sweet', 'mithai', 'laddu', 'barfi', 'halwa', 'gulab'],
        'Dairy': ['milk', 'paneer', 'yogurt', 'cheese', 'cream', 'dahi'],
        'Frozen': ['frozen', 'paratha', 'naan', 'samosa', 'ice cream'],
        'Fresh Produce': ['fresh', 'vegetable', 'fruit', 'onion', 'potato', 'tomato'],
    }
    
    # check existing category first
    if category:
        for cat_name, keywords in categories.items():
            if any(keyword in category.lower() for keyword in keywords):
                return cat_name
    
    # check product name
    for cat_name, keywords in categories.items():
        if any(keyword in name_lower for keyword in keywords):
            return cat_name
    
    return 'Other'

@router.get("/stores")
async def get_stores(db: Session = Depends(get_db)):
    """Get all stores with their product counts"""
    stores = db.query(Store).all()
    result = []
    
    for store in stores:
        # count active products
        product_count = db.query(Product).filter(
            Product.store_id == store.id,
            Product.is_active == True
        ).count()
        
        # count matched products for competitors
        matched_count = 0
        if not store.is_primary:
            matched_count = db.query(ProductMatch).join(
                Product, Product.id == ProductMatch.matched_product_id
            ).filter(
                Product.store_id == store.id
            ).count()
        
        result.append({
            "id": store.id,
            "name": store.name,
            "website": store.website,
            "location": store.location,
            "store_type": store.store_type,
            "is_primary": store.is_primary,
            "total_products": product_count,
            "matched_products": matched_count
        })
    
    return result

@router.get("/comparison/{competitor_store_id}")
async def get_comparison(
    competitor_store_id: int,
    limit: int = 50,
    offset: int = 0,
    category: str = None,
    search: str = None,
    db: Session = Depends(get_db)
):
    """Compare prices with a competitor store"""
    
    # get stores
    primary_store = StoreCRUD.get_primary_store(db)
    if not primary_store:
        raise HTTPException(status_code=404, detail="Primary store not found")
    
    competitor_store = db.query(Store).filter(Store.id == competitor_store_id).first()
    if not competitor_store:
        raise HTTPException(status_code=404, detail="Competitor store not found")
    
    # build query for matches
    query = db.query(ProductMatch).join(
        Product, Product.id == ProductMatch.matched_product_id
    ).filter(
        Product.store_id == competitor_store_id
    )
    
    # get all matches first for stats
    all_matches = query.all()
    
    # calculate stats and build comparisons
    total_matched = len(all_matches)
    we_cheaper = 0
    they_cheaper = 0
    total_savings_amount = 0
    total_savings_percent = 0
    product_comparisons = []
    categories_found = set()
    
    for match in all_matches:
        # get products
        primary_product = db.query(Product).filter(
            Product.id == match.primary_product_id
        ).first()
        competitor_product = db.query(Product).filter(
            Product.id == match.matched_product_id
        ).first()
        
        if not primary_product or not competitor_product:
            continue
        
        # get prices
        our_price = PriceCRUD.get_latest_price(db, primary_product.id)
        their_price = PriceCRUD.get_latest_price(db, competitor_product.id)
        
        if our_price and their_price:
            # calculate savings
            savings = their_price.price - our_price.price
            savings_percent = (savings / their_price.price * 100) if their_price.price > 0 else 0
            
            if savings > 0:
                we_cheaper += 1
            elif savings < 0:
                they_cheaper += 1
            
            total_savings_amount += abs(savings)
            total_savings_percent += abs(savings_percent)
            
            # get normalized prices
            our_normalized = extract_normalized_price(primary_product.name, our_price.price)
            their_normalized = extract_normalized_price(competitor_product.name, their_price.price)
            
            # determine category
            product_category = categorize_product(primary_product.name, primary_product.category)
            categories_found.add(product_category)
            
            # apply filters
            if category and category != 'All' and product_category != category:
                continue
            
            if search:
                search_lower = search.lower()
                if not (search_lower in primary_product.name.lower() or 
                       search_lower in competitor_product.name.lower()):
                    continue
            
            product_comparisons.append({
                "primary_product_id": primary_product.id,
                "primary_product_name": primary_product.name,
                "primary_product_brand": primary_product.brand,
                "primary_product_size": our_normalized['size'] or primary_product.size,
                "competitor_product_id": competitor_product.id,
                "competitor_product_name": competitor_product.name,
                "competitor_product_brand": competitor_product.brand,
                "competitor_product_size": their_normalized['size'] or competitor_product.size,
                "category": product_category,
                "our_price": our_price.price,
                "their_price": their_price.price,
                "our_normalized_price": our_normalized['normalized_price'],
                "their_normalized_price": their_normalized['normalized_price'],
                "normalized_unit": our_normalized['unit'] or their_normalized['unit'],
                "savings": savings,
                "savings_percent": savings_percent,
                "match_confidence": match.confidence_score,
                "match_type": match.match_type,
                "is_on_sale_primary": our_price.is_on_sale,
                "is_on_sale_competitor": their_price.is_on_sale
            })
    
    # sort by savings by default
    product_comparisons.sort(key=lambda x: x['savings_percent'], reverse=True)
    
    # calculate averages
    avg_savings_percent = (total_savings_percent / total_matched) if total_matched > 0 else 0
    avg_savings_amount = (total_savings_amount / total_matched) if total_matched > 0 else 0
    
    return {
        "primary_store": {
            "id": primary_store.id,
            "name": primary_store.name
        },
        "competitor_store": {
            "id": competitor_store.id,
            "name": competitor_store.name,
            "website": competitor_store.website,
            "location": competitor_store.location
        },
        "statistics": {
            "total_matched": total_matched,
            "we_cheaper_count": we_cheaper,
            "they_cheaper_count": they_cheaper,
            "we_cheaper_percent": (we_cheaper / total_matched * 100) if total_matched > 0 else 0,
            "they_cheaper_percent": (they_cheaper / total_matched * 100) if total_matched > 0 else 0,
            "average_savings_percent": avg_savings_percent,
            "average_savings_amount": avg_savings_amount
        },
        "categories": sorted(list(categories_found)),
        "products": product_comparisons[offset:offset + limit],
        "pagination": {
            "total": len(product_comparisons),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(product_comparisons)
        }
    }

@router.get("/export/{competitor_store_id}")
async def export_comparison(
    competitor_store_id: int,
    format: str = "csv",
    db: Session = Depends(get_db)
):
    """Export comparison data as CSV or JSON"""
    
    # get all comparison data
    comparison_data = await get_comparison(competitor_store_id, limit=10000, db=db)
    
    if format == "csv":
        import csv
        import io
        from fastapi.responses import StreamingResponse
        
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "Product Name (Ours)", "Size", "Category",
                "Our Price", "Their Price", 
                "Price/100g or ml (Ours)", "Price/100g or ml (Theirs)",
                "Savings", "Savings %",
                "Match Type", "Confidence"
            ]
        )
        writer.writeheader()
        
        for product in comparison_data["products"]:
            # format normalized prices
            our_norm = f"${product['our_normalized_price']:.2f}" if product['our_normalized_price'] else "N/A"
            their_norm = f"${product['their_normalized_price']:.2f}" if product['their_normalized_price'] else "N/A"
            
            writer.writerow({
                "Product Name (Ours)": product["primary_product_name"],
                "Size": product["primary_product_size"] or "-",
                "Category": product["category"],
                "Our Price": f"${product['our_price']:.2f}",
                "Their Price": f"${product['their_price']:.2f}",
                "Price/100g or ml (Ours)": our_norm,
                "Price/100g or ml (Theirs)": their_norm,
                "Savings": f"${abs(product['savings']):.2f}",
                "Savings %": f"{product['savings_percent']:.1f}%",
                "Match Type": product["match_type"],
                "Confidence": f"{product['match_confidence']:.3f}"
            })
        
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=price_comparison_{competitor_store_id}.csv"
            }
        )
    else:
        return comparison_data