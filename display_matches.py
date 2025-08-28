#!/usr/bin/env python3
"""
Complete Match Display - Shows all matches and exports to text file
"""

from app.database import SessionLocal
from app.models import ProductMatch as DBProductMatch, Product, Store
from datetime import datetime
import os

def get_product_details(db, product_id):
    """Get product details with store info"""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            store = db.query(Store).filter(Store.id == product.store_id).first()
            return {
                'name': product.name,
                'brand': product.brand or 'N/A',
                'size': product.size or 'N/A',
                'store': store.name if store else 'Unknown Store',
                'sku': product.sku or 'N/A'
            }
    except Exception as e:
        return {'name': f'Error: {e}', 'brand': 'N/A', 'size': 'N/A', 'store': 'N/A', 'sku': 'N/A'}
    return {'name': 'Not Found', 'brand': 'N/A', 'size': 'N/A', 'store': 'N/A', 'sku': 'N/A'}

def complete_display():
    """Complete display of all matches with export to file"""
    db = SessionLocal()
    
    try:
        # Get all matches sorted by confidence (highest first)
        matches = db.query(DBProductMatch).order_by(DBProductMatch.confidence_score.desc()).all()
        
        print(f"\n🎯 Found {len(matches)} matches in database")
        print("📝 Generating complete match report...")
        
        if not matches:
            print("No matches found!")
            return
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"all_product_matches_{timestamp}.txt"
        
        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*100 + "\n")
            f.write("COMPLETE PRODUCT MATCHES REPORT\n")
            f.write("="*100 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Matches: {len(matches)}\n")
            f.write("="*100 + "\n\n")
            
            # Statistics
            exact_matches = len([m for m in matches if getattr(m, 'match_type', '') == 'exact'])
            similar_matches = len([m for m in matches if getattr(m, 'match_type', '') == 'similar'])  
            substitute_matches = len([m for m in matches if getattr(m, 'match_type', '') == 'substitute'])
            
            high_conf = len([m for m in matches if m.confidence_score >= 0.85])
            medium_conf = len([m for m in matches if 0.75 <= m.confidence_score < 0.85])
            low_conf = len([m for m in matches if m.confidence_score < 0.75])
            
            f.write("MATCH STATISTICS:\n")
            f.write("-"*50 + "\n")
            f.write(f"Exact Matches:      {exact_matches:4d} ({exact_matches/len(matches)*100:.1f}%)\n")
            f.write(f"Similar Matches:    {similar_matches:4d} ({similar_matches/len(matches)*100:.1f}%)\n")
            f.write(f"Substitute Matches: {substitute_matches:4d} ({substitute_matches/len(matches)*100:.1f}%)\n")
            f.write(f"\nHigh Confidence (≥85%):   {high_conf:4d} ({high_conf/len(matches)*100:.1f}%)\n")
            f.write(f"Medium Confidence (75-84%): {medium_conf:4d} ({medium_conf/len(matches)*100:.1f}%)\n")
            f.write(f"Low Confidence (<75%):      {low_conf:4d} ({low_conf/len(matches)*100:.1f}%)\n\n")
            f.write("="*100 + "\n\n")
            
            # All matches
            for i, match in enumerate(matches, 1):
                f.write(f"MATCH #{i:3d} (ID: {match.id})\n")
                f.write("-"*50 + "\n")
                f.write(f"Confidence Score: {match.confidence_score:.3f} ({match.confidence_score*100:.1f}%)\n")
                f.write(f"Match Type:       {getattr(match, 'match_type', 'unknown')}\n")
                f.write(f"Created:          {getattr(match, 'created_at', 'unknown')}\n\n")
                
                # Get product details
                primary_details = get_product_details(db, match.primary_product_id)
                matched_details = get_product_details(db, match.matched_product_id)
                
                f.write(f"PRIMARY PRODUCT:\n")
                f.write(f"  Store:  {primary_details['store']}\n")
                f.write(f"  Name:   {primary_details['name']}\n")
                f.write(f"  Brand:  {primary_details['brand']}\n")
                f.write(f"  Size:   {primary_details['size']}\n")
                f.write(f"  SKU:    {primary_details['sku']}\n\n")
                
                f.write(f"MATCHED PRODUCT:\n")
                f.write(f"  Store:  {matched_details['store']}\n")
                f.write(f"  Name:   {matched_details['name']}\n")
                f.write(f"  Brand:  {matched_details['brand']}\n")
                f.write(f"  Size:   {matched_details['size']}\n")
                f.write(f"  SKU:    {matched_details['sku']}\n")
                
                f.write("\n" + "="*100 + "\n\n")
                
                # Progress indicator for console
                if i % 50 == 0:
                    print(f"  ✏️  Processed {i}/{len(matches)} matches...")
        
        print(f"✅ Complete report saved to: {filename}")
        print(f"📊 Total matches: {len(matches)}")
        print(f"🏆 High confidence matches: {high_conf}")
        
        # Ask if they want to see a summary in console
        show_summary = input("\nShow summary statistics in console? (y/n): ").lower().strip()
        if show_summary == 'y':
            print(f"\n📊 MATCH SUMMARY:")
            print(f"{'='*50}")
            print(f"Total Matches: {len(matches)}")
            print(f"\nBy Type:")
            print(f"  Exact:      {exact_matches:4d} ({exact_matches/len(matches)*100:.1f}%)")
            print(f"  Similar:    {similar_matches:4d} ({similar_matches/len(matches)*100:.1f}%)")
            print(f"  Substitute: {substitute_matches:4d} ({substitute_matches/len(matches)*100:.1f}%)")
            print(f"\nBy Confidence:")
            print(f"  High (≥85%):    {high_conf:4d} ({high_conf/len(matches)*100:.1f}%)")
            print(f"  Medium (75-84%): {medium_conf:4d} ({medium_conf/len(matches)*100:.1f}%)")
            print(f"  Low (<75%):     {low_conf:4d} ({low_conf/len(matches)*100:.1f}%)")
        
        # Ask if they want to see top matches
        show_top = input("Show top 20 highest confidence matches in console? (y/n): ").lower().strip()
        if show_top == 'y':
            print(f"\n🏆 TOP 20 HIGHEST CONFIDENCE MATCHES:")
            print("="*80)
            for i, match in enumerate(matches[:20], 1):
                primary_details = get_product_details(db, match.primary_product_id)
                matched_details = get_product_details(db, match.matched_product_id)
                
                print(f"\n{i:2d}. [{match.confidence_score:.3f}] {getattr(match, 'match_type', 'unknown').upper()}")
                print(f"    Primary:  {primary_details['name'][:50]}")
                print(f"    Matched:  {matched_details['name'][:50]}")
                print(f"    Stores:   {primary_details['store']} ↔ {matched_details['store']}")
        
        print(f"\n📁 Full detailed report saved to: {os.path.abspath(filename)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    complete_display()