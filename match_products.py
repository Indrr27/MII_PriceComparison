# match_products.py - FULLY CORRECTED with proper pricing logic and store labels
"""
Complete product matching system with:
- AI-powered product matching
- Per-unit price normalization for accurate comparisons
- Quality validation with size analysis
- Comprehensive business intelligence reporting
- FIXED: Correct pricing logic and dynamic store labels
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
from sqlalchemy.orm import Session
from tabulate import tabulate
from app.database import SessionLocal
from app.models import Store, Product, ProductMatch as DBProductMatch
from app.crud import StoreCRUD, ProductCRUD, ProductMatchCRUD, PriceCRUD
from ai_matching.product_matcher import ProductMatcher, ProductMatch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NormalizedPrice:
    """Represents a price normalized to standard units"""
    price_per_100g: Optional[float] = None
    price_per_lb: Optional[float] = None
    price_per_liter: Optional[float] = None
    price_per_unit: Optional[float] = None
    original_price: float = 0
    original_size: str = ""
    confidence: str = "unknown"  # high, medium, low, unknown

class DatabaseMatcher:
    """Complete product matcher with per-unit price normalization"""
    
    def __init__(self):
        self.matcher = ProductMatcher()
        self.db = SessionLocal()
        
        # Enhanced size extraction patterns for normalization
        self.size_patterns = [
            # Weight patterns
            (r'(\d+(?:\.\d+)?)\s*kg\b', 'weight', 1000, 'g'),
            (r'(\d+(?:\.\d+)?)\s*(?:g|gm|gms|gram|grams)\b', 'weight', 1, 'g'),
            (r'(\d+(?:\.\d+)?)\s*(?:lb|lbs|pound|pounds)\b', 'weight', 453.592, 'g'),
            (r'(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces)\b', 'weight', 28.3495, 'g'),
            
            # Volume patterns
            (r'(\d+(?:\.\d+)?)\s*(?:l|liter|liters|litre|litres)\b', 'volume', 1000, 'ml'),
            (r'(\d+(?:\.\d+)?)\s*(?:ml|milliliter|milliliters)\b', 'volume', 1, 'ml'),
            (r'(\d+(?:\.\d+)?)\s*(?:fl\s*oz|fluid\s*ounce)\b', 'volume', 29.5735, 'ml'),
            
            # Count patterns
            (r'(\d+)\s*(?:pcs?|pieces?|each|count)\b', 'count', 1, 'pcs'),
            (r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(?:g|gm|ml)\b', 'multi_pack', 1, 'special'),
        ]
        
        # Quality thresholds
        self.HIGH_CONFIDENCE = 0.85
        self.MEDIUM_CONFIDENCE = 0.75
        self.MIN_REPORT_CONFIDENCE = 0.75
    
    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'db'):
            self.db.close()
    
    def match_stores(self, primary_store: str, competitor_store: str,
                    min_confidence: float = 0.65, save: bool = True,
                    use_normalization: bool = True) -> Tuple[List[ProductMatch], Dict]:
        """
        Match products between stores with optional per-unit normalization.
        
        Args:
            primary_store: Name of primary store
            competitor_store: Name of competitor store  
            min_confidence: Minimum confidence threshold
            save: Whether to save matches to database
            use_normalization: Whether to use per-unit price analysis
            
        Returns:
            Tuple of (matches, quality_report)
        """
        # Get stores from database
        primary = StoreCRUD.get_store_by_name(self.db, primary_store)
        competitor = StoreCRUD.get_store_by_name(self.db, competitor_store)
        
        if not primary or not competitor:
            logger.error(f"Store not found: {primary_store} or {competitor_store}")
            return [], {}
        
        # Get products
        primary_products = self._products_to_dicts(
            ProductCRUD.get_products_by_store(self.db, primary.id)
        )
        competitor_products = self._products_to_dicts(
            ProductCRUD.get_products_by_store(self.db, competitor.id)
        )
        
        logger.info(f"Matching {len(primary_products)} {primary_store} products "
                   f"against {len(competitor_products)} {competitor_store} products")
        
        # Run matching
        raw_matches = self.matcher.batch_match(
            primary_products, competitor_products, min_confidence
        )
        
        # Validate matches with optional size analysis
        if use_normalization:
            validated_matches, quality_report = self._validate_with_size_analysis(
                raw_matches, primary_products, competitor_products
            )
        else:
            validated_matches = self._validate_matches(raw_matches, primary_products, competitor_products)
            quality_report = {
                'total_raw_matches': len(raw_matches),
                'validated_matches': len(validated_matches),
                'rejected_matches': len(raw_matches) - len(validated_matches)
            }
        
        # Save to database if requested
        if save and validated_matches:
            saved_count = self._save_matches(validated_matches)
            quality_report['saved_matches'] = saved_count
        
        return validated_matches, quality_report
    
    def _products_to_dicts(self, products: List[Product]) -> List[Dict]:
        """Convert SQLAlchemy products to dicts for matcher"""
        result = []
        for p in products:
            latest_price = PriceCRUD.get_latest_price(self.db, p.id)
            result.append({
                'id': p.id,
                'name': p.name,
                'brand': p.brand or '',
                'size': p.size or '',
                'category': p.category or 'Other',
                'price': latest_price.price if latest_price else 0
            })
        return result
    
    def _validate_matches(self, matches: List[ProductMatch], 
                         primaries: List[Dict], competitors: List[Dict]) -> List[ProductMatch]:
        """Basic validation of matches"""
        validated = []
        primary_lookup = {p['id']: p for p in primaries}
        competitor_lookup = {c['id']: c for c in competitors}
        
        for match in matches:
            primary = primary_lookup.get(match.primary_id)
            competitor = competitor_lookup.get(match.matched_id)
            
            if not primary or not competitor:
                continue
            
            # Basic validation
            if self._is_valid_match(primary, competitor, match):
                validated.append(match)
        
        logger.info(f"Validated {len(validated)} matches from {len(matches)} raw matches")
        return validated
    
    def _validate_with_size_analysis(self, matches: List[ProductMatch], 
                                    primaries: List[Dict], 
                                    competitors: List[Dict]) -> Tuple[List[ProductMatch], Dict]:
        """Enhanced validation including per-unit price analysis"""
        
        primary_lookup = {p['id']: p for p in primaries}
        competitor_lookup = {c['id']: c for c in competitors}
        
        validated = []
        rejected = []
        size_analysis = []
        
        for match in matches:
            primary = primary_lookup.get(match.primary_id)
            competitor = competitor_lookup.get(match.matched_id)
            
            if not primary or not competitor:
                rejected.append(("Missing product data", match))
                continue
            
            # Perform normalized price comparison
            price_comparison = self.compare_normalized_prices(primary, competitor)
            size_analysis.append(price_comparison)
            
            # Enhanced validation rules
            is_valid, issues = self._validate_match_with_pricing(primary, competitor, match, price_comparison)
            
            if is_valid:
                validated.append(match)
            else:
                rejected.append(("; ".join(issues), match))
        
        # Generate enhanced quality report
        quality_report = {
            'total_raw_matches': len(matches),
            'validated_matches': len(validated),
            'rejected_matches': len(rejected),
            'size_analysis': size_analysis,
            'normalization_success_rate': len([s for s in size_analysis if s['can_compare_normalized']]) / len(size_analysis) if size_analysis else 0,
            'rejection_reasons': defaultdict(int)
        }
        
        # Count rejection reasons
        for reason, _ in rejected:
            quality_report['rejection_reasons'][reason] += 1
        
        return validated, quality_report
    
    def _is_valid_match(self, primary: Dict, competitor: Dict, match: ProductMatch) -> bool:
        """Basic match validation"""
        p_words = set(primary['name'].lower().split())
        c_words = set(competitor['name'].lower().split())
        
        common_words = p_words & c_words
        if len(common_words) == 0 and match.confidence < 0.8:
            logger.debug(f"Rejecting match with no common words: "
                       f"{primary['name']} vs {competitor['name']}")
            return False
        
        return True
    
    def _validate_match_with_pricing(self, primary: Dict, competitor: Dict, 
                                    match: ProductMatch, price_comparison: Dict) -> Tuple[bool, List[str]]:
        """Enhanced validation including normalized pricing checks"""
        issues = []
        
        # Name similarity check for low confidence matches
        if match.confidence < 0.7:
            name_similarity = self._calculate_name_similarity(primary['name'], competitor['name'])
            if name_similarity < 0.3:
                issues.append(f"Low name similarity ({name_similarity:.2f}) for low confidence match")
        
        # Per-unit price validation
        if price_comparison['can_compare_normalized']:
            # Check for extreme per-unit price differences
            if abs(price_comparison['normalized_savings_pct']) > 500:  # 5x difference
                issues.append(f"Extreme per-unit price difference: {price_comparison['normalized_savings_pct']:.1f}%")
            
            # Flag suspicious size extraction
            if price_comparison['size_confidence'] == 'low':
                issues.append("Low confidence in size extraction")
        else:
            # Stricter checks when we can't normalize
            if primary['price'] > 0 and competitor['price'] > 0:
                price_ratio = max(primary['price'], competitor['price']) / min(primary['price'], competitor['price'])
                if price_ratio > 10:
                    issues.append(f"Cannot normalize sizes and absolute price difference too large: {price_ratio:.1f}x")
        
        # Size/quantity mismatch detection
        if match.size_similarity < 0.5 and match.confidence < 0.75:
            issues.append("Size/quantity mismatch detected")
        
        return len(issues) == 0, issues
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate basic name similarity"""
        words1 = set(name1.lower().split())
        words2 = set(name2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def extract_enhanced_size(self, product_name: str) -> Tuple[float, str, str, str]:
        """
        Extract size with enhanced patterns and normalization.
        Returns: (normalized_value, base_unit, unit_type, confidence)
        """
        name_lower = product_name.lower()
        
        for pattern, unit_type, multiplier, base_unit in self.size_patterns:
            match = re.search(pattern, name_lower, re.IGNORECASE)
            if match:
                if unit_type == 'multi_pack':
                    # Handle "12 x 200g" format
                    pack_count = float(match.group(1))
                    unit_size = float(match.group(2))
                    total_grams = pack_count * unit_size
                    return total_grams, 'g', 'weight', 'high'
                else:
                    value = float(match.group(1))
                    normalized_value = value * multiplier
                    confidence = 'high' if len(match.group(0)) > 3 else 'medium'
                    return normalized_value, base_unit, unit_type, confidence
        
        # Fallback: look for any number
        number_match = re.search(r'(\d+(?:\.\d+)?)', name_lower)
        if number_match:
            return float(number_match.group(1)), 'unknown', 'unknown', 'low'
        
        return 0, 'unknown', 'unknown', 'unknown'
    
    def calculate_normalized_price(self, price: float, product_name: str) -> NormalizedPrice:
        """Calculate price per standardized unit"""
        size_value, base_unit, unit_type, confidence = self.extract_enhanced_size(product_name)
        
        normalized = NormalizedPrice(
            original_price=price,
            original_size=product_name,
            confidence=confidence
        )
        
        if size_value <= 0 or confidence == 'unknown':
            return normalized
        
        try:
            if unit_type == 'weight' and base_unit == 'g':
                # Calculate price per 100g and per lb
                normalized.price_per_100g = (price / size_value) * 100
                normalized.price_per_lb = (price / size_value) * 453.592
                
            elif unit_type == 'volume' and base_unit == 'ml':
                # Calculate price per liter
                normalized.price_per_liter = (price / size_value) * 1000
                
            elif unit_type == 'count' and base_unit == 'pcs':
                # Calculate price per unit
                normalized.price_per_unit = price / size_value
                
        except (ZeroDivisionError, ValueError) as e:
            logger.debug(f"Error calculating normalized price: {e}")
        
        return normalized
    
    def compare_normalized_prices(self, primary_product: Dict, competitor_product: Dict) -> Dict:
        """Compare products using normalized pricing"""
        primary_norm = self.calculate_normalized_price(
            primary_product['price'], primary_product['name']
        )
        competitor_norm = self.calculate_normalized_price(
            competitor_product['price'], competitor_product['name']
        )
        
        comparison = {
            'primary_name': primary_product['name'][:45],
            'competitor_name': competitor_product['name'][:45],
            'primary_price': primary_product['price'],
            'competitor_price': competitor_product['price'],
            'primary_normalized': primary_norm,
            'competitor_normalized': competitor_norm,
            'comparison_type': 'absolute',
            'normalized_savings': 0,
            'normalized_savings_pct': 0,
            'size_confidence': min(primary_norm.confidence, competitor_norm.confidence),
            'can_compare_normalized': False
        }
        
        # Determine best comparison method
        if (primary_norm.price_per_100g and competitor_norm.price_per_100g and 
            primary_norm.confidence != 'unknown' and competitor_norm.confidence != 'unknown'):
            # Weight-based comparison
            comparison['comparison_type'] = 'per_100g'
            comparison['primary_per_unit'] = primary_norm.price_per_100g
            comparison['competitor_per_unit'] = competitor_norm.price_per_100g
            comparison['unit_label'] = '$/100g'
            comparison['can_compare_normalized'] = True
            
        elif (primary_norm.price_per_liter and competitor_norm.price_per_liter and
              primary_norm.confidence != 'unknown' and competitor_norm.confidence != 'unknown'):
            # Volume-based comparison
            comparison['comparison_type'] = 'per_liter'
            comparison['primary_per_unit'] = primary_norm.price_per_liter
            comparison['competitor_per_unit'] = competitor_norm.price_per_liter
            comparison['unit_label'] = '$/L'
            comparison['can_compare_normalized'] = True
            
        elif (primary_norm.price_per_unit and competitor_norm.price_per_unit and
              primary_norm.confidence != 'unknown' and competitor_norm.confidence != 'unknown'):
            # Count-based comparison
            comparison['comparison_type'] = 'per_unit'
            comparison['primary_per_unit'] = primary_norm.price_per_unit
            comparison['competitor_per_unit'] = competitor_norm.price_per_unit
            comparison['unit_label'] = '$/unit'
            comparison['can_compare_normalized'] = True
        
        # Calculate normalized savings if possible
        if comparison['can_compare_normalized']:
            primary_unit_price = comparison['primary_per_unit']
            competitor_unit_price = comparison['competitor_per_unit']
            
            comparison['normalized_savings'] = competitor_unit_price - primary_unit_price
            comparison['normalized_savings_pct'] = (
                (comparison['normalized_savings'] / primary_unit_price) * 100
                if primary_unit_price > 0 else 0
            )
        
        return comparison
    
    def _save_matches(self, matches: List[ProductMatch]) -> int:
        """Save validated matches to database"""
        saved_count = 0
        
        for match in matches:
            try:
                existing = self.db.query(DBProductMatch).filter(
                    DBProductMatch.primary_product_id == match.primary_id,
                    DBProductMatch.matched_product_id == match.matched_id
                ).first()
                
                if existing:
                    if match.confidence > existing.confidence_score:
                        existing.confidence_score = match.confidence
                        existing.match_type = match.match_type
                        saved_count += 1
                else:
                    db_match = DBProductMatch(
                        primary_product_id=match.primary_id,
                        matched_product_id=match.matched_id,
                        confidence_score=match.confidence,
                        match_type=match.match_type
                    )
                    self.db.add(db_match)
                    saved_count += 1
            
            except Exception as e:
                logger.error(f"Error saving match: {e}")
        
        self.db.commit()
        logger.info(f"Saved {saved_count} matches to database")
        return saved_count
    
    def _get_competitor_store_name_from_matches(self, matches: List) -> str:
        """Get competitor store name from the actual matches being processed"""
        try:
            if not matches:
                return "Competitor"
            
            # Get competitor store name from first match in current analysis
            first_match = matches[0]
            matched_product = self.db.query(Product).filter(
                Product.id == first_match.matched_product_id
            ).first()
            
            if matched_product and matched_product.store:
                return matched_product.store.name
                    
        except Exception as e:
            logger.debug(f"Could not determine competitor store: {e}")
            
        return "Competitor"
    
    def generate_price_report(self, primary_store: str, min_confidence: float = 0.65,
                             use_normalized: bool = True, competitor_store: str = None) -> None:
        """
        Generate comprehensive price comparison report.
        
        Args:
            primary_store: Name of primary store
            min_confidence: Minimum confidence threshold
            use_normalized: Whether to use per-unit pricing analysis
            competitor_store: Specific competitor to analyze (optional)
        """
        if use_normalized:
            self.generate_normalized_price_report(primary_store, min_confidence, competitor_store)
        else:
            self.generate_basic_price_report(primary_store, min_confidence, competitor_store)
    
    def generate_basic_price_report(self, primary_store: str, min_confidence: float = 0.65, competitor_store: str = None) -> None:
        """Generate basic price comparison report"""
        store = StoreCRUD.get_store_by_name(self.db, primary_store)
        if not store:
            logger.error(f"Store {primary_store} not found")
            return
        
        # Build query to filter matches by competitor if specified
        query = self.db.query(DBProductMatch).join(
            Product, DBProductMatch.primary_product_id == Product.id
        ).filter(
            Product.store_id == store.id,
            DBProductMatch.confidence_score >= min_confidence
        )
        
        # If competitor store is specified, filter by that competitor
        if competitor_store:
            competitor_store_obj = StoreCRUD.get_store_by_name(self.db, competitor_store)
            if competitor_store_obj:
                query = query.join(
                    Product.query.filter(Product.id == DBProductMatch.matched_product_id),
                    Product.store_id == competitor_store_obj.id
                )
        
        matches = query.order_by(DBProductMatch.confidence_score.desc()).all()
        
        # Filter matches by competitor store if specified
        if competitor_store:
            filtered_matches = []
            competitor_store_obj = StoreCRUD.get_store_by_name(self.db, competitor_store)
            if competitor_store_obj:
                for match in matches:
                    matched_product = self.db.query(Product).filter(
                        Product.id == match.matched_product_id
                    ).first()
                    if matched_product and matched_product.store_id == competitor_store_obj.id:
                        filtered_matches.append(match)
                matches = filtered_matches
        
        print(f"\n📊 Found {len(matches)} matches above confidence {min_confidence}")
        
        # Get competitor store name from the actual matches being processed
        final_competitor_name = competitor_store if competitor_store else self._get_competitor_store_name_from_matches(matches)
        
        comparisons = []
        
        for match in matches:
            try:
                primary_product = self.db.query(Product).filter(
                    Product.id == match.primary_product_id
                ).first()
                matched_product = self.db.query(Product).filter(
                    Product.id == match.matched_product_id
                ).first()
                
                if not primary_product or not matched_product:
                    continue
                
                primary_price = PriceCRUD.get_latest_price(self.db, primary_product.id)
                matched_price = PriceCRUD.get_latest_price(self.db, matched_product.id)
                
                if primary_price and matched_price:
                    savings = matched_price.price - primary_price.price  # CORRECTED: Positive = we're cheaper
                    savings_pct = (savings / matched_price.price * 100) if matched_price.price > 0 else 0
                    
                    comparisons.append({
                        'Product': primary_product.name[:40],
                        'Our Price': f"${primary_price.price:.2f}",
                        'Their Price': f"${matched_price.price:.2f}",
                        'Savings': f"${abs(savings):.2f}",
                        'Savings %': f"{savings_pct:+.1f}%",
                        'Match': f"{match.confidence_score:.3f}"
                    })
                    
            except Exception as e:
                logger.error(f"Error processing match: {e}")
        
        print("\n" + "="*80)
        print(f"PRICE COMPARISON REPORT - {primary_store}")
        print("="*80)
        
        if comparisons:
            comparisons.sort(key=lambda x: float(x['Savings %'][:-1]), reverse=True)
            
            print(f"\n📊 Top 20 Price Comparisons:")
            print(tabulate(comparisons[:20], headers='keys', tablefmt='grid'))
            
            total_products = len(comparisons)
            we_cheaper = len([c for c in comparisons if float(c['Savings %'][:-1]) > 0])
            they_cheaper = len([c for c in comparisons if float(c['Savings %'][:-1]) < 0])
            
            print(f"\n📈 Summary:")
            print(f"  • Total compared: {total_products}")
            print(f"  • Made in India cheaper: {we_cheaper} ({we_cheaper/total_products*100:.1f}%)")
            print(f"  • {final_competitor_name} cheaper: {they_cheaper} ({they_cheaper/total_products*100:.1f}%)")
    
    def generate_normalized_price_report(self, primary_store: str, min_confidence: float = 0.75, competitor_store: str = None) -> None:
        """Generate enhanced price report with per-unit analysis"""
        
        print("\n" + "="*100)
        print("🏢 BUSINESS INTELLIGENCE PRICE COMPARISON REPORT")
        print("="*100)
        
        # Get primary store
        primary_store_obj = StoreCRUD.get_store_by_name(self.db, primary_store)
        if not primary_store_obj:
            logger.error(f"Store {primary_store} not found")
            return
        
        # Get high-confidence matches for this primary store
        query = self.db.query(DBProductMatch).join(
            Product, DBProductMatch.primary_product_id == Product.id
        ).filter(
            Product.store_id == primary_store_obj.id,
            DBProductMatch.confidence_score >= min_confidence
        )
        
        high_conf_matches = query.order_by(DBProductMatch.confidence_score.desc()).all()
        
        # Filter matches by competitor store if specified
        if competitor_store:
            filtered_matches = []
            competitor_store_obj = StoreCRUD.get_store_by_name(self.db, competitor_store)
            if competitor_store_obj:
                for match in high_conf_matches:
                    matched_product = self.db.query(Product).filter(
                        Product.id == match.matched_product_id
                    ).first()
                    if matched_product and matched_product.store_id == competitor_store_obj.id:
                        filtered_matches.append(match)
                high_conf_matches = filtered_matches
        
        print(f"📈 Analysis based on {len(high_conf_matches)} HIGH-CONFIDENCE matches (≥{min_confidence})")
        
        if not high_conf_matches:
            print("⚠️ No high-confidence matches for analysis")
            return
        
        # Get competitor store name from the actual matches being processed
        final_competitor_name = competitor_store if competitor_store else self._get_competitor_store_name_from_matches(high_conf_matches)
        
        # Categorize normalized comparisons
        categorized_comparisons = defaultdict(list)
        
        for match in high_conf_matches:
            try:
                primary_product = self.db.query(Product).filter(
                    Product.id == match.primary_product_id
                ).first()
                matched_product = self.db.query(Product).filter(
                    Product.id == match.matched_product_id
                ).first()
                
                if not primary_product or not matched_product:
                    continue
                
                primary_price = PriceCRUD.get_latest_price(self.db, primary_product.id)
                matched_price = PriceCRUD.get_latest_price(self.db, matched_product.id)
                
                if primary_price and matched_price:
                    primary_dict = {
                        'name': primary_product.name,
                        'price': primary_price.price,
                        'category': primary_product.category
                    }
                    competitor_dict = {
                        'name': matched_product.name,
                        'price': matched_price.price,
                        'category': matched_product.category
                    }
                    
                    # Get normalized pricing comparison
                    price_comparison = self.compare_normalized_prices(primary_dict, competitor_dict)
                    
                    # Use normalized pricing if available, otherwise use absolute
                    if price_comparison['can_compare_normalized']:
                        # Use per-unit comparison
                        primary_unit_price = price_comparison['primary_per_unit']
                        competitor_unit_price = price_comparison['competitor_per_unit']
                        unit_label = price_comparison['unit_label']
                        
                        savings = competitor_unit_price - primary_unit_price  # CORRECTED: Positive = we're cheaper
                        savings_pct = (savings / competitor_unit_price * 100) if competitor_unit_price > 0 else 0
                        
                        comparison_entry = {
                            'Product': primary_product.name[:30],
                            'Our Price': f"{primary_unit_price:.2f} {unit_label}",
                            'Their Price': f"{competitor_unit_price:.2f} {unit_label}",
                            'Difference': f"{abs(savings):.2f} {unit_label}",
                            'Advantage': "Made in India" if savings > 0 else final_competitor_name,
                            'Impact %': f"{abs(savings_pct):.1f}%",
                            'Confidence': match.confidence_score,
                            'savings_amount': abs(savings),
                            'raw_savings_pct': savings_pct
                        }
                    else:
                        # Fall back to absolute pricing
                        savings = matched_price.price - primary_price.price  # CORRECTED: Positive = we're cheaper
                        savings_pct = (savings / matched_price.price * 100) if matched_price.price > 0 else 0
                        
                        comparison_entry = {
                            'Product': primary_product.name[:30],
                            'Our Price': f"${primary_price.price:.2f}",
                            'Their Price': f"${matched_price.price:.2f}",
                            'Difference': f"${abs(savings):.2f}",
                            'Advantage': "Made in India" if savings > 0 else final_competitor_name,
                            'Impact %': f"{abs(savings_pct):.1f}%",
                            'Confidence': match.confidence_score,
                            'savings_amount': abs(savings),
                            'raw_savings_pct': savings_pct
                        }
                    
                    category_group = self._get_category_group(primary_product.category)
                    categorized_comparisons[category_group].append(comparison_entry)
            
            except Exception as e:
                logger.error(f"Error in analysis: {e}")
        
        # Generate category reports
        for category, comparisons in categorized_comparisons.items():
            if not comparisons:
                continue
            
            print(f"\n🏷️  {category.upper()} CATEGORY ANALYSIS")
            print("-" * 80)
            
            # Sort by savings amount
            comparisons.sort(key=lambda x: x['savings_amount'], reverse=True)
            
            print(f"Top {min(7, len(comparisons))} Price Differences:")
            display_comps = [{k: v for k, v in comp.items() if k not in ['savings_amount', 'raw_savings_pct']} 
                           for comp in comparisons[:7]]
            print(tabulate(display_comps, headers='keys', tablefmt='grid'))
            
            # Category summary
            we_better = len([c for c in comparisons if c['raw_savings_pct'] > 0])
            they_better = len([c for c in comparisons if c['raw_savings_pct'] < 0])
            major_opportunities = len([c for c in comparisons if abs(c['raw_savings_pct']) > 15])
            
            print(f"\n📊 {category} Summary:")
            print(f"  • Products compared: {len(comparisons)}")
            print(f"  • Made in India cheaper: {we_better} ({we_better/len(comparisons)*100:.1f}%)")
            print(f"  • {final_competitor_name} cheaper: {they_better} ({they_better/len(comparisons)*100:.1f}%)")
            if major_opportunities:
                print(f"  • 🔥 Major price differences (>15%): {major_opportunities}")
        
        # Strategic insights
        self._generate_strategic_insights(categorized_comparisons)
    
    def _get_category_group(self, category: str) -> str:
        """Map categories to business groups"""
        category_groups = {
            'Staples': ['Rice', 'Flour', 'Dals and Grains', 'Oil & Ghee'],
            'Spices': ['Spices'],
            'Ready-to-Cook': ['Quick Cook'],
            'Dairy': ['Dairy'],
            'Snacks': ['Snacks'],
            'Beverages': ['Beverages', 'Tea, Coffee'],
            'Other': []
        }
        
        if not category:
            return 'Other'
            
        for group, categories in category_groups.items():
            if any(cat in category for cat in categories):
                return group
        return 'Other'
    
    def _generate_strategic_insights(self, categorized_comparisons: Dict) -> None:
        """Generate strategic business insights"""
        print(f"\n🎯 STRATEGIC INSIGHTS")
        print("="*60)
        
        all_comparisons = []
        for comparisons in categorized_comparisons.values():
            all_comparisons.extend(comparisons)
        
        if not all_comparisons:
            print("⚠️ Insufficient data for strategic insights")
            return
        
        total_products = len(all_comparisons)
        competitive_products = len([c for c in all_comparisons if abs(c['raw_savings_pct']) <= 10])
        we_overpriced = len([c for c in all_comparisons if c['raw_savings_pct'] < -20])  # We're more expensive
        we_underpriced = len([c for c in all_comparisons if c['raw_savings_pct'] > 20])   # We're much cheaper
        
        print(f"📈 Competitive Position:")
        print(f"  • Competitively priced (±10%): {competitive_products}/{total_products} ({competitive_products/total_products*100:.1f}%)")
        print(f"  • Made in India overpriced (>20%): {we_overpriced} products")
        print(f"  • Made in India underpriced (>20%): {we_underpriced} products")
        
        print(f"\n💡 Recommended Actions:")
        if we_overpriced > 0:
            print(f"  🔻 REDUCE PRICES: {we_overpriced} products need price adjustments")
        if we_underpriced > 0:
            print(f"  🔺 RAISE PRICES: {we_underpriced} products may have room for increases")
    
    def generate_match_report(self, primary_store: str) -> None:
        """Generate matching summary report with quality metrics"""
        store = StoreCRUD.get_store_by_name(self.db, primary_store)
        if not store:
            return
        
        products = ProductCRUD.get_products_by_store(self.db, store.id)
        total = len(products)
        
        # Count matches by confidence level for this specific store
        high_conf = self.db.query(DBProductMatch).join(
            Product, DBProductMatch.primary_product_id == Product.id
        ).filter(
            Product.store_id == store.id,
            DBProductMatch.confidence_score >= 0.8
        ).count()
        
        med_conf = self.db.query(DBProductMatch).join(
            Product, DBProductMatch.primary_product_id == Product.id
        ).filter(
            Product.store_id == store.id,
            DBProductMatch.confidence_score >= 0.65,
            DBProductMatch.confidence_score < 0.8
        ).count()
        
        with_matches = high_conf + med_conf
        
        print("\n" + "="*60)
        print(f"MATCHING SUMMARY - {primary_store}")
        print("="*60)
        print(f"Total Products: {total}")
        print(f"Products with Matches: {with_matches} ({with_matches/total*100:.1f}%)")
        print(f"\nMatch Quality:")
        print(f"  • High confidence (≥0.8): {high_conf}")
        print(f"  • Medium confidence (0.65-0.8): {med_conf}")
    
    def generate_quality_report(self, quality_report: Dict) -> None:
        """Generate detailed quality report from matching process"""
        if not quality_report:
            return
            
        print(f"\n📊 QUALITY REPORT:")
        print(f"  • Raw matches found: {quality_report.get('total_raw_matches', 0)}")
        print(f"  • Quality validated: {quality_report.get('validated_matches', 0)}")
        print(f"  • Rejected: {quality_report.get('rejected_matches', 0)}")
        
        if 'normalization_success_rate' in quality_report:
            print(f"  • Size normalization success: {quality_report['normalization_success_rate']*100:.1f}%")
        
        if 'rejection_reasons' in quality_report and quality_report['rejection_reasons']:
            print(f"  • Top rejection reasons:")
            sorted_reasons = sorted(quality_report['rejection_reasons'].items(), 
                                  key=lambda x: x[1], reverse=True)
            for reason, count in sorted_reasons[:5]:
                print(f"    - {reason}: {count}")


def main():
    """CLI interface for unified product matching"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Match products between stores with price analysis')
    parser.add_argument('--primary', default='Made in India Grocery',
                      help='Primary store name')
    parser.add_argument('--competitor', default='Real Canadian Superstore',
                      help='Competitor store name')
    parser.add_argument('--confidence', type=float, default=0.65,
                      help='Minimum confidence threshold')
    parser.add_argument('--report-only', action='store_true',
                      help='Generate reports only, no matching')
    parser.add_argument('--basic', action='store_true',
                      help='Use basic matching without normalization')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    matcher = DatabaseMatcher()
    
    if not args.report_only:
        print(f"🎯 Matching {args.primary} vs {args.competitor}")
        print(f"   Min confidence: {args.confidence}")
        print(f"   Mode: {'Basic' if args.basic else 'Enhanced with normalization'}")
        
        matches, quality_report = matcher.match_stores(
            args.primary, 
            args.competitor,
            min_confidence=args.confidence,
            save=True,
            use_normalization=not args.basic
        )
        
        print(f"✅ Found {len(matches)} validated matches")
        matcher.generate_quality_report(quality_report)
    
    # Generate reports
    matcher.generate_match_report(args.primary)
    matcher.generate_price_report(args.primary, args.confidence, use_normalized=not args.basic, competitor_store=args.competitor)


if __name__ == "__main__":
    main()