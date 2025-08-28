# scrapers/competitor_scrapers/indianfrootland_scraper.py

from ..base_scraper import BaseScraper
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from typing import List, Dict, Optional
import re
import time
import random
import logging

class IndianFrootlandScraper(BaseScraper):
    """Scraper for Indian Frootland website - follows similar approach to AFC Grocery"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless=headless, delay=3.0)
        self.base_url = "https://indianfrootland.com"
        self.search_url = "https://indianfrootland.com/search"
        self.shop_url = "https://indianfrootland.com/shop"
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Map product categories to keywords for Indian groceries
        self.category_mapping = {
            'Flour': ['flour', 'atta', 'besan', 'maida', 'rice flour', 'gram flour', 'wheat flour', 'chakki'],
            'Rice': ['rice', 'basmati', 'jasmine', 'sona masoori', 'ponni', 'parboiled', 'brown rice'],
            'Dals and Grains': ['dal', 'lentil', 'toor', 'urad', 'moong', 'chana', 'rajma', 'kidney beans', 'masoor', 'arhar'],
            'Spices': ['spice', 'masala', 'powder', 'turmeric', 'cumin', 'coriander', 'chili', 'garam masala', 
                      'sambar', 'rasam', 'curry', 'cardamom', 'cloves', 'cinnamon', 'black pepper', 'fenugreek'],
            'Cosmetics and Oils': ['oil', 'mustard oil', 'sesame oil', 'coconut oil', 'sunflower oil', 'ghee', 
                                   'olive oil', 'almond oil', 'hair oil'],
            'Edible Oil & Ghee': ['oil', 'mustard oil', 'sesame oil', 'coconut oil', 'sunflower oil', 'ghee', 'vanaspati'],
            'Sauces and Pastes': ['sauce', 'paste', 'chutney', 'pickle', 'achaar', 'ketchup', 'tamarind'],
            'Snacks': ['namkeen', 'chips', 'bhujia', 'sev', 'mixture', 'papad', 'cookies', 'biscuit', 'murukku', 'chakli'],
            'Sweets': ['mithai', 'laddu', 'barfi', 'halwa', 'gulab jamun', 'rasgulla', 'sweet', 'jalebi', 'soan papdi'],
            'Tea, Coffee & Milk Products': ['tea', 'chai', 'coffee', 'green tea', 'black tea', 'milk powder'],
            'Noodles and Pasta': ['noodles', 'maggi', 'pasta', 'vermicelli', 'sevai', 'hakka noodles'],
            'Beverages': ['juice', 'drink', 'lassi', 'sherbet', 'soda', 'rooh afza'],
            'Frozen Items': ['frozen', 'paratha', 'samosa', 'naan', 'roti', 'kathi roll'],
            'Dairy': ['paneer', 'milk', 'yogurt', 'cheese', 'butter', 'cream', 'dahi', 'ghee'],
            'Pooja Items': ['pooja', 'agarbatti', 'camphor', 'diya', 'kumkum', 'incense', 'dhoop'],
            'Quick Cook': ['instant', 'ready', 'mix', 'dosa mix', 'idli mix', 'khaman mix', 'dhokla mix'],
            'Biscuits and Cookies': ['biscuit', 'cookie', 'rusk', 'parle', 'britannia', 'marie']
        }
        
        # Search terms optimized for Indian Frootland's inventory
        self.target_searches = [
            # Oils
            "mustard oil", "coconut oil", "sesame oil", "sunflower oil", "kachi ghani",
            "olive oil", "groundnut oil", "rice bran oil",
            
            # Flours
            "atta", "flour", "besan", "maida", "rice flour", "chakki atta", "whole wheat",
            "gram flour", "corn flour", "sooji", "rava",
            
            # Rice varieties
            "basmati rice", "sona masoori", "jasmine rice", "brown rice", "parboiled rice",
            "ponni rice", "kolam rice", 
            
            # Dals and Pulses
            "toor dal", "moong dal", "chana dal", "urad dal", "masoor dal",
            "rajma", "kabuli chana", "black chana", "lentils",
            
            # Spices and Masalas
            "turmeric", "cumin", "coriander", "garam masala", "chili powder",
            "sambar powder", "rasam powder", "curry powder", "chat masala",
            "pav bhaji masala", "biryani masala", "kitchen king", "tandoori masala",
            
            # Ready mixes
            "dosa mix", "idli mix", "dhokla mix", "gulab jamun mix", "halwa mix",
            "upma mix", "poha", "khaman mix",
            
            # Snacks
            "namkeen", "bhujia", "sev", "mixture", "papad", "murukku", "chakli",
            "mathri", "khakhra", "fryums",
            
            # Pickles and Chutneys
            "pickle", "achaar", "chutney", "sauce", "mango pickle", "lime pickle",
            "mixed pickle", "garlic pickle",
            
            # Tea and Coffee
            "tea", "chai", "coffee", "green tea", "masala chai", "brooke bond",
            "taj mahal", "red label", "society tea",
            
            # Sweets
            "mithai", "laddu", "barfi", "halwa", "rasgulla", "gulab jamun",
            "soan papdi", "jalebi", "kaju katli",
            
            # Noodles and Pasta
            "maggi", "noodles", "pasta", "hakka noodles", "vermicelli", "sevai",
            
            # Frozen items
            "paratha", "samosa", "spring roll", "naan", "roti", "kathi roll",
            
            # Brands
            "sher", "aashirvaad", "fortune", "mdh", "everest", "shan", "mother's recipe",
            "priya", "nirav", "deep", "haldiram", "bikaji", "dabur", "patanjali",
            "tata", "parle", "britannia", "amul", "nestle", "ktc"
        ]
    
    def get_store_info(self) -> Dict:
        """Return basic store information"""
        return {
            "name": "Indian Frootland",
            "location": "Brampton, ON",
            "website": self.base_url,
            "store_type": "Indian Grocery"
        }
    
    def scrape_products(self) -> List[Dict]:
        """Main scraping method using targeted searches"""
        all_products = []
        seen_products = set()
        
        self.logger.info("Starting Indian Frootland scraping...")
        
        # Use targeted searches
        for i, search_term in enumerate(self.target_searches):
            self.logger.info(f"Searching for '{search_term}' ({i+1}/{len(self.target_searches)})")
            
            try:
                products = self._search_products(search_term)
                
                # Filter out duplicates
                new_products = 0
                for product in products:
                    product_key = f"{product['name']}_{product['price']}"
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        all_products.append(product)
                        new_products += 1
                
                self.logger.info(f"Found {new_products} new products for '{search_term}' (Total: {len(all_products)})")
                
                # Add human-like delay between searches
                time.sleep(random.uniform(3.0, 6.0))
                
            except Exception as e:
                self.logger.error(f"Error searching for '{search_term}': {e}")
                continue
        
        # Browse shop pages if we need more products
        if len(all_products) < 100:
            self.logger.info("Browsing shop pages for additional products...")
            shop_products = self._browse_shop_pages(max_pages=3)
            
            for product in shop_products:
                product_key = f"{product['name']}_{product['price']}"
                if product_key not in seen_products:
                    seen_products.add(product_key)
                    all_products.append(product)
        
        # Filter for relevant products
        relevant_products = self._filter_relevant_products(all_products)
        
        self.logger.info(f"Scraping complete: {len(relevant_products)} relevant products from {len(all_products)} total")
        return relevant_products
    
    def _search_products(self, search_term: str) -> List[Dict]:
        """Search for products using the site's search functionality"""
        products = []
        
        try:
            # Build search URL
            search_url = f"{self.search_url}?query={search_term.replace(' ', '%20')}"
            self.logger.debug(f"Searching: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(5)  # Wait for page load
            
            # Save page for debugging
            with open(f'debug_{search_term}.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            self.logger.info(f"Saved debug page for '{search_term}'")
            
            # Wait for products to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".card, [data-currency='CAD'], .search-result-card"))
                )
            except TimeoutException:
                # Try alternative selectors
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".product-item, .fill, .inner_class_mobile_responsive_grid"))
                    )
                except TimeoutException:
                    self.logger.warning(f"No products found for '{search_term}'")
                    # Check for "no results" messages
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    no_results_texts = ['no products found', 'no results', 'sorry', 'not found', '0 results']
                    page_text_lower = soup.get_text().lower()
                    for text in no_results_texts:
                        if text in page_text_lower:
                            self.logger.warning(f"Found '{text}' message on page")
                    return products
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Debug: Check what elements we can find
            debug_selectors = ['.card', '[data-currency="CAD"]', '.search-result-card', 
                            '.fill', '.inner_class_mobile_responsive_grid']
            for selector in debug_selectors:
                elements = soup.select(selector)
                self.logger.info(f"Found {len(elements)} elements with selector: {selector}")
                if elements and len(elements) > 0:
                    self.logger.debug(f"First element text: {elements[0].get_text(strip=True)[:100]}...")
            
            # Extract products from page
            page_products = self._extract_products_from_page(soup)
            products.extend(page_products)
            
            # Check for more pages
            self._handle_pagination(products, max_pages=2)
            
        except Exception as e:
            self.logger.error(f"Error in search: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        
        return products
    
    def _browse_shop_pages(self, max_pages: int = 3) -> List[Dict]:
        """Browse through shop pages directly"""
        products = []
        
        try:
            self.driver.get(self.shop_url)
            time.sleep(3)
            
            for page in range(1, max_pages + 1):
                self.logger.debug(f"Browsing shop page {page}")
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                page_products = self._extract_products_from_page(soup)
                products.extend(page_products)
                
                # Try to go to next page
                try:
                    next_button = self.driver.find_element(By.XPATH, "//a[contains(@class, 'next') or contains(text(), 'Next')]")
                    if next_button.is_enabled():
                        self.driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(3)
                    else:
                        break
                except:
                    break
                    
        except Exception as e:
            self.logger.error(f"Error browsing shop pages: {e}")
        
        return products
    
    def _extract_products_from_page(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract products from page content"""
        products = []
        
        # Try different selectors to find products
        product_selectors = [
            '.card.search-result-card',
            '.card',
            '.search-result-card',
            '.inner_class_mobile_responsive_grid',
            '.fill',
            '[class*="product"]'
        ]
        
        product_elements = []
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                product_elements = elements
                self.logger.info(f"Found {len(elements)} products using selector: {selector}")
                break
        
        if not product_elements:
            self.logger.warning("No product elements found with any selector")
            # Fallback: look for divs containing price info
            product_elements = soup.select('div')
            product_elements = [el for el in product_elements if 'cad' in el.get_text().lower()]
            self.logger.info(f"Found {len(product_elements)} potential product elements using generic approach")
        
        for element in product_elements:
            try:
                product = self._parse_product_element(element)
                if product:
                    products.append(product)
                    self.logger.debug(f"Found product: {product['name']} - ${product['price']}")
            except Exception as e:
                self.logger.debug(f"Error parsing product element: {e}")
                continue
        
        self.logger.info(f"Extracted {len(products)} products from page")
        return products
    
    def _parse_product_element(self, element: BeautifulSoup) -> Optional[Dict]:
        """Parse individual product element"""
        try:
            # Get product name
            name_selectors = [
                'h3.card-name', 'h3', '.card-name', '.card-title', 
                '[class*="name"]', 'h4', 'h5', 'h6'
            ]
            
            name_elem = None
            for selector in name_selectors:
                name_elem = element.select_one(selector)
                if name_elem:
                    break
                    
            if not name_elem:
                self.logger.debug("No name element found")
                return None
            
            full_text = name_elem.get_text(strip=True)
            
            # Extract size info from parentheses
            size_match = re.search(r'\(([^)]+)\)', full_text)
            size_text = None
            product_name = full_text
            
            if size_match:
                size_text = size_match.group(1)
                product_name = full_text[:size_match.start()].strip()
            
            # Try to extract size from name if not found
            if not size_text:
                size_pattern = r'(\d+(?:\.\d+)?\s*(?:ml|l|g|kg|lb|lbs|oz|pack|count|pc))'
                size_match = re.search(size_pattern, product_name, re.IGNORECASE)
                if size_match:
                    size_text = size_match.group(1)
            
            # Include size in product name
            if size_text:
                product_name = f"{product_name} {size_text}"
            
            # Get price
            price_selectors = [
                '[data-currency="CAD"]', '[data-price]', '.card-price', '.price',
                '.obw-primary-color', 'strong', 'b', '.text-price'
            ]
            
            price_elem = None
            for selector in price_selectors:
                price_elem = element.select_one(selector)
                if price_elem:
                    break
                    
            if not price_elem:
                self.logger.debug("No price element found")
                return None
            
            price_text = price_elem.get_text()
            
            # Check data-price attribute as fallback
            if not price_text and price_elem.get('data-price'):
                price_text = price_elem['data-price']
            
            price = self.extract_price_from_text(price_text)
            if not price:
                self.logger.debug(f"Could not extract price from: {price_text}")
                return None
            
            # Get product URL
            url_elem = element.select_one('a[href*="/product/"], a[href*="/menu/"]')
            product_url = url_elem['href'] if url_elem else None
            if product_url and not product_url.startswith('http'):
                product_url = self.base_url + product_url
            
            # Get image URL
            img_elem = element.select_one('img')
            image_url = img_elem.get('src') if img_elem else None
            
            # Get brand info
            brand_elem = element.select_one('a[href*="brand="]')
            if brand_elem:
                brand = brand_elem.get_text(strip=True)
            else:
                brand = self._extract_brand(product_name)
            
            # Determine category
            cat_elem = element.select_one('a[href*="/menu/"][href*="-"]')
            category = None
            if cat_elem and 'brand=' not in cat_elem['href']:
                category_text = cat_elem.get_text(strip=True)
                category = self._map_category(category_text)
            
            if not category:
                category = self._determine_category(product_name)
            
            # Check for sale tag
            on_sale = bool(element.select_one('.sale-label, .discount, [class*="offer"]'))
            
            return {
                'name': product_name,
                'price': price,
                'category': category,
                'brand': brand,
                'url': product_url,
                'image_url': image_url,
                'on_sale': on_sale,
                'source': 'Indian Frootland'
            }
            
        except Exception as e:
            self.logger.debug(f"Error parsing product element: {e}")
            return None
    
    def _map_category(self, category_text: str) -> str:
        """Map website categories to standard categories"""
        category_mapping = {
            'Edible Oil & Ghee': 'Edible Oil & Ghee',
            'Flour & Atta': 'Flour',
            'Rice & Rice Products': 'Rice',
            'Dal & Pulses': 'Dals and Grains',
            'Spices & Masala': 'Spices',
            'Snack': 'Snacks',
            'Sweets': 'Sweets',
            'Beverages': 'Beverages',
            'Tea Coffee': 'Tea, Coffee & Milk Products',
            'Noodles': 'Noodles and Pasta',
            'Frozen': 'Frozen Items',
            'Dairy': 'Dairy',
            'Pooja': 'Pooja Items'
        }
        
        for key, value in category_mapping.items():
            if key.lower() in category_text.lower():
                return value
        
        return category_text
    
    def _determine_category(self, product_name: str) -> str:
        """Guess category based on product name keywords"""
        product_lower = product_name.lower()
        
        for category, keywords in self.category_mapping.items():
            for keyword in keywords:
                if keyword in product_lower:
                    return category
        
        return "Other"
    
    def _extract_brand(self, product_name: str) -> Optional[str]:
        """Extract brand name from product name"""
        brands = [
            'Sher', 'Aashirvaad', 'Fortune', 'MDH', 'Everest', 'Shan', 'National',
            'Ashoka', 'Haldiram', 'Bikaji', 'Balaji', 'Priya', 'Mother\'s Recipe',
            'Patak', 'Deep', 'Swad', 'Laxmi', 'Badshah', 'Catch', 'Dabur', 'KTC',
            'Nirav', 'TRS', 'Heera', 'Natco', 'Patanjali', 'Tata', 'Amul',
            'Britannia', 'Parle', 'Nestle', 'Maggi', 'Kissan', 'Borges'
        ]
        
        product_upper = product_name.upper()
        for brand in brands:
            if brand.upper() in product_upper:
                return brand
        
        return None
    
    def _filter_relevant_products(self, products: List[Dict]) -> List[Dict]:
        """Filter out non-grocery items"""
        relevant_products = []
        irrelevant_keywords = [
            'lottery', 'ticket', 'gift card', 'phone card', 
            'calling card', 'recharge', 'top up', 'cigarette',
            'tobacco', 'vape'
        ]
        
        for product in products:
            # Skip non-grocery items
            product_lower = product['name'].lower()
            if any(keyword in product_lower for keyword in irrelevant_keywords):
                continue
            
            # Keep products with known categories
            if product.get('category') not in ['Other', None]:
                relevant_products.append(product)
            # Keep branded products
            elif product.get('brand'):
                relevant_products.append(product)
            # Keep products with Indian grocery keywords
            elif any(keyword in product_lower for keyword in ['dal', 'atta', 'rice', 'masala', 'chai', 'ghee', 'oil']):
                relevant_products.append(product)
        
        return relevant_products
    
    def _handle_pagination(self, products: List[Dict], max_pages: int = 2):
        """Handle pagination if available"""
        for page in range(2, max_pages + 1):
            try:
                # Look for page links
                pagination_link = self.driver.find_element(
                    By.XPATH, 
                    f"//a[contains(@href, 'page={page}') or contains(text(), '{page}')]"
                )
                
                if pagination_link:
                    self.driver.execute_script("arguments[0].click();", pagination_link)
                    time.sleep(3)
                    
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    page_products = self._extract_products_from_page(soup)
                    products.extend(page_products)
                    
                    self.logger.debug(f"Found {len(page_products)} products on page {page}")
            except:
                # Stop if no more pages
                break