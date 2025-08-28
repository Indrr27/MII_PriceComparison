# scrapers/made_in_india_scraper.py 

from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from typing import List, Dict
import re
import time
import random

class MadeInIndiaGroceryScraper(BaseScraper):
    """Scraper for Made in India Grocery with improved category detection"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless=headless, delay=3.0)
        self.base_url = "https://madeinindiagrocery.com"
        self.shop_url = "https://madeinindiagrocery.com/shop/"
        
        # Known categories from the website
        self.official_categories = {
            'Bathroom Essentials', 'Beverages', 'Biscuits and Cookies', 'Breads',
            'Candies and Mukhwas', 'Cosmetics and Oils', 'Dairy', 'Dals and Grains',
            'Flour', 'Frozen Items', 'Herbal Products and Medicines', 'Ice Creams',
            'Pickles', 'Pooja and Festive Items', 'Produce', 'Quick Cook', 'Rice',
            'Sauces and Pastes', 'Snacks', 'Spices', 'Sports Items', 'Sweets',
            'Tea, Coffee & Milk Products', 'Utensils and Kitchen Essentials'
        }
        
    def get_store_info(self) -> Dict:
        return {
            "name": "Made in India Grocery",
            "location": "Georgetown, Ontario", 
            "website": self.base_url,
            "store_type": "Indian Grocery"
        }
    
    def wait_and_get_page_source(self, url: str, wait_element: str = None) -> str:
        """Load page with retry for failed attempts"""
        for attempt in range(3):  # Max 3 retries
            try:
                if attempt > 0:
                    self.logger.info(f"Retry {attempt} for page")
                    time.sleep(5)
                
                self.driver.set_page_load_timeout(15)
                self.driver.get(url)
                time.sleep(random.uniform(2.0, 4.0))
                
                page_source = self.driver.page_source
                
                # Check if page loaded properly
                if len(page_source) > 5000 and ('/product/' in page_source or 'shop' in page_source.lower()):
                    return page_source
                elif attempt < 2:
                    self.logger.warning("Page didn't load properly, retrying...")
                    continue
                else:
                    return page_source  # Return whatever we got
                    
            except Exception as e:
                if attempt < 2:
                    self.logger.warning(f"Load error, retrying: {e}")
                    continue
                else:
                    self.logger.error(f"Failed to load after retries: {e}")
                    return ""
        
        return ""
    
    def scrape_products(self) -> List[Dict]:
        """Main scraping method with better category detection"""
        products = []
        page = 1
        max_pages = 70
        consecutive_failures = 0
        
        while page <= max_pages and consecutive_failures < 5:
            # Build page URL
            if page == 1:
                url = self.shop_url
            else:
                url = f"{self.shop_url}page/{page}/"
            
            self.logger.info(f"Scraping page {page}: {url}")
            
            try:
                page_source = self.wait_and_get_page_source(url)
                
                if not page_source:
                    self.logger.error(f"Failed to load page {page}")
                    consecutive_failures += 1
                    page += 1
                    continue
                
                soup = BeautifulSoup(page_source, 'html.parser')
                page_products = self._extract_products_from_page(soup)
                
                if not page_products:
                    # Check if products exist but weren't extracted
                    product_links = len(soup.find_all('a', href=lambda x: x and '/product/' in x))
                    
                    if product_links > 0:
                        self.logger.warning(f"Page {page} has {product_links} product links but extraction failed")
                        # Try backup extraction method
                        page_products = self._extract_products_alternative(soup)
                    
                    if not page_products:
                        consecutive_failures += 1
                        self.logger.info(f"No products on page {page}")
                        if consecutive_failures >= 5:
                            break
                else:
                    consecutive_failures = 0
                    
                    # Add accurate categories to products
                    self.logger.info(f"Adding categories to {len(page_products)} products...")
                    enhanced_products = self._enhance_with_accurate_categories(page_products)
                    products.extend(enhanced_products)
                    
                    self.logger.info(f"Page {page} complete: {len(enhanced_products)} products (Total: {len(products)})")
                
                page += 1
                time.sleep(random.uniform(3.0, 7.0))
                
            except Exception as e:
                self.logger.error(f"Error on page {page}: {e}")
                consecutive_failures += 1
                page += 1
                time.sleep(15)
        
        self.logger.info(f"Done scraping. Total products: {len(products)}")
        return products
    
    def _extract_category_from_product_page(self, product_url: str) -> str:
        """Get category from product page with multiple fallback strategies"""
        if not product_url:
            return None
        
        try:
            # Quick timeout for product pages
            self.driver.set_page_load_timeout(8)
            self.driver.get(product_url)
            time.sleep(1)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 1. Check breadcrumbs first
            breadcrumb_selectors = [
                '.breadcrumb', '.breadcrumbs', '.woocommerce-breadcrumb', 
                '[class*="breadcrumb"]', 'nav[class*="breadcrumb"]'
            ]
            
            for selector in breadcrumb_selectors:
                breadcrumb = soup.select_one(selector)
                if breadcrumb:
                    breadcrumb_text = breadcrumb.get_text()
                    self.logger.debug(f"Found breadcrumb: {breadcrumb_text}")
                    
                    # Match against known categories
                    for category in self.official_categories:
                        if category != "All Products" and category in breadcrumb_text:
                            # Ensure it's a proper match
                            if f"/{category}/" in breadcrumb_text or breadcrumb_text.strip().endswith(category):
                                self.logger.debug(f"Found category in breadcrumb: {category}")
                                return category
            
            # 2. Check meta tags
            meta_selectors = [
                'meta[property="product:category"]',
                'meta[name="product_category"]',
                '[itemtype*="Product"] [itemprop="category"]',
                '.product-category', '.product_cat'
            ]
            
            for selector in meta_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    content = elem.get('content') or elem.get_text()
                    if content:
                        for category in self.official_categories:
                            if category != "All Products" and category.lower() in content.lower():
                                self.logger.debug(f"Found category in meta: {category}")
                                return category
            
            # 3. Look for category links
            category_link_selectors = [
                '.product-meta a', '.entry-meta a', '.product-categories a',
                '.product_meta a', '.single-product-summary a'
            ]
            
            for selector in category_link_selectors:
                links = soup.select(selector)
                for link in links:
                    link_text = link.get_text(strip=True)
                    link_href = link.get('href', '')
                    
                    # Check if link points to a category
                    if 'category' in link_href.lower():
                        for category in self.official_categories:
                            if category != "All Products" and category == link_text:
                                self.logger.debug(f"Found category link: {category}")
                                return category
            
            # 4. Look for "Categories:" text
            page_text = soup.get_text()
            if "Categories:" in page_text or "Category:" in page_text:
                categories_section = soup.find(string=re.compile(r'Categor(?:y|ies):?', re.IGNORECASE))
                if categories_section:
                    parent = categories_section.parent
                    if parent:
                        # Check nearby elements
                        for sibling in parent.parent.find_all(['a', 'span', 'div'], limit=10):
                            sibling_text = sibling.get_text(strip=True)
                            sibling_href = sibling.get('href', '')
                            
                            if ('category' in sibling_href.lower() or 
                                any(cat_word in sibling.get('class', []) for cat_word in ['category', 'cat', 'tag'])):
                                
                                for category in self.official_categories:
                                    if category != "All Products" and category == sibling_text:
                                        self.logger.debug(f"Found category in categories section: {category}")
                                        return category
            
            # 5. WooCommerce-specific elements
            woo_selectors = [
                '.posted_in a', '.product_meta .posted_in a', 
                'span.posted_in a', '.product-categories a'
            ]
            
            for selector in woo_selectors:
                category_links = soup.select(selector)
                for link in category_links:
                    link_text = link.get_text(strip=True)
                    if link_text in self.official_categories and link_text != "All Products":
                        self.logger.debug(f"Found WooCommerce category: {link_text}")
                        return link_text
            
            # 6. Check URL structure
            if '/product-category/' in product_url:
                url_parts = product_url.split('/product-category/')
                if len(url_parts) > 1:
                    category_slug = url_parts[1].split('/')[0]
                    # Match slug to category names
                    for category in self.official_categories:
                        category_slug_candidate = category.lower().replace(' ', '-').replace('&', 'and')
                        if category_slug_candidate in category_slug and category != "All Products":
                            self.logger.debug(f"Found category in URL: {category}")
                            return category
            
            self.logger.debug(f"No category found for {product_url}")
            return None
            
        except Exception as e:
            self.logger.debug(f"Category extraction failed for {product_url}: {e}")
            return None
        finally:
            try:
                self.driver.set_page_load_timeout(30)
            except:
                pass
    
    def _enhance_with_accurate_categories(self, products: List[Dict]) -> List[Dict]:
        """Add accurate categories to products"""
        enhanced_products = []
        category_stats = {"found": 0, "fallback": 0, "failed": 0}
        
        for i, product in enumerate(products):
            try:
                product_name = product.get('name', 'Unknown')
                product_url = product.get('url', '')
                
                self.logger.debug(f"Processing {i+1}/{len(products)}: {product_name}")
                
                # Get category from product page
                accurate_category = self._extract_category_from_product_page(product_url)
                
                if accurate_category:
                    product['category'] = accurate_category
                    category_stats["found"] += 1
                    self.logger.debug(f"SUCCESS: {product_name} -> {accurate_category}")
                else:
                    product['category'] = self._guess_category_fallback(product_name)
                    category_stats["fallback"] += 1
                    self.logger.debug(f"FALLBACK: {product_name} -> {product['category']}")
                
                enhanced_products.append(product)
                
                # Progress update
                if (i + 1) % 50 == 0:
                    self.logger.info(f"Progress: {i+1}/{len(products)} processed. "
                                f"Found: {category_stats['found']}, "
                                f"Fallback: {category_stats['fallback']}")
                
                # Small delay between requests
                if i < len(products) - 1:
                    time.sleep(random.uniform(1.0, 2.5))
                
            except Exception as e:
                self.logger.warning(f"Error enhancing {product.get('name', 'Unknown')}: {e}")
                product['category'] = self._guess_category_fallback(product.get('name', ''))
                category_stats["failed"] += 1
                enhanced_products.append(product)
        
        # Final stats
        self.logger.info(f"Category extraction results:")
        self.logger.info(f"  Found from page: {category_stats['found']}")
        self.logger.info(f"  Used fallback: {category_stats['fallback']}")
        self.logger.info(f"  Failed: {category_stats['failed']}")
        
        return enhanced_products
    
    def _extract_products_from_page(self, soup: BeautifulSoup) -> List[Dict]:
        """Get products from page"""
        products = []
        seen_products = set()
        
        # Find product links
        product_links = soup.find_all('a', href=lambda x: x and '/product/' in x)
        
        for link in product_links:
            try:
                product_data = self._extract_product_from_link(link, soup)
                if product_data and product_data['name'] not in seen_products:
                    products.append(product_data)
                    seen_products.add(product_data['name'])
            except Exception as e:
                continue
        
        # Also try WooCommerce selectors
        woo_products = soup.select('li.product, .type-product, .woocommerce-loop-product__link')
        for product_elem in woo_products:
            try:
                product_data = self._extract_woocommerce_product(product_elem)
                if product_data and product_data['name'] not in seen_products:
                    products.append(product_data)
                    seen_products.add(product_data['name'])
            except Exception as e:
                continue
        
        # Remove duplicates
        unique_products = []
        for product in products:
            if (product['name'] and product['price'] and 
                product['name'] not in [p['name'] for p in unique_products]):
                unique_products.append(product)
        
        return unique_products
    
    def _extract_products_alternative(self, soup: BeautifulSoup) -> List[Dict]:
        """Backup extraction method"""
        products = []
        seen_products = set()
        
        # Find all product links
        all_links = soup.find_all('a', href=lambda x: x and '/product/' in x)
        
        for link in all_links:
            try:
                product_url = link.get('href')
                if not product_url.startswith('http'):
                    product_url = self.base_url + product_url
                
                product_name = link.get_text(strip=True)
                
                # Look for price near the link
                price = None
                current = link
                for _ in range(5):
                    if current:
                        price = self.extract_price_from_text(current.get_text())
                        if price:
                            break
                        current = current.parent
                
                if product_name and price and len(product_name) > 3 and product_name not in seen_products:
                    products.append({
                        'name': self._clean_product_name(product_name),
                        'price': price,
                        'url': product_url,
                        'brand': self._extract_brand(product_name),
                        'size': self._extract_size(product_name),
                        'category': None
                    })
                    seen_products.add(product_name)
                    
            except Exception as e:
                continue
        
        return products
    
    def _extract_product_from_link(self, link, soup: BeautifulSoup) -> Dict:
        """Extract product data from link element"""
        try:
            product_url = link.get('href')
            if not product_url.startswith('http'):
                product_url = self.base_url + product_url
                
            product_name = link.get_text(strip=True)
            
            # Find price in nearby elements
            price = None
            parent = link.parent
            for _ in range(3):
                if parent:
                    price = self.extract_price_from_text(parent.get_text())
                    if price:
                        break
                    parent = parent.parent
            
            # Check siblings if still no price
            if not price:
                for sibling in link.parent.find_all():
                    price = self.extract_price_from_text(sibling.get_text())
                    if price:
                        break
            
            if product_name and price and len(product_name) > 3:
                return {
                    'name': self._clean_product_name(product_name),
                    'price': price,
                    'url': product_url,
                    'brand': self._extract_brand(product_name),
                    'size': self._extract_size(product_name),
                    'category': None
                }
        except Exception as e:
            pass
            
        return None
    
    def _extract_woocommerce_product(self, product_elem) -> Dict:
        """Extract from WooCommerce product elements"""
        try:
            # Find title and URL
            title_elem = product_elem.find('a', href=lambda x: x and '/product/' in x)
            if not title_elem:
                return None
                
            product_name = title_elem.get_text(strip=True)
            product_url = title_elem.get('href')
            
            if not product_url.startswith('http'):
                product_url = self.base_url + product_url
            
            # Find price
            price = self.extract_price_from_text(product_elem.get_text())
            
            if product_name and price and len(product_name) > 3:
                return {
                    'name': self._clean_product_name(product_name),
                    'price': price,
                    'url': product_url,
                    'brand': self._extract_brand(product_name),
                    'size': self._extract_size(product_name),
                    'category': None
                }
        except Exception as e:
            pass
            
        return None
    
    def _clean_product_name(self, name: str) -> str:
        """Clean up product name"""
        if not name:
            return ""
        
        name = ' '.join(name.split())
        unwanted_phrases = ['Add to cart', 'Quick view', 'Select options', 'Read more']
        for phrase in unwanted_phrases:
            name = name.replace(phrase, '')
        
        return name.strip()
    
    def _extract_brand(self, product_name: str) -> str:
        """Extract brand from product name"""
        known_brands = [
            'Everest', 'MDH', 'Shan', 'Tata', 'Amul', 'Britannia', 'Parle', 
            'Haldiram', 'Deep', 'Swad', 'Heera', 'TRS', 'Natco', 'Dabur'
        ]
        
        name_upper = product_name.upper()
        for brand in known_brands:
            if brand.upper() in name_upper:
                return brand
        
        words = product_name.split()
        if words and words[0].istitle() and len(words[0]) > 2:
            return words[0]
        
        return "Unknown"
    
    def _extract_size(self, product_name: str) -> str:
        """Extract size from product name"""
        size_patterns = [
            r'(\d+(?:\.\d+)?\s*(?:kg|g|gm|lb|lbs|oz|ml|l))',
            r'(\d+(?:\.\d+)?\s*(?:pack|pcs|pieces))'
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, product_name, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return "Unknown"
    
    def _guess_category_fallback(self, product_name: str) -> str:
        """Fallback category guessing based on product name"""
        if not product_name:
            return "Unknown"
        
        import re
        name_lower = product_name.lower()
        
        # Brand-based categorization
        brand_categories = {
            'Spices': [
                'everest', 'mdh', 'shan', 'catch', 'trs spices',
                'natco', 'heera spices', 'rajah', 'east end', 'laziza',
                'badshah', 'suhana', 'mangal', 'priya'
            ],
            'Tea, Coffee & Milk Products': [
                'red label tea', 'red label', 'tata tea', 'brooke bond', 'lipton', 'taj mahal tea',
                'society tea', 'wagh bakri', 'nescafe', 'bru coffee', 'bru instant',
                'tetley', 'organic india'
            ],
            'Snacks': [
                'haldiram', 'bikano', 'balaji', 'britannia snacks',
                'kurkure', 'lays indian', 'uncle chipps'
            ],
            'Sweets': [
                'haldiram sweets', 'bikano sweets', 'gits sweets',
                'mithai', 'bikanervala'
            ],
            'Cosmetics and Oils': [
                'dabur', 'himalaya', 'patanjali', 'vlcc', 'khadi', 'bajaj',
                'parachute', 'head and shoulders', 'pantene', 'loreal',
                'vicco', 'boroplus'
            ],
            'Herbal Products and Medicines': [
                'patanjali medicine', 'dabur health', 'himalaya wellness',
                'baidyanath', 'zandu', 'hamdard',
                'ayush', 'sri sri tattva'
            ],
            'Dairy': [
                'amul', 'britannia dairy', 'nestle dairy', 'mother dairy',
                'nandini', 'aavin'
            ],
            'Biscuits and Cookies': [
                'parle', 'britannia biscuits', 'sunfeast', 'priyagold',
                'mcdowells', 'unibic'
            ],
            'Quick Cook': [
                'gits', 'mtr', 'maiys', 'ashoka'
            ],
            'Frozen Items': [
                'deep frozen', 'swad frozen', 'vadilal'
            ],
            'Ice Creams': [
                'kwality walls', 'amul ice cream', 'havmor', 'vadilal ice cream',
                'baskin robbins indian'
            ]
        }
        
        # Check brand matches first
        for category, brands in brand_categories.items():
            for brand in brands:
                if brand in name_lower:
                    # For multi-word brands, require exact match
                    if len(brand.split()) > 1:
                        if brand in name_lower:
                            return category
                    else:
                        if re.search(rf'\b{re.escape(brand)}\b', name_lower):
                            return category
        
        # Keyword-based categorization
        category_mappings = {
            'Biscuits and Cookies': [
                'biscuit', 'cookie', 'rusk', 'toast', 'marie gold', 'glucose biscuit',
                'cream biscuit', 'digestive biscuit', 'bourbon', 'nice time', 'milk bikis',
                'oreo indian', 'hide and seek', 'monaco', 'krackjack'
            ],
            'Ice Creams': [
                'ice cream', 'kulfi', 'falooda', 'cassata', 'matka kulfi', 'ice candy',
                'sundae', 'cone ice cream', 'family pack ice cream'
            ],
            'Pooja and Festive Items': [
                'incense', 'agarbatti', 'dhoop', 'camphor', 'kapoor', 'diya', 'lamp',
                'pooja oil', 'kumkum', 'turmeric pooja', 'sindoor', 'vibhuti', 'puja kit',
                'rangoli', 'toran', 'garland', 'festive decoration', 'haldi kumkum', 'betel nut'
            ],
            'Sports Items': [
                'cricket bat', 'cricket ball', 'carrom board', 'carrom striker', 'chess set',
                'badminton racket', 'shuttlecock', 'kabaddi mat', 'yoga mat', 'dumbbell indian'
            ],
            'Spices': [
                'spice', 'masala', 'powder', 'turmeric', 'haldi', 'cumin', 'coriander', 'chili',
                'kashmiri lal', 'kashmiri red', 'garam', 'tandoori', 'biryani', 'curry', 'chat', 'chaat',
                'jeera', 'dhania', 'methi', 'ajwain', 'kala namak', 'amchur', 'hing',
                'cardamom', 'elaichi', 'cinnamon', 'dalchini', 'cloves', 'laung',
                'bay leaves', 'tej patta', 'mustard seeds', 'rai', 'fennel', 'saunf',
                'fenugreek', 'nutmeg', 'mace', 'javitri', 'star anise', 'black pepper',
                'white pepper', 'long pepper', 'pipli', 'asafoetida',
                'sambhar', 'sambar', 'rasam', 'pav bhaji', 'chole', 'rajma masala',
                'dal tadka', 'pickle masala', 'meat masala', 'fish masala',
                'saffron', 'kesar', 'paprika', 'kokum', 'dagad phool', 'stone flower', 'kalpasi'
            ],
            'Flour': [
                'flour', 'atta', 'maida', 'besan', 'gram flour', 'chickpea flour',
                'rice flour', 'wheat flour', 'corn flour', 'bajra flour', 'jowar flour',
                'ragi flour', 'sattu', 'kuttu flour', 'singhara flour',
                'multigrain atta', 'sooji', 'rava', 'semolina'
            ],
            'Rice': [
                'rice', 'basmati', 'jasmine', 'sona masoori', 'ponni', 'kolam',
                'ambemohar', 'indrayani', 'brown rice', 'red rice', 'black rice',
                'idli rice', 'matta rice', 'jeera rice'
            ],
            'Dals and Grains': [
                'dal', 'daal', 'lentil', 'lentils', 'chickpea', 'chickpeas', 'rajma',
                'beans', 'quinoa', 'oats', 'barley', 'jau',
                'toor', 'tuar', 'arhar', 'chana', 'moong', 'mung', 'urad', 'masoor',
                'kulthi', 'horse gram', 'black gram', 'green gram', 'split pea',
                'kidney beans', 'black beans', 'pinto beans', 'lima beans',
                'kabuli chana', 'moth beans', 'matki', 'whole moong'
            ],
            'Tea, Coffee & Milk Products': [
                'tea', 'chai', 'coffee', 'milk tea', 'green tea', 'black tea',
                'herbal tea', 'masala chai', 'cardamom tea', 'ginger tea',
                'instant coffee', 'filter coffee', 'chicory',
                'milk powder', 'condensed milk', 'evaporated milk'
            ],
            'Sauces and Pastes': [
                'sauce', 'paste', 'chutney', 'pickle', 'achaar', 'achar',
                'tomato sauce', 'soy sauce', 'vinegar', 'ketchup',
                'ginger garlic paste', 'tamarind paste', 'curry paste',
                'mint chutney', 'coconut chutney', 'schezwan sauce'
            ],
            'Snacks': [
                'chips', 'namkeen', 'mixture', 'bhujia', 'wafers', 'sev', 'papdi', 'khakhra', 'thepla',
                'mathri', 'shakkar pare', 'nuts', 'almonds', 'cashews', 'peanuts',
                'banana chips', 'jackfruit chips', 'farsan', 'chekkalu'
            ],
            'Sweets': [
                'sweet', 'mithai', 'laddu', 'ladoo', 'barfi', 'burfi', 'jaggery', 'gur',
                'rasgulla', 'gulab jamun', 'kaju katli', 'motichoor', 'besan laddu',
                'coconut laddu', 'til laddu', 'halwa', 'kheer', 'payasam',
                'peda', 'sandesh', 'rasmalai', 'cham cham',
                'mysore pak', 'soan papdi', 'malpua'
            ],
            'Beverages': [
                'juice', 'drink', 'beverage', 'lassi', 'buttermilk', 'chaas',
                'sherbet', 'squash', 'concentrate', 'syrup',
                'mango drink', 'coconut water', 'energy drink',
                'rose syrup', 'thandai', 'jaljeera'
            ],
            'Dairy': [
                'milk', 'paneer', 'cottage cheese', 'butter', 'cheese', 'cream',
                'yogurt', 'curd', 'dahi', 'ghee', 'clarified butter',
                'khoya', 'mawa', 'rabri'
            ],
            'Cosmetics and Oils': [
                'oil', 'hair oil', 'coconut oil hair', 'almond oil cosmetic',
                'sesame oil hair', 'mustard oil hair', 'castor oil',
                'shampoo', 'conditioner', 'hair mask', 'hair cream',
                'face cream', 'body lotion', 'soap', 'face wash',
                'toothpaste', 'talcum powder', 'kajal', 'mehendi', 'henna',
                'sunscreen', 'moisturizer', 'lip balm'
            ],
            'Candies and Mukhwas': [
                'candy', 'candies', 'toffee', 'chocolate', 'lollipop',
                'mukhwas', 'mouth freshener', 'saunf', 'sugar coated',
                'digestive', 'after meal', 'fennel candy', 'mint',
                'pan masala', 'elaichi candy', 'imli candy'
            ],
            'Bathroom Essentials': [
                'soap', 'hand wash', 'body wash', 'face wash', 'scrub',
                'loofah', 'sponge', 'towel', 'toilet paper',
                'detergent', 'sanitizer', 'disinfectant'
            ],
            'Herbal Products and Medicines': [
                'herbal', 'ayurvedic', 'medicine', 'tablet', 'capsule', 'syrup',
                'churna', 'powder medicine', 'oil medicine', 'balm',
                'pain relief', 'digestive', 'immunity', 'wellness',
                'triphala', 'ashwagandha', 'tulsi drops'
            ],
            'Utensils and Kitchen Essentials': [
                'utensil', 'pot', 'pan', 'plate', 'bowl', 'spoon', 'fork',
                'knife', 'cutting board', 'container', 'storage',
                'pressure cooker', 'tawa', 'kadhai', 'grinder',
                'idli maker', 'dosa tawa', 'masala box'
            ],
            'Frozen Items': [
                'frozen', 'popsicle', 'frozen vegetables',
                'frozen fruits', 'frozen snacks', 'frozen paratha', 'frozen samosa',
                'frozen kebab', 'frozen paneer', 'frozen dosa batter'
            ],
            'Pickles': [
                'pickle', 'achar', 'achaar', 'mango pickle', 'lime pickle',
                'mixed pickle', 'garlic pickle', 'ginger pickle',
                'green chili pickle', 'gongura pickle', 'avakaya'
            ],
            'Quick Cook': [
                'instant', 'ready to eat', 'ready to cook', 'mix', 'batter',
                'noodles', 'pasta', 'maggi', 'ramen', 'upma mix',
                'poha mix', 'idli mix', 'dosa mix', 'rava dosa',
                'biryani mix', 'pulao mix', 'khichdi mix'
            ],
            'Breads': [
                'bread', 'naan', 'roti', 'chapati', 'paratha', 'kulcha',
                'pita', 'tortilla', 'pav', 'bun', 'burger bun',
                'poori', 'bhatura', 'appam'
            ],
            'Produce': [
                'fresh', 'vegetable', 'fruit', 'onion', 'potato', 'tomato',
                'ginger', 'garlic', 'green chili', 'lemon', 'lime',
                'bhindi', 'okra', 'brinjal', 'eggplant', 'drumstick', 'moringa',
                'curry leaves', 'coriander leaves', 'mint leaves', 'mango', 'banana', 'papaya'
            ]
        }
        
        # Check keyword matches
        for category, keywords in category_mappings.items():
            if any(keyword in name_lower for keyword in keywords):
                return category
        
        # Special handling for products with sizes
        if re.search(r'\b(100g|200g|500g|1kg|250ml|500ml|1l)\b', name_lower):
            # Try partial matching for sized products
            for category, keywords in category_mappings.items():
                for keyword in keywords[:3]:  # Check first few keywords
                    if keyword in name_lower:
                        return category
        
        return "Unknown"


if __name__ == "__main__":
    scraper = MadeInIndiaGroceryScraper(headless=False)
    products = scraper.scrape_with_error_handling()
    print(f"Scraped {len(products)} products with enhanced categories")