# scrape_made_in_india.py
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import Store, Product, Price
from app.crud import StoreCRUD, ProductCRUD, PriceCRUD
from scrapers.made_in_india_scraper import MadeInIndiaGroceryScraper

# Set up logging (UTF-8 safe)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_database():
    """Create database tables if they don't exist"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database setup complete")

def setup_made_in_india_store(db: Session) -> Store:
    """Create or get the Made in India Grocery store record"""
    store = StoreCRUD.get_store_by_name(db, "Made in India Grocery")
    
    if not store:
        store_data = {
            "name": "Made in India Grocery",
            "website": "https://madeinindiagrocery.com",
            "location": "Georgetown, Ontario",
            "store_type": "Indian Grocery",
            "is_primary": True
        }
        store = StoreCRUD.create_store(db, store_data)
        logger.info("Created Made in India Grocery store record")
    else:
        logger.info("Found existing Made in India Grocery store record")
    
    return store

def save_products_to_db(db: Session, store: Store, products: list):
    """Save scraped products to database with enhanced category tracking"""
    saved_count = 0
    updated_count = 0
    
    # Track category improvements
    category_improvements = {}
    
    for product_data in products:
        try:
            # Check if product already exists (by name and store)
            existing_product = db.query(Product).filter(
                Product.store_id == store.id,
                Product.name == product_data['name']
            ).first()
            
            if existing_product:
                # Track category improvements
                old_category = existing_product.category
                new_category = product_data['category']
                
                if old_category != new_category:
                    if old_category not in category_improvements:
                        category_improvements[old_category] = {}
                    if new_category not in category_improvements[old_category]:
                        category_improvements[old_category][new_category] = 0
                    category_improvements[old_category][new_category] += 1
                
                # Update existing product
                update_data = {
                    'brand': product_data['brand'],
                    'size': product_data['size'],
                    'category': product_data['category'],
                    'url': product_data['url'],
                    'is_active': True
                }
                ProductCRUD.update_product(db, existing_product.id, update_data)
                
                # Add new price
                PriceCRUD.add_price(db, existing_product.id, product_data['price'])
                updated_count += 1
                logger.debug(f"Updated product: {product_data['name']} | Category: {new_category}")
                
            else:
                # Create new product
                new_product_data = {
                    'store_id': store.id,
                    'name': product_data['name'],
                    'brand': product_data['brand'],
                    'size': product_data['size'],
                    'category': product_data['category'],
                    'url': product_data['url']
                }
                new_product = ProductCRUD.create_product(db, new_product_data)
                
                # Add initial price
                PriceCRUD.add_price(db, new_product.id, product_data['price'])
                saved_count += 1
                logger.debug(f"Created new product: {product_data['name']} | Category: {product_data['category']}")
                
        except Exception as e:
            logger.error(f"Error saving product {product_data.get('name', 'Unknown')}: {e}")
            continue
    
    # Report category improvements
    if category_improvements:
        logger.info("CATEGORY IMPROVEMENTS DETECTED:")
        for old_cat, new_cats in category_improvements.items():
            for new_cat, count in new_cats.items():
                logger.info(f"   {old_cat} -> {new_cat}: {count} products")
    
    logger.info(f"Database update complete: {saved_count} new products, {updated_count} updated products")
    return saved_count, updated_count

def generate_enhanced_summary_report(db: Session, store: Store):
    """Generate enhanced summary report with category accuracy"""
    products = ProductCRUD.get_products_by_store(db, store.id)
    
    if not products:
        print("No products found in database!")
        return
    
    # Category breakdown
    category_counts = {}
    brand_counts = {}
    price_ranges = {'Under $2': 0, '$2-$5': 0, '$5-$10': 0, 'Over $10': 0}
    
    for product in products:
        # Count categories
        category = product.category or 'Unknown'
        category_counts[category] = category_counts.get(category, 0) + 1
        
        # Count brands
        brand = product.brand or 'Unknown'
        brand_counts[brand] = brand_counts.get(brand, 0) + 1
        
        # Price ranges
        latest_price = PriceCRUD.get_latest_price(db, product.id)
        if latest_price:
            price = latest_price.price
            if price < 2:
                price_ranges['Under $2'] += 1
            elif price < 5:
                price_ranges['$2-$5'] += 1
            elif price < 10:
                price_ranges['$5-$10'] += 1
            else:
                price_ranges['Over $10'] += 1
    
    print("\n" + "="*70)
    print("MADE IN INDIA GROCERY - ENHANCED SCRAPING SUMMARY")
    print("="*70)
    print(f"Total Products: {len(products)}")
    print(f"Store: {store.name}")
    print(f"Location: {store.location}")
    
    print(f"\nCATEGORY BREAKDOWN:")
    official_categories = 0
    unknown_categories = 0
    
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        if category == 'Unknown':
            unknown_categories += count
            print(f"  [UNKNOWN] {category}: {count} products")
        else:
            official_categories += count
            print(f"  [SUCCESS] {category}: {count} products")
    
    # Calculate accuracy
    total_products = len(products)
    accuracy_rate = (official_categories / total_products) * 100 if total_products > 0 else 0
    
    print(f"\nCATEGORY EXTRACTION ACCURACY:")
    print(f"  Official Categories: {official_categories}/{total_products} products ({accuracy_rate:.1f}%)")
    print(f"  Unknown Categories: {unknown_categories}/{total_products} products ({100-accuracy_rate:.1f}%)")
    
    if accuracy_rate >= 90:
        print("  STATUS: EXCELLENT - Category extraction working perfectly!")
    elif accuracy_rate >= 80:
        print("  STATUS: GOOD - Most categories extracted successfully!")
    elif accuracy_rate >= 70:
        print("  STATUS: FAIR - Some category extraction issues detected")
    else:
        print("  STATUS: NEEDS IMPROVEMENT - Category extraction needs work")
    
    print(f"\nTOP BRANDS:")
    for brand, count in sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {brand}: {count} products")
    
    print(f"\nPRICE DISTRIBUTION:")
    for price_range, count in price_ranges.items():
        print(f"  {price_range}: {count} products")
    
    print("="*70)

def main():
    """Main scraping function with enhanced category extraction"""
    logger.info("Starting Enhanced Made in India Grocery scraping...")
    
    # Setup database
    setup_database()
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Setup store record
        store = setup_made_in_india_store(db)
        
        # Run enhanced scraper
        logger.info("Initializing enhanced scraper with accurate category extraction...")
        scraper = MadeInIndiaGroceryScraper(headless=True)  # Set to False for debugging
        
        logger.info("Starting enhanced product scraping...")
        logger.info("NOTE: This will take longer due to individual product page visits for accurate categories")
        logger.info("Expected time: 30-45 minutes for complete scraping")
        
        products = scraper.scrape_with_error_handling()
        
        if not products:
            logger.error("No products were scraped! Check the scraper configuration.")
            return
        
        logger.info(f"Successfully scraped {len(products)} products with enhanced categories")
        
        # Save to database
        logger.info("Saving products to database with enhanced category data...")
        saved_count, updated_count = save_products_to_db(db, store, products)
        
        # Generate enhanced summary report
        generate_enhanced_summary_report(db, store)
        
        logger.info("Enhanced scraping process completed successfully!")
        logger.info("Categories are now much more accurate for AI matching!")
        
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        print("\nScraping interrupted. Partial data may have been saved.")
    except Exception as e:
        logger.error(f"Scraping process failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()