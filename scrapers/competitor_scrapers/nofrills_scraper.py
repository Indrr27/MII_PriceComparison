# scrapers/competitor_scrapers/nofrills_scraper.py - No Frills scraper (Loblaw family)

from ..base_scraper import BaseScraper
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import List, Dict
import re
import time
import random
import urllib.parse

class NoFrillsScraper(BaseScraper):
    """🆕 No Frills scraper - Loblaw family store with same layout as Superstore"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless=headless, delay=3.0)
        self.base_url = "https://www.nofrills.ca"
        self.search_url = "https://www.nofrills.ca/en/search"
        
        # Same category mapping as Superstore (Loblaw family)
        self.category_mapping = {
            'Spices': ['spice', 'seasoning', 'powder', 'turmeric', 'cumin', 'coriander',
                      'masala', 'curry', 'chili', 'pepper', 'cardamom', 'cinnamon', 'cloves',
                      'bay leaves', 'mustard seeds', 'fennel seeds', 'fenugreek', 'asafoetida',
                      'amchur', 'kashmiri chili', 'sambar powder', 'rasam powder'],
            
            'Rice': ['rice', 'quinoa', 'barley', 'bulgur', 'oats', 'grain', 'basmati', 'jasmine',
                    'poha', 'sooji', 'vermicelli'],
            
            'Flour': ['flour', 'baking', 'yeast', 'atta', 'besan', 'gram flour', 'wheat flour',
                     'all purpose flour', 'chickpea flour'],
            
            'Dals and Grains': ['lentil', 'bean', 'chickpea', 'dal', 'split pea', 'toor', 'urad', 'moong',
                               'chana', 'rajma', 'kidney beans', 'black beans'],
            
            'Sauces and Pastes': ['sauce', 'paste', 'coconut milk', 'pickle', 'achar',
                                 'chutney', 'tahini', 'vinegar', 'soy sauce', 'tomato paste'],
            
            'Cosmetics and Oils': ['oil', 'coconut oil', 'sesame oil', 'olive oil', 'mustard oil',
                                  'almond oil', 'ghee'],
            
            'Snacks': ['papad', 'pappadum', 'murukku', 'sev', 'bhujia', 'chips', 'crackers'],
            
            'Sweets': ['halwa', 'jalebi', 'gulab jamun', 'barfi', 'rasgulla', 'mithai'],
            
            'Beverages': ['juice', 'drink', 'beverage', 'lassi', 'tea', 'coffee'],
            
            'Dairy': ['milk', 'yogurt', 'curd', 'paneer', 'cheese', 'butter', 'cream'],
            
            'Biscuits and Cookies': ['biscuit', 'cookie', 'cracker'],
            
            'Tea, Coffee & Milk Products': ['tea', 'coffee', 'milk powder', 'creamer'],
            
            'Quick Cook': ['instant', 'ready', 'mix', 'noodles', 'pasta']
        }
        
        # Same target searches as Superstore - these work well for Indian groceries
        self.target_searches = [
            # Spices & Seasonings
            "turmeric", "cumin", "coriander", "garam masala", "curry powder",
            "chili powder", "cardamom", "cinnamon", "cloves", "bay leaves",
            "mustard seeds", "fennel seeds", "fenugreek", "asafoetida", "amchur",
            "kashmiri chili", "sambar powder", "rasam powder",
            
            # Rice & Grains
            "basmati rice", "jasmine rice", "long grain rice", "brown rice",
            "quinoa", "bulgur", "barley", "poha", "sooji", "vermicelli",
            
            # Flour & Baking
            "chickpea flour", "besan", "gram flour", "rice flour", 
            "whole wheat flour", "atta", "all purpose flour",
            "baking powder", "baking soda",
            
            # Lentils & Beans
            "red lentils", "green lentils", "black beans", "chickpeas", 
            "kidney beans", "split peas", "toor dal", "urad dal", 
            "moong dal", "chana dal", "rajma",
            
            # Oils & Vinegars
            "coconut oil", "sesame oil", "mustard oil", "olive oil",
            "vegetable oil", "ghee", "apple cider vinegar",
            
            # Canned/Packaged
            "coconut milk", "tomato paste", "tomato sauce", "pasta",
            "naan", "tortilla", "pita bread", "paneer", "yogurt", "curd",
            
            # Condiments & Sauces
            "soy sauce", "fish sauce", "sriracha", "chili sauce",
            "sesame seeds", "tahini", "pickle", "achar", "chutney",
            
            # Snacks & Sweets
            "papad", "pappadum", "murukku", "sev", "bhujia", "halwa",
            "jalebi", "gulab jamun", "barfi", "rasgulla", "mithai",
            
            # International brands that might overlap
            "everest", "mdh", "shan", "trs", "natco", "heera", "swad",
            "deep", "tata", "amul", "nandini",
            
            # Indian specialty items
            "ghee", "paneer", "atta", "besan", "dal", "chana", "moong", 
            "urad", "toor dal", "rajma", "sooji", "vermicelli", "poha", 
            "papad", "pickle", "achar", "chutney", "lassi", "yogurt", 
            "curd", "pappad", "murukku", "sev", "bhujia", "idli", "dosa", 
            "vada", "sambar", "rasam", "biriyani", "pulao", "halwa", 
            "jalebi", "gulab jamun", "barfi", "rasgulla"
        ]
    
    def get_store_info(self) -> Dict:
        return {
            "name": "No Frills",
            "location": "Georgetown, Ontario", 
            "website": self.base_url,
            "store_type": "Discount Supermarket"
        }
    
    def scrape_products(self) -> List[Dict]:
        """Scrape relevant products from No Frills"""
        all_products = []
        seen_products = set()  # Avoid duplicates across searches
        
        for i, search_term in enumerate(self.target_searches):
            self.logger.info(f"Searching for '{search_term}' ({i+1}/{len(self.target_searches)})")
            
            try:
                # Scrape multiple pages per search term
                products = self._search_products(search_term, max_pages=5)
                
                # Filter out duplicates and add to collection
                new_products = 0
                for product in products:
                    product_key = f"{product['name']}_{product['price']}"
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        all_products.append(product)
                        new_products += 1
                
                self.logger.info(f"Found {new_products} new products for '{search_term}' (Total: {len(all_products)})")
                
                # Human-like delay between searches
                delay = random.uniform(5.0, 10.0)
                time.sleep(delay)
                
            except Exception as e:
                self.logger.error(f"Error searching for '{search_term}': {e}")
                continue
        
        # Filter products for relevance
        relevant_products = self._filter_relevant_products(all_products)
        
        self.logger.info(f"Scraping complete: {len(relevant_products)} relevant products from {len(all_products)} total")
        return relevant_products
    
    def _search_products(self, search_term: str, max_pages: int = 5) -> List[Dict]:
        """Search for products using a specific term (same logic as Superstore)"""
        products = []
        
        for page in range(1, max_pages + 1):
            try:
                # Build search URL (No Frills uses similar structure)
                params = {
                    'search-bar': search_term,
                    'page': str(page)
                }
                search_url = f"{self.search_url}?{urllib.parse.urlencode(params)}"
                
                self.logger.debug(f"Searching page {page}: {search_url}")
                
                # Navigate and wait for results (same selectors as Superstore)
                page_source = self.wait_and_get_page_source(
                    search_url, 
                    wait_element="[data-testid='product-tile']"
                )
                
                soup = BeautifulSoup(page_source, 'html.parser')
                page_products = self._extract_products_from_search_page(soup)
                
                if not page_products:
                    self.logger.debug(f"No products found on page {page} for '{search_term}'")
                    break  # No more products
                
                products.extend(page_products)
                self.logger.debug(f"Found {len(page_products)} products on page {page}")
                
                # Check if there's a next page
                if not self._has_next_page(soup):
                    break
                
                # Add human-like delay between pages
                time.sleep(random.uniform(1.5, 3.5))
                
            except Exception as e:
                self.logger.warning(f"Error on page {page} for '{search_term}': {e}")
                break
        
        return products
    
    def _extract_products_from_search_page(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract products from search results page (same as Superstore)"""
        products = []
        
        # Try multiple selectors for product tiles
        product_selectors = [
            "[data-testid='product-tile']",
            ".product-tile",
            ".product-item",
            "[class*='product']",
            ".search-result-item"
        ]
        
        product_elements = []
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                product_elements = elements
                self.logger.debug(f"Found {len(elements)} products using selector: {selector}")
                break
        
        if not product_elements:
            # Fallback: look for any elements with product-like attributes
            product_elements = soup.find_all(attrs={"data-testid": re.compile("product", re.I)})
            if not product_elements:
                self.logger.warning("No product elements found on page")
                return products
        
        for element in product_elements:
            try:
                product_data = self._extract_product_from_element(element)
                if product_data:
                    products.append(product_data)
            except Exception as e:
                self.logger.debug(f"Error extracting product: {e}")
                continue
        
        return products
    
    def _extract_product_from_element(self, element) -> Dict:
        """Extract product data from a single product element (enhanced size detection)"""
        try:
            # Extract product name
            name_selectors = [
                "[data-testid='product-title']",
                ".product-title",
                ".product-name",
                "h3", "h4", "a[href*='/product/']"
            ]
            
            product_name = None
            product_url = None
            
            for selector in name_selectors:
                name_elem = element.select_one(selector)
                if name_elem:
                    product_name = name_elem.get_text(strip=True)
                    if name_elem.name == 'a':
                        product_url = name_elem.get('href')
                    break
            
            if not product_name:
                return None

            # Enhanced size detection strategies (same as Superstore)
            size_text = None
            
            # Strategy 1: Look for size in separate elements
            size_selectors = [
                "span[class*='size']",
                "div[class*='size']", 
                "span[class*='weight']",
                "div[class*='weight']",
                "span[class*='volume']",
                "div[class*='volume']",
                ".product-size",
                ".product-weight",
                ".product-volume",
                "[data-testid*='size']",
                "[data-testid*='weight']",
                "[data-testid*='volume']"
            ]
            
            for selector in size_selectors:
                size_elem = element.select_one(selector)
                if size_elem:
                    potential_size = size_elem.get_text(strip=True)
                    if re.search(r'\d+\s*(ml|l|g|kg|lb|oz|fl\s?oz)', potential_size, re.IGNORECASE):
                        size_text = potential_size
                        self.logger.debug(f"Found size using selector {selector}: {size_text}")
                        break
            
            # Strategy 2: Look for size patterns in nearby text
            if not size_text:
                all_text_elements = element.find_all(['span', 'div', 'p'], string=True)
                for elem in all_text_elements:
                    text = elem.get_text(strip=True)
                    size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:ml|l|g|kg|lb|lbs|oz|fl\s?oz))', text, re.IGNORECASE)
                    if size_match:
                        size_text = size_match.group(1)
                        self.logger.debug(f"Found size in text element: {size_text}")
                        break
            
            # Strategy 3: Look in the entire element text
            if not size_text:
                full_text = element.get_text()
                size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:ml|l|g|kg|lb|lbs|oz|fl\s?oz))', full_text, re.IGNORECASE)
                if size_match:
                    size_text = size_match.group(1)
                    self.logger.debug(f"Found size in full element text: {size_text}")
            
            # Strategy 4: Check product attributes
            if not size_text:
                for attr in ['data-size', 'data-weight', 'data-volume', 'title', 'alt']:
                    attr_value = element.get(attr, '')
                    if attr_value:
                        size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:ml|l|g|kg|lb|lbs|oz|fl\s?oz))', attr_value, re.IGNORECASE)
                        if size_match:
                            size_text = size_match.group(1)
                            self.logger.debug(f"Found size in {attr} attribute: {size_text}")
                            break
            
            # Strategy 5: Look in adjacent elements
            if not size_text:
                parent = element.parent
                if parent:
                    nearby_elements = parent.find_all(string=re.compile(r'\d+\s*(ml|l|g|kg|lb|oz)', re.IGNORECASE))
                    if nearby_elements:
                        for nearby_text in nearby_elements:
                            size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:ml|l|g|kg|lb|lbs|oz|fl\s?oz))', str(nearby_text), re.IGNORECASE)
                            if size_match:
                                size_text = size_match.group(1)
                                self.logger.debug(f"Found size in nearby element: {size_text}")
                                break
            
            # Append size to product name if found
            if size_text:
                size_text = re.sub(r'\s+', ' ', size_text.strip())
                product_name = f"{product_name} {size_text}"
                self.logger.info(f"✅ Enhanced product name with size: {product_name}")
            else:
                self.logger.warning(f"⚠️ No size found for product: {product_name}")

            # Extract price (same selectors as Superstore)
            price_selectors = [
                "[data-testid='price']",
                ".price",
                ".product-price",
                "[class*='price']",
                ".pricing"
            ]
            
            price = None
            for selector in price_selectors:
                price_elem = element.select_one(selector)
                if price_elem:
                    price = self.extract_price_from_text(price_elem.get_text())
                    if price:
                        break
            
            # If no price found in specific elements, search all text
            if not price:
                price = self.extract_price_from_text(element.get_text())
            
            if not price:
                return None  # Skip products without prices
            
            # Build product URL if not found
            if not product_url:
                link_elem = element.find('a', href=True)
                if link_elem:
                    product_url = link_elem['href']
            
            if product_url and not product_url.startswith('http'):
                product_url = self.base_url + product_url
            
            # Extract additional info
            brand = self._extract_brand_from_name(product_name)
            size = self._extract_size_from_name(product_name)
            category = self._guess_category_from_name(product_name)
            
            return {
                'name': self._clean_product_name(product_name),
                'price': price,
                'url': product_url or "",
                'brand': brand,
                'size': size,
                'category': category
            }
            
        except Exception as e:
            self.logger.debug(f"Error extracting product from element: {e}")
            return None
    
    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page (same as Superstore)"""
        next_selectors = [
            "a[aria-label*='next']",
            ".pagination-next",
            "[data-testid='next-page']",
            "a[href*='page=']"
        ]
        
        for selector in next_selectors:
            if soup.select_one(selector):
                return True
        
        return False
    
    def _filter_relevant_products(self, products: List[Dict]) -> List[Dict]:
        """Filter products for relevance to Indian grocery comparison (same as Superstore)"""
        relevant_products = []
        
        # Expanded relevant keywords
        relevant_keywords = [
            # Spice-related
            'spice', 'seasoning', 'masala', 'powder', 'turmeric', 'cumin', 'coriander',
            'cardamom', 'cinnamon', 'cloves', 'curry', 'chili', 'pepper', 'amchur', 'hing',
            'sambar', 'rasam',
            
            # Grain/flour related
            'rice', 'flour', 'wheat', 'grain', 'basmati', 'jasmine', 'lentil',
            'chickpea', 'dal', 'beans', 'quinoa', 'poha', 'sooji', 'vermicelli', 'barley',
            'bulgur', 'atta', 'besan',
            
            # Oil/cooking
            'oil', 'coconut', 'sesame', 'olive', 'ghee', 'vanaspati',
            
            # International/ethnic brands
            'everest', 'mdh', 'shan', 'trs', 'natco', 'heera', 'swad', 'deep',
            
            # Basic cooking ingredients
            'salt', 'sugar', 'vinegar', 'sauce', 'paste', 'milk', 'yogurt', 'curd',
            
            # Indian specialty items
            'paneer', 'papad', 'pappadum', 'murukku', 'sev', 'bhujia', 'pickle',
            'achar', 'chutney', 'lassi', 'halwa', 'jalebi', 'gulab jamun', 'barfi',
            'rasgulla', 'mithai', 'idli', 'dosa', 'vada', 'biriyani', 'pulao'
        ]
        
        # Expanded irrelevant keywords
        irrelevant_keywords = [
            'frozen', 'fresh', 'refrigerated', 'ready to eat', 'prepared', 'cooked',
            'sandwich', 'pizza', 'cake', 'cookie', 'chocolate', 'candy',
            'soda', 'juice', 'water', 'beer', 'wine', 'alcohol', 'coffee', 'tea bags',
            'shampoo', 'soap', 'detergent', 'paper', 'cleaning', 'pet', 'dog', 'cat',
            'toy', 'game', 'battery', 'light bulb', 'broom', 'mop', 'shower', 'deodorant',
            'toothpaste', 'razor', 'diaper', 'baby', 'furniture', 'clothing', 'electronics',
            'hardware', 'garden', 'plant', 'flower', 'candle', 'cookware', 'utensil'
        ]
        
        for product in products:
            name_lower = product['name'].lower()
            
            # Check if relevant
            is_relevant = any(keyword in name_lower for keyword in relevant_keywords)
            
            # Check if irrelevant
            is_irrelevant = any(keyword in name_lower for keyword in irrelevant_keywords)
            
            # Additional relevance scoring
            relevance_score = 0
            
            # Boost score for specific patterns
            if re.search(r'\b(organic|natural|whole|pure)\b', name_lower):
                relevance_score += 1
            if re.search(r'\b\d+\s*(g|kg|lb|oz|ml|l)\b', name_lower):
                relevance_score += 1  # Has size indication
            if len(product['name'].split()) <= 6:
                relevance_score += 1  # Simple product names are often basic ingredients
            
            # Include if relevant and not irrelevant, or high relevance score
            if (is_relevant and not is_irrelevant) or relevance_score >= 2:
                relevant_products.append(product)
                self.logger.debug(f"Included: {product['name']} (relevant: {is_relevant}, score: {relevance_score})")
            else:
                self.logger.debug(f"Filtered out: {product['name']}")
        
        return relevant_products
    
    def _extract_brand_from_name(self, product_name: str) -> str:
        """Extract brand from product name (same as Superstore)"""
        # Known brands that appear in No Frills
        known_brands = [
            'Club House', 'McCormick', 'PC', 'No Name', 'Organics',
            'Simply Organic', 'Spice Islands', 'Tilda', 'Uncle Ben',
            'Minute Rice', 'Robin Hood', 'Five Roses', 'Everest',
            'MDH', 'Shan', 'TRS', 'Natco', 'Heera', 'Swad', 'Deep',
            'President\'s Choice', 'Compliments'  # No Frills specific brands
        ]
        
        name_upper = product_name.upper()
        
        for brand in known_brands:
            if brand.upper() in name_upper:
                return brand
        
        # Fallback: take first word if it's capitalized
        words = product_name.split()
        if words and words[0].istitle() and len(words[0]) > 2:
            return words[0]
        
        return "Unknown"
    
    def _extract_size_from_name(self, product_name: str) -> str:
        """Extract size from product name (same as Superstore)"""
        size_patterns = [
            r'(\d+(?:\.\d+)?\s*(?:kg|g|gm|lb|lbs|oz|ml|l))',
            r'(\d+\s*x\s*\d+(?:\.\d+)?\s*(?:kg|g|gm|lb|lbs|oz|ml|l))',
            r'(\d+\s*pack)',
            r'(\d+\s*count)'
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, product_name, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Add check for "each" when no size pattern found
        if "each" in product_name.lower():
            return "1 each"
        
        return "Unknown"
    
    def _guess_category_from_name(self, product_name: str) -> str:
        """Guess category using Made in India compatible categories (same as Superstore)"""
        name_lower = product_name.lower()
        
        # Check against our enhanced category mapping
        for category, keywords in self.category_mapping.items():
            if any(keyword in name_lower for keyword in keywords):
                self.logger.debug(f"Categorized '{product_name}' as '{category}'")
                return category
        
        # Fallback categories
        if any(word in name_lower for word in ['organic', 'natural']):
            return "Other"
        
        return "Unknown"
    
    def _clean_product_name(self, name: str) -> str:
        """Clean product name (same as Superstore)"""
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Remove common prefixes/suffixes
        prefixes_to_remove = ['PC ', 'No Name ', 'Great Value ', 'President\'s Choice ']
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):]
        
        return name.strip()

# Usage example
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    scraper = NoFrillsScraper(headless=False)
    products = scraper.scrape_with_error_handling()
    
    print(f"Scraped {len(products)} relevant products:")
    for product in products[:10]:  # Show first 10
        print(f"- {product['name']} | ${product['price']} | {product['brand']} | {product['category']}")