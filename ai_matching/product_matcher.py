# ai_matching/product_matcher.py
"""
AI Product Matcher with hybrid semantic/fuzzy matching and strict forbidden rules.
Prevents incorrect matches between incompatible product categories.
"""

import json
import logging
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from fuzzywuzzy import fuzz
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class SizeInfo:
    """Stores product size information"""
    value: float
    unit: str
    unit_type: str  # 'weight', 'volume', or 'count'
    original: str

@dataclass 
class ProductMatch:
    """Represents a match between two products"""
    primary_id: int
    matched_id: int
    confidence: float
    match_type: str  # 'exact', 'similar', or 'substitute'
    size_similarity: float = 0.0
    warnings: List[str] = field(default_factory=list)

class ProductMatcher:
    """Matches products using AI with strict category validation"""
    
    def __init__(self, config_dir: str = "ai_matching/config"):
        """Initialize with external configuration"""
        self.config_dir = Path(config_dir)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Load configuration files
        self.classifications = self._load_json("classifications.json")
        self.forbidden = self._load_json("forbidden.json")
        self.synonyms = self._load_json("synonyms.json")
        self.brands = self._load_json("brands.json")
        
        # Parse forbidden pairs for efficient matching
        self.forbidden_pairs = set()
        self.forbidden_patterns = []
        self._parse_forbidden_rules()
        
        # Brand set for quick lookups
        self.brand_set = set(self.brands.get("known_brands", []))
        
        # Regex pattern for size extraction
        self.size_pattern = re.compile(
            r'(\d+(?:\.\d+)?)\s*(kg|g|gm|lb|oz|ml|l|pcs?|each)', 
            re.IGNORECASE
        )
        
        # Load strict matching rules if available
        self.strict_categories = set()
        self.incompatible_categories = []
        if "matching_rules" in self.classifications:
            rules = self.classifications["matching_rules"]
            self.strict_categories = set(rules.get("strict_category_matching", []))
            self.incompatible_categories = rules.get("incompatible_categories", [])
        
        # Load penalty multipliers for matching rules
        self.penalty_multipliers = {}
        if "rules" in self.forbidden:
            self.penalty_multipliers = self.forbidden["rules"].get("penalty_multipliers", {})
        
        logger.info(f"Loaded {len(self.classifications.get('categories', []))} classifications, "
                   f"{len(self.forbidden_pairs)} forbidden pairs, "
                   f"{len(self.forbidden_patterns)} forbidden patterns")
    
    def _load_json(self, filename: str) -> Dict:
        """Load JSON configuration file"""
        filepath = self.config_dir / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
        logger.warning(f"Config file {filename} not found, using defaults")
        return {}
    
    def _parse_forbidden_rules(self):
        """Parse forbidden pairs into efficient matching structures"""
        for pair in self.forbidden.get("pairs", []):
            if isinstance(pair, list) and len(pair) == 2:
                # Handle patterns (contain special characters)
                if any(char in str(pair[0]) + str(pair[1]) for char in ['|', ':']):
                    self.forbidden_patterns.append(pair)
                else:
                    # Simple pair - add both directions
                    self.forbidden_pairs.add(tuple(pair))
                    self.forbidden_pairs.add(tuple(reversed(pair)))
    
    def classify_product(self, name: str) -> Tuple[str, str]:
        """
        Categorize product into type and subtype
        Returns: (type, subtype) e.g., ('masala', 'warm_masala')
        """
        name_lower = name.lower()
        
        # Apply synonyms first
        for syn_group in self.synonyms.get("groups", []):
            canonical = syn_group.get("canonical", "")
            for syn in syn_group.get("terms", []):
                if syn.lower() in name_lower:
                    name_lower = name_lower.replace(syn.lower(), canonical.lower())
        
        # Track all matching categories with priority
        matches = []
        
        for category in self.classifications.get("categories", []):
            priority = len(category.get("keywords", []))  # More specific = higher priority
            
            for keyword in category.get("keywords", []):
                if keyword.lower() in name_lower:
                    matches.append((
                        priority,
                        category["type"], 
                        category.get("subtype", "generic"),
                        keyword
                    ))
                    break
        
        # Return most specific match
        if matches:
            matches.sort(reverse=True)
            return matches[0][1], matches[0][2]
        
        return "other", "generic"
    
    def extract_size(self, name: str) -> SizeInfo:
        """Extract and normalize size information from product name"""
        match = self.size_pattern.search(name)
        if not match:
            return SizeInfo(0, "", "unknown", "")
        
        value = float(match.group(1))
        unit = match.group(2).lower()
        
        # Convert to base units
        conversions = {
            'kg': (1000, 'g', 'weight'),
            'lb': (453.6, 'g', 'weight'),
            'oz': (28.35, 'g', 'weight'),
            'l': (1000, 'ml', 'volume'),
            'g': (1, 'g', 'weight'),
            'gm': (1, 'g', 'weight'),
            'ml': (1, 'ml', 'volume'),
            'pcs': (1, 'pcs', 'count'),
            'each': (1, 'each', 'count')
        }
        
        if unit in conversions:
            factor, base_unit, unit_type = conversions[unit]
            return SizeInfo(value * factor, base_unit, unit_type, match.group(0))
        
        return SizeInfo(value, unit, "unknown", match.group(0))
    
    def calculate_size_similarity(self, size1: SizeInfo, size2: SizeInfo) -> float:
        """Calculate similarity between sizes with strict penalties"""
        # Different unit types get very low similarity
        if size1.unit_type != size2.unit_type:
            if size1.unit_type == "unknown" or size2.unit_type == "unknown":
                return 0.3
            return 0.1  # Very different products
        
        if size1.value == 0 or size2.value == 0:
            return 0.5  # Missing size info
        
        ratio = min(size1.value, size2.value) / max(size1.value, size2.value)
        
        # Bonus for exact matches
        if abs(ratio - 1.0) < 0.02:
            return 1.0
        
        # Stricter penalties for size differences
        if ratio < 0.5:  # More than 2x difference
            return ratio * 0.3
        elif ratio < 0.75:  # 25-50% difference
            return ratio * 0.6
        
        return ratio
    
    def normalize_name(self, name: str) -> str:
        """Clean and normalize product name for comparison"""
        # Remove size info
        size_info = self.extract_size(name)
        if size_info.original:
            name = name.replace(size_info.original, "")
        
        # Lowercase and clean special characters
        name = name.lower().strip()
        name = re.sub(r'[^\w\s]', ' ', name)
        
        # Remove common stop words
        stop_words = {'the', 'and', 'or', 'of', 'in', 'with', 'for', 'pure', 'organic', 'fresh', 'premium'}
        words = [w for w in name.split() if w not in stop_words]
        
        return ' '.join(words)
    
    def _check_forbidden_patterns(self, name1: str, name2: str, 
                                 type1: str, subtype1: str,
                                 type2: str, subtype2: str) -> bool:
        """Check against forbidden patterns"""
        name1_lower = name1.lower()
        name2_lower = name2.lower()
        
        for pattern in self.forbidden_patterns:
            pattern1, pattern2 = pattern
            
            # Check category-based patterns
            if ':' in str(pattern1):
                cat1_parts = pattern1.split(':')
                if len(cat1_parts) == 2:
                    if cat1_parts[0] == type1 and cat1_parts[1] == subtype1:
                        if self._matches_pattern(pattern2, name2_lower, type2, subtype2):
                            return True
            elif '|' in str(pattern1):
                # Multiple options pattern
                options1 = pattern1.split('|')
                options2 = pattern2.split('|') if '|' in str(pattern2) else [pattern2]
                
                if any(opt1 in name1_lower for opt1 in options1):
                    if any(opt2 in name2_lower for opt2 in options2):
                        return True
            else:
                # Simple keyword pattern
                if pattern1 in name1_lower and pattern2 in name2_lower:
                    return True
                if pattern2 in name1_lower and pattern1 in name2_lower:
                    return True
        
        return False
    
    def _matches_pattern(self, pattern: str, name: str, type_: str, subtype: str) -> bool:
        """Check if a pattern matches a product"""
        if ':' in pattern:
            parts = pattern.split(':')
            if len(parts) == 2:
                return parts[0] == type_ and parts[1] == subtype
        elif '|' in pattern:
            options = pattern.split('|')
            return any(opt in name for opt in options)
        else:
            return pattern in name
    
    def is_forbidden_match(self, primary: Dict, candidate: Dict,
                          type1: str, subtype1: str, 
                          type2: str, subtype2: str) -> Tuple[bool, str]:
        """
        Check if match is forbidden
        Returns: (is_forbidden, reason)
        """
        # Check exact forbidden pairs
        type_pair = (f"{type1}:{subtype1}", f"{type2}:{subtype2}")
        if type_pair in self.forbidden_pairs:
            return True, f"Forbidden type combination: {type1}:{subtype1} vs {type2}:{subtype2}"
        
        # Check type-level restrictions
        type_only_pair = (type1, type2)
        if type_only_pair in self.forbidden_pairs:
            return True, f"Forbidden type combination: {type1} vs {type2}"
        
        # Check pattern-based restrictions
        if self._check_forbidden_patterns(primary['name'], candidate['name'],
                                         type1, subtype1, type2, subtype2):
            return True, f"Matches forbidden pattern"
        
        # Check incompatible categories
        for incompat_pair in self.incompatible_categories:
            if len(incompat_pair) == 2:
                cat1, cat2 = incompat_pair
                if ((f"{type1}:{subtype1}" == cat1 and f"{type2}:{subtype2}" == cat2) or
                    (f"{type1}:{subtype1}" == cat2 and f"{type2}:{subtype2}" == cat1) or
                    (type1 == cat1 and type2 == cat2) or
                    (type1 == cat2 and type2 == cat1)):
                    return True, f"Incompatible categories: {cat1} vs {cat2}"
        
        # Specific hard-coded critical rules
        name1_lower = primary['name'].lower()
        name2_lower = candidate['name'].lower()
        
        # Never match baking with spices
        if ('baking powder' in name1_lower and any(spice in name2_lower for spice in ['cumin', 'coriander', 'turmeric', 'chili', 'masala'])) or \
           ('baking powder' in name2_lower and any(spice in name1_lower for spice in ['cumin', 'coriander', 'turmeric', 'chili', 'masala'])):
            return True, "Baking powder cannot match with spices"
        
        # Never match different specific spices
        spices = ['amchur', 'anardana', 'cumin', 'coriander', 'turmeric', 'chili']
        spice1 = next((s for s in spices if s in name1_lower), None)
        spice2 = next((s for s in spices if s in name2_lower), None)
        if spice1 and spice2 and spice1 != spice2:
            return True, f"Different spices: {spice1} vs {spice2}"
        
        # Never match coconut powder with curry powder
        if ('coconut' in name1_lower and 'curry' in name2_lower) or \
           ('curry' in name1_lower and 'coconut' in name2_lower):
            return True, "Coconut products cannot match with curry products"
        
        return False, ""
    
    def calculate_hybrid_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate hybrid similarity with reduced weight on semantic matching
        40% semantic, 60% fuzzy for better Indian product matching
        """
        # Normalize names
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Check for minimum word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        common_words = words1 & words2
        
        # If no common words, very low score
        if len(common_words) == 0:
            return 0.1
        
        # Semantic similarity (40%)
        embeddings = self.model.encode([norm1, norm2])
        semantic_sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        
        # Fuzzy similarity (60%)
        fuzzy_sim = fuzz.token_sort_ratio(norm1, norm2) / 100.0
        
        # Weighted combination
        hybrid_score = (semantic_sim * 0.4) + (fuzzy_sim * 0.6)
        
        # Brand matching adjustments
        brand1 = self._extract_brand(name1)
        brand2 = self._extract_brand(name2)
        if brand1 and brand1 == brand2:
            hybrid_score = min(hybrid_score + 0.1, 1.0)
        elif brand1 and brand2 and brand1 != brand2:
            # Penalty for different brands
            hybrid_score *= 0.85
        
        return float(hybrid_score)
    
    def _extract_brand(self, name: str) -> Optional[str]:
        """Extract brand from product name"""
        name_words = name.lower().split()
        for brand in self.brand_set:
            brand_lower = brand.lower()
            if brand_lower in name_words or brand_lower in name.lower():
                return brand
        return None
    
    def calculate_confidence(self, primary: Dict, candidate: Dict) -> Tuple[float, List[str]]:
        """
        Calculate match confidence with strict category validation
        Returns (confidence_score, warnings_list)
        """
        warnings = []
        
        # Get product classifications
        p_type, p_subtype = self.classify_product(primary['name'])
        c_type, c_subtype = self.classify_product(candidate['name'])
        
        # Check forbidden combinations first
        is_forbidden, reason = self.is_forbidden_match(
            primary, candidate, p_type, p_subtype, c_type, c_subtype
        )
        if is_forbidden:
            warnings.append(reason)
            return 0.0, warnings
        
        # Calculate base similarity
        base_score = self.calculate_hybrid_similarity(primary['name'], candidate['name'])
        
        # Early rejection for very low similarity
        if base_score < 0.3:
            warnings.append(f"Very low name similarity: {base_score:.2f}")
            return 0.0, warnings
        
        # Apply category penalties
        if p_type != c_type:
            # Check for specific penalty
            penalty_key = f"different_{p_type}_vs_{c_type}"
            if penalty_key in self.penalty_multipliers:
                base_score *= self.penalty_multipliers[penalty_key]
            else:
                base_score *= 0.5  # Heavy default penalty
            warnings.append(f"Type mismatch: {p_type} vs {c_type}")
            
        elif p_subtype != c_subtype:
            # Different subtypes within same type
            if f"{p_type}:{p_subtype}" in self.strict_categories or \
               f"{c_type}:{c_subtype}" in self.strict_categories:
                # Strict category matching required
                base_score *= 0.3
                warnings.append(f"Strict subtype mismatch: {p_subtype} vs {c_subtype}")
            else:
                base_score *= 0.7
                warnings.append(f"Subtype mismatch: {p_subtype} vs {c_subtype}")
        else:
            # Exact type match - bonus
            base_score = min(base_score + 0.15, 1.0)
        
        # Size similarity check
        p_size = self.extract_size(primary['name'])
        c_size = self.extract_size(candidate['name'])
        size_sim = self.calculate_size_similarity(p_size, c_size)
        
        # Apply size penalties
        if size_sim < 0.5:
            base_score *= 0.5
            warnings.append(f"Significant size mismatch: {p_size.value}{p_size.unit} vs {c_size.value}{c_size.unit}")
        elif size_sim < 0.75:
            base_score *= 0.8
            warnings.append(f"Size difference: {p_size.value}{p_size.unit} vs {c_size.value}{c_size.unit}")
        elif size_sim > 0.95:
            base_score = min(base_score + 0.05, 1.0)
        
        # Price sanity check
        if primary.get('price') and candidate.get('price'):
            price_ratio = max(primary['price'], candidate['price']) / min(primary['price'], candidate['price'])
            if price_ratio > 10:
                base_score *= 0.6
                warnings.append(f"Large price difference: {price_ratio:.1f}x")
            elif price_ratio > 5:
                base_score *= 0.8
                warnings.append(f"Price difference: {price_ratio:.1f}x")
        
        # Extra validation for borderline matches
        if 0.6 < base_score < 0.75:
            # Extra scrutiny for borderline matches
            if len(warnings) > 2:
                base_score *= 0.8  # Too many warnings
            
            # Check if only size matches
            name_words1 = set(primary['name'].lower().split())
            name_words2 = set(candidate['name'].lower().split())
            common_meaningful = name_words1 & name_words2 - {'g', 'kg', 'ml', 'l', 'oz', 'lb'}
            if len(common_meaningful) < 2:
                base_score *= 0.7
                warnings.append("Insufficient common meaningful words")
        
        return min(max(base_score, 0.0), 1.0), warnings
    
    def find_matches(self, primary: Dict, candidates: List[Dict], 
                    min_confidence: float = 0.65, max_matches: int = 3) -> List[ProductMatch]:
        """Find best matches for a primary product with strict validation"""
        matches = []
        
        for candidate in candidates:
            if candidate['id'] == primary['id']:
                continue
            
            confidence, warnings = self.calculate_confidence(primary, candidate)
            
            if confidence >= min_confidence:
                # Determine match type
                if confidence >= 0.9:
                    match_type = 'exact'
                elif confidence >= 0.75:
                    match_type = 'similar'
                else:
                    match_type = 'substitute'
                
                p_size = self.extract_size(primary['name'])
                c_size = self.extract_size(candidate['name'])
                size_sim = self.calculate_size_similarity(p_size, c_size)
                
                matches.append(ProductMatch(
                    primary_id=primary['id'],
                    matched_id=candidate['id'],
                    confidence=confidence,
                    match_type=match_type,
                    size_similarity=size_sim,
                    warnings=warnings
                ))
        
        # Sort by confidence and return top matches
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[:max_matches]
    
    def batch_match(self, primaries: List[Dict], candidates: List[Dict],
                   min_confidence: float = 0.65) -> List[ProductMatch]:
        """Batch process all primary products"""
        all_matches = []
        
        for i, primary in enumerate(primaries):
            if i % 50 == 0:
                logger.info(f"Processing {i+1}/{len(primaries)} products")
            
            matches = self.find_matches(primary, candidates, min_confidence)
            all_matches.extend(matches)
        
        logger.info(f"Found {len(all_matches)} total matches")
        return all_matches