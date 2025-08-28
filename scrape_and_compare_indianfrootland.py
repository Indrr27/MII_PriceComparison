# scrape_and_compare_indianfrootland.py
"""
Indian Frootland scraper and comparison tool with detailed match display.
Works with the unified match_products.py including per-unit price normalization.
"""

import logging
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from tabulate import tabulate
from app.database import SessionLocal, engine, Base
from app.models import Store, Product, Price
from app.crud import StoreCRUD, ProductCRUD, PriceCRUD
from scrapers.competitor_scrapers.indianfrootland_scraper import IndianFrootlandScraper
from match_products import DatabaseMatcher  # Using unified matcher

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('indianfrootland_scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_database():
    """Create database tables if they don't exist"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database setup complete")

def setup_indianfrootland_store(db: Session) -> Store:
    """Create or get the Indian Frootland store record"""
    store = StoreCRUD.get_store_by_name(db, "Indian Frootland")
    
    if not store:
        store_data = {
            "name": "Indian Frootland",
            "website": "https://indianfrootland.com",
            "location": "Brampton, Ontario",
            "store_type": "Indian Grocery",
            "is_primary": False
        }
        store = StoreCRUD.create_store(db, store_data)
        logger.info("Created Indian Frootland store record")
    else:
        logger.info("Found existing Indian Frootland store record")
    
    return store

def validate_and_clean_scraped_data(products: list) -> list:
    """Validate and clean scraped product data before saving"""
    logger.info(f"🔍 Validating {len(products)} scraped products...")
    
    cleaned_products = []
    issues_found = {'missing_name': 0, 'missing_price': 0, 'invalid_price': 0, 'cleaned': 0}
    
    for product in products:
        # Skip products with missing essential data
        if not product.get('name') or len(product['name'].strip()) < 3:
            issues_found['missing_name'] += 1
            continue
            
        if not product.get('price') or product['price'] <= 0:
            issues_found['missing_price'] += 1
            continue
            
        # Clean and validate price
        try:
            price = float(product['price'])
            if price > 1000:  # Flag extremely high prices
                logger.warning(f"High price detected: {product['name']} - ${price}")
        except (ValueError, TypeError):
            issues_found['invalid_price'] += 1
            continue
        
        # Clean product name
        cleaned_name = product['name'].strip()
        cleaned_name = cleaned_name.replace('Add to cart', '').replace('Quick view', '').strip()
        
        # Clean category if present
        category = product.get('category', 'Other')
        if category and len(category) > 100:
            category = category[:100]
        
        # Note: Indian Frootland includes size in product name (extracted from brackets)
        cleaned_product = {
            'name': cleaned_name,
            'price': price,
            'brand': product.get('brand', 'Unknown')[:50] if product.get('brand') else 'Unknown',
            'category': category,
            'url': product.get('url', '')[:500] if product.get('url') else '',
            'on_sale': product.get('on_sale', False)
        }
        
        cleaned_products.append(cleaned_product)
        issues_found['cleaned'] += 1
    
    # Report validation results
    logger.info(f"📊 Validation complete:")
    logger.info(f"   ✅ Clean products: {issues_found['cleaned']}")
    logger.info(f"   ❌ Missing names: {issues_found['missing_name']}")
    logger.info(f"   ❌ Missing/invalid prices: {issues_found['missing_price']}")
    logger.info(f"   ❌ Invalid price format: {issues_found['invalid_price']}")
    
    return cleaned_products

def save_indianfrootland_products(db: Session, store: Store, products: list):
    """Save scraped Indian Frootland products to database with validation"""
    products = validate_and_clean_scraped_data(products)
    
    if not products:
        logger.error("No valid products to save after validation!")
        return 0, 0
    
    saved_count = 0
    updated_count = 0
    
    logger.info(f"💾 Saving {len(products)} validated products to database...")
    
    for i, product_data in enumerate(products):
        if i % 50 == 0:
            logger.info(f"Progress: {i}/{len(products)} products processed")
            
        try:
            # Check if product already exists
            existing_product = db.query(Product).filter(
                Product.store_id == store.id,
                Product.name == product_data['name']
            ).first()
            
            if existing_product:
                # Update existing product
                update_data = {
                    'brand': product_data['brand'],
                    'category': product_data['category'],
                    'url': product_data['url'],
                    'is_active': True
                }
                ProductCRUD.update_product(db, existing_product.id, update_data)
                
                # Add new price
                PriceCRUD.add_price(db, existing_product.id, product_data['price'])
                updated_count += 1
                logger.debug(f"Updated product: {product_data['name']}")
                
            else:
                # Create new product
                new_product_data = {
                    'store_id': store.id,
                    'name': product_data['name'],
                    'brand': product_data['brand'],
                    'category': product_data['category'],
                    'url': product_data['url']
                }
                new_product = ProductCRUD.create_product(db, new_product_data)
                
                # Add initial price
                PriceCRUD.add_price(db, new_product.id, product_data['price'])
                saved_count += 1
                logger.debug(f"Created new product: {product_data['name']}")
                
        except Exception as e:
            logger.error(f"Error saving product {product_data.get('name', 'Unknown')}: {e}")
            continue
    
    logger.info(f"✅ Database update complete: {saved_count} new products, {updated_count} updated products")
    return saved_count, updated_count

def display_detailed_matches(matches, quality_report=None):
    """Display detailed match information in console"""
    if not matches:
        print("No matches to display")
        return
    
    print("\n" + "="*120)
    print("🎯 DETAILED MATCH RESULTS - INDIAN FROOTLAND")
    print("="*120)
    
    # Group matches by confidence level
    exact_matches = [m for m in matches if m.match_type == 'exact']
    similar_matches = [m for m in matches if m.match_type == 'similar']
    substitute_matches = [m for m in matches if m.match_type == 'substitute']
    
    db = SessionLocal()
    
    try:
        # Display exact matches
        if exact_matches:
            print("\n✨ EXACT MATCHES (Confidence >= 0.9)")
            print("-" * 120)
            for match in exact_matches[:10]:  # Show first 10
                primary = db.query(Product).filter(Product.id == match.primary_id).first()
                matched = db.query(Product).filter(Product.id == match.matched_id).first()
                
                print(f"  [{match.confidence:.3f}] {primary.name[:50]:<50} → {matched.name[:50]:<50}")
                if match.warnings:
                    print(f"         Warnings: {', '.join(match.warnings[:2])}")
        
        # Display similar matches
        if similar_matches:
            print("\n🔄 SIMILAR MATCHES (Confidence 0.75-0.9)")
            print("-" * 120)
            for match in similar_matches[:15]:  # Show first 15
                primary = db.query(Product).filter(Product.id == match.primary_id).first()
                matched = db.query(Product).filter(Product.id == match.matched_id).first()
                
                print(f"  [{match.confidence:.3f}] {primary.name[:50]:<50} → {matched.name[:50]:<50}")
                if match.warnings:
                    print(f"         Warnings: {', '.join(match.warnings[:2])}")
        
        # Display substitute matches
        if substitute_matches:
            print("\n🔀 SUBSTITUTE MATCHES (Confidence 0.65-0.75)")
            print("-" * 120)
            for match in substitute_matches[:20]:  # Show first 20
                primary = db.query(Product).filter(Product.id == match.primary_id).first()
                matched = db.query(Product).filter(Product.id == match.matched_id).first()
                
                print(f"  [{match.confidence:.3f}] {primary.name[:50]:<50} → {matched.name[:50]:<50}")
                if match.warnings:
                    print(f"         Warnings: {', '.join(match.warnings[:2])}")
        
        # Summary statistics
        print("\n" + "="*120)
        print("📊 MATCH SUMMARY")
        print("="*120)
        print(f"Total Matches: {len(matches)}")
        print(f"  • Exact: {len(exact_matches)} ({len(exact_matches)/len(matches)*100:.1f}%)")
        print(f"  • Similar: {len(similar_matches)} ({len(similar_matches)/len(matches)*100:.1f}%)")
        print(f"  • Substitute: {len(substitute_matches)} ({len(substitute_matches)/len(matches)*100:.1f}%)")
        
        # Show confidence distribution
        confidence_ranges = {
            '0.90-1.00': len([m for m in matches if m.confidence >= 0.9]),
            '0.80-0.89': len([m for m in matches if 0.8 <= m.confidence < 0.9]),
            '0.70-0.79': len([m for m in matches if 0.7 <= m.confidence < 0.8]),
            '0.65-0.69': len([m for m in matches if 0.65 <= m.confidence < 0.7])
        }
        
        print("\n📈 Confidence Distribution:")
        for range_name, count in confidence_ranges.items():
            percentage = (count / len(matches) * 100) if matches else 0
            print(f"  {range_name}: {count} matches ({percentage:.1f}%)")
        
        # Show common warnings if any
        all_warnings = []
        for match in matches:
            all_warnings.extend(match.warnings)
        
        if all_warnings:
            from collections import Counter
            warning_counts = Counter(all_warnings)
            print("\n⚠️ Common Warnings:")
            for warning, count in warning_counts.most_common(5):
                print(f"  • {warning}: {count} occurrences")
        
        # Display quality report if provided
        if quality_report:
            print("\n📊 QUALITY METRICS:")
            print(f"  • Raw matches found: {quality_report.get('total_raw_matches', 0)}")
            print(f"  • Quality validated: {quality_report.get('validated_matches', 0)}")
            print(f"  • Rejected: {quality_report.get('rejected_matches', 0)}")
            
            if 'normalization_success_rate' in quality_report:
                print(f"  • Size normalization success: {quality_report['normalization_success_rate']*100:.1f}%")
            
            if 'rejection_reasons' in quality_report and quality_report['rejection_reasons']:
                print(f"  • Top rejection reasons:")
                sorted_reasons = sorted(quality_report['rejection_reasons'].items(), 
                                      key=lambda x: x[1], reverse=True)
                for reason, count in sorted_reasons[:3]:
                    print(f"    - {reason}: {count}")
    
    finally:
        db.close()

def validate_store_data_quality():
    """Validate data quality before AI matching"""
    db = SessionLocal()
    
    try:
        made_in_india = StoreCRUD.get_store_by_name(db, "Made in India Grocery")
        indianfrootland = StoreCRUD.get_store_by_name(db, "Indian Frootland")
        
        if not made_in_india or not indianfrootland:
            return False, "Missing store data"
        
        mii_products = ProductCRUD.get_products_by_store(db, made_in_india.id)
        if_products = ProductCRUD.get_products_by_store(db, indianfrootland.id)
        
        print(f"\n🔍 DATA QUALITY VALIDATION")
        print(f"{'='*50}")
        print(f"Made in India: {len(mii_products)} products")
        print(f"Indian Frootland: {len(if_products)} products")
        
        if len(mii_products) < 10:
            return False, "Not enough Made in India products for meaningful comparison"
        
        if len(if_products) < 50:
            return False, "Not enough Indian Frootland products for meaningful comparison"
        
        # Check price data availability
        mii_with_prices = sum(1 for p in mii_products if PriceCRUD.get_latest_price(db, p.id))
        if_with_prices = sum(1 for p in if_products if PriceCRUD.get_latest_price(db, p.id))
        
        print(f"With prices - MII: {mii_with_prices}/{len(mii_products)}, IF: {if_with_prices}/{len(if_products)}")
        
        if mii_with_prices / len(mii_products) < 0.8:
            return False, "Too many Made in India products missing prices"
        
        if if_with_prices / len(if_products) < 0.8:
            return False, "Too many Indian Frootland products missing prices"
        
        print("✅ Data quality validation passed!")
        return True, "Data quality is good for AI matching"
        
    except Exception as e:
        return False, f"Validation error: {e}"
    finally:
        db.close()

def run_ai_matching_with_display():
    """Run AI matching with detailed match display using unified matcher"""
    print("\n🎯 AI MATCHING WITH DETAILED DISPLAY - INDIAN FROOTLAND")
    print("="*60)
    
    # Validate data quality first
    is_valid, message = validate_store_data_quality()
    if not is_valid:
        print(f"❌ {message}")
        print("Please ensure both stores have sufficient product data with prices.")
        return
    
    # Check if JSON config files exist
    config_dir = Path("ai_matching/config")
    required_files = ["classifications.json", "forbidden.json", "synonyms.json", "brands.json"]
    missing_files = []
    
    for file in required_files:
        if not (config_dir / file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing configuration files: {', '.join(missing_files)}")
        print(f"Please ensure all JSON files are in {config_dir}/")
        return
    
    # Allow user to select matching mode
    print("\nSelect matching mode:")
    print("1. Enhanced with per-unit normalization (recommended)")
    print("2. Basic matching without normalization")
    
    mode_choice = input("Choose mode (1-2, default 1): ").strip()
    use_normalization = mode_choice != '2'
    
    # Allow user to tune confidence threshold
    print("\nSelect matching confidence level:")
    print("1. Conservative (0.75) - Fewer, higher-quality matches")
    print("2. Balanced (0.65) - Good balance of quality and quantity")  
    print("3. Aggressive (0.55) - More matches, some may be less accurate")
    
    confidence_choice = input("Choose confidence level (1-3, default 2): ").strip()
    
    confidence_map = {'1': 0.75, '2': 0.65, '3': 0.55}
    min_confidence = confidence_map.get(confidence_choice, 0.65)
    
    print(f"\n🎯 Using confidence threshold: {min_confidence}")
    print(f"📊 Mode: {'Enhanced with per-unit normalization' if use_normalization else 'Basic matching'}")
    
    logger.info("Starting AI product matching...")
    
    # Use unified DatabaseMatcher
    matcher = DatabaseMatcher()
    
    # Run matching with selected confidence and mode
    matches, quality_report = matcher.match_stores(
        primary_store="Made in India Grocery",
        competitor_store="Indian Frootland",
        min_confidence=min_confidence,
        save=True,
        use_normalization=use_normalization
    )
    
    logger.info(f"✅ AI matching complete: {len(matches)} validated matches")
    
    if len(matches) == 0:
        print("⚠️ No matches found. Try lowering confidence threshold or check data quality.")
        if quality_report:
            matcher.generate_quality_report(quality_report)
        return
    
    # Display detailed matches with quality report
    display_detailed_matches(matches, quality_report)
    
    # Ask if user wants to see reports
    print("\n" + "="*60)
    show_reports = input("Show matching and price reports? (y/N): ").strip().lower()
    
    if show_reports == 'y':
        # Generate reports using unified matcher
        matcher.generate_match_report("Made in India Grocery")
        matcher.generate_price_report("Made in India Grocery", min_confidence, 
                                     use_normalized=use_normalization, 
                                     competitor_store="Indian Frootland")

def check_json_configuration():
    """Check and display JSON configuration status"""
    config_dir = Path("ai_matching/config")
    
    print("\n📋 JSON CONFIGURATION STATUS")
    print("="*60)
    
    required_files = {
        "classifications.json": "Product type and subtype classifications",
        "forbidden.json": "Forbidden match combinations",
        "synonyms.json": "Regional term synonyms",
        "brands.json": "Known brand names"
    }
    
    all_present = True
    
    for filename, description in required_files.items():
        filepath = config_dir / filename
        if filepath.exists():
            # Get file size and count entries
            import json
            with open(filepath, 'r') as f:
                data = json.load(f)
                if filename == "classifications.json":
                    count = len(data.get("categories", []))
                    print(f"✅ {filename}: {count} categories")
                elif filename == "forbidden.json":
                    count = len(data.get("pairs", []))
                    print(f"✅ {filename}: {count} forbidden pairs")
                elif filename == "synonyms.json":
                    count = len(data.get("groups", []))
                    print(f"✅ {filename}: {count} synonym groups")
                elif filename == "brands.json":
                    count = len(data.get("known_brands", []))
                    print(f"✅ {filename}: {count} brands")
        else:
            print(f"❌ {filename}: MISSING - {description}")
            all_present = False
    
    if not all_present:
        print(f"\n⚠️ Please create missing JSON files in {config_dir}/")
    else:
        print("\n✅ All configuration files present!")
    
    return all_present

def main():
    """Main function with enhanced features"""
    print("🛒 ENHANCED INDIAN FROOTLAND SCRAPER & COMPARISON")
    print("🎯 With Unified Matching & Per-Unit Price Analysis")
    print("="*80)
    
    # Check JSON configuration
    if not check_json_configuration():
        print("\n⚠️ Please set up JSON configuration files before proceeding.")
        return
    
    # Setup database
    setup_database()
    
    db = SessionLocal()
    
    try:
        # Check if Made in India Grocery exists
        made_in_india = StoreCRUD.get_store_by_name(db, "Made in India Grocery")
        if not made_in_india:
            print("⚠️ Made in India Grocery not found in database!")
            print("📋 Please run 'python scrape_made_in_india.py' first.")
            return
        
        made_in_india_products = ProductCRUD.get_products_by_store(db, made_in_india.id)
        print(f"✅ Found {len(made_in_india_products)} Made in India Grocery products")
        
        # Setup Indian Frootland store
        if_store = setup_indianfrootland_store(db)
        existing_if_products = ProductCRUD.get_products_by_store(db, if_store.id)
        print(f"ℹ️ Found {len(existing_if_products)} existing Indian Frootland products")
        
        # Enhanced menu
        print("\n🎯 What would you like to do?")
        print("1. Scrape Indian Frootland products (10-15 minutes)")
        print("2. Run AI matching with detailed display")
        print("3. Both - Full process (scrape + match)")
        print("4. Validate data quality only")
        print("5. Check JSON configuration status")
        print("6. Generate reports from existing matches")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice in ['1', '3']:
            # Scrape Indian Frootland
            logger.info("Starting Indian Frootland scraping...")
            print("🛒 Starting Indian Frootland scraping...")
            print("⏱️ Expected time: 10-15 minutes")
            print("📍 Note: Indian Frootland specializes in Indian groceries")
            
            confirm = input("Continue? (y/N): ").strip().lower()
            if confirm != 'y':
                print("Scraping cancelled.")
                return
            
            scraper = IndianFrootlandScraper(headless=True)
            products = scraper.scrape_with_error_handling()
            
            if not products:
                logger.error("❌ No products were scraped from Indian Frootland!")
                return
            
            logger.info(f"✅ Successfully scraped {len(products)} products from Indian Frootland")
            
            # Save to database
            logger.info("💾 Saving products to database...")
            saved_count, updated_count = save_indianfrootland_products(db, if_store, products)
            
            print(f"\n✅ Saved {saved_count} new products, updated {updated_count} existing products")
        
        if choice in ['2', '3']:
            # Run AI matching with display
            run_ai_matching_with_display()
        
        if choice == '4':
            # Data quality validation only
            is_valid, message = validate_store_data_quality()
            print(f"\n📊 Validation Result: {'✅ PASSED' if is_valid else '❌ FAILED'}")
            print(f"Details: {message}")
        
        if choice == '5':
            # Already checked at startup, just show again
            check_json_configuration()
        
        if choice == '6':
            # Generate reports from existing matches
            print("\nSelect report type:")
            print("1. Enhanced report with per-unit pricing")
            print("2. Basic report")
            
            report_choice = input("Choose report type (1-2, default 1): ").strip()
            use_normalized = report_choice != '2'
            
            confidence = input("Minimum confidence (default 0.65): ").strip()
            min_confidence = float(confidence) if confidence else 0.65
            
            matcher = DatabaseMatcher()
            matcher.generate_match_report("Made in India Grocery")
            matcher.generate_price_report("Made in India Grocery", min_confidence, 
                                         use_normalized=use_normalized, 
                                         competitor_store="Indian Frootland")
        
        if choice not in ['1', '2', '3', '4', '5', '6']:
            print("❌ Invalid choice. Please run again.")
        
        print("\n🎉 Process completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Process failed: {e}")
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()