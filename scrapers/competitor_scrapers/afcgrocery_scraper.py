# scrapers/competitor_scrapers/afcgrocery_scraper.py

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

class AFCGroceryScraper(BaseScraper):
    """Scraper for AFC Grocery (Asian Food Centre)"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless=headless, delay=3.0)
        self.base_url = "https://afcgrocery.com"
        self.search_url = "https://afcgrocery.com/categorysearch"
        self.shop_url = "https://afcgrocery.com/shop"
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Map products to categories using keywords
        self.category_mapping = {
            'Flour': ['flour', 'atta', 'besan', 'maida', 'rice flour', 'gram flour'],
            'Rice': ['rice', 'basmati', 'jasmine', 'sona masoori', 'ponni'],
            'Dals and Grains': ['dal', 'lentil', 'toor', 'urad', 'moong', 'chana', 'rajma', 'kidney beans'],
            'Spices': ['spice', 'masala', 'powder', 'turmeric', 'cumin', 'coriander', 'chili', 'garam'],
            'Oils': ['oil', 'mustard oil', 'sesame oil', 'coconut oil', 'sunflower oil', 'ghee'],
            'Sauces and Pastes': ['sauce', 'paste', 'chutney', 'pickle', 'achaar', 'ketchup'],
            'Snacks': ['namkeen', 'chips', 'bhujia', 'sev', 'mixture', 'papad', 'cookies', 'biscuit'],
            'Sweets': ['mithai', 'laddu', 'barfi', 'halwa', 'gulab jamun', 'rasgulla', 'sweet'],
            'Tea and Coffee': ['tea', 'chai', 'coffee', 'green tea', 'black tea'],
            'Noodles and Pasta': ['noodles', 'maggi', 'pasta', 'vermicelli', 'sevai'],
            'Beverages': ['juice', 'drink', 'lassi', 'sherbet', 'soda'],
            'Frozen Items': ['frozen', 'paratha', 'samosa', 'naan', 'roti'],
            'Dairy': ['paneer', 'milk', 'yogurt', 'cheese', 'butter', 'cream'],
            'Pooja Items': ['pooja', 'agarbatti', 'camphor', 'diya', 'kumkum', 'incense']
        }
        
        # Search terms we'll use to find products
        self.target_searches = [
            # Oils
            "mustard oil", "coconut oil", "sesame oil", "sunflower oil",
            
            # Flours
            "atta", "flour", "besan", "maida", "rice flour",
            
            # Rice varieties
            "basmati rice", "rice", "sona masoori", "jasmine rice",
            
            # Dals and lentils
            "dal", "lentils", "toor dal", "moong dal", "chana dal", "urad dal",
            
            # Common spices
            "turmeric", "cumin", "coriander", "garam masala", "chili powder",
            "masala", "spice mix", "curry powder",
            
            # Ready-to-cook mixes
            "dosa mix", "idli mix", "gulab jamun", "halwa mix",
            
            # Snacks
            "namkeen", "bhujia", "chips", "mixture", "papad",
            
            # Condiments
            "pickle", "chutney", "sauce", "paste",
            
            # Drinks
            "tea", "chai", "coffee", "juice",
            
            # Instant foods
            "maggi", "noodles", "pasta",
            
            # Sweets
            "mithai", "laddu", "barfi", "sweet",
            
            # Frozen foods
            "frozen", "paratha", "samosa",
            
            # Popular brands
            "tez", "fortune", "patanjali", "kissan", "sardarjee", "sher"
        ]
    
    def get_store_info(self) -> Dict:
        """Returns basic store information"""
        return {
            "name": "AFC Grocery",
            "location": "Toronto, ON",
            "website": self.base_url,
            "store_type": "Asian/Indian Grocery"
        }
    
    def scrape_products(self) -> List[Dict]:
        """Main method to scrape products using search terms"""
        all_products = []
        seen_products = set()
        
        self.logger.info("Starting AFC Grocery scraping...")
        
        # Search for each term in our list
        for i, search_term in enumerate(self.target_searches):
            self.logger.info(f"Searching for '{search_term}' ({i+1}/{len(self.target_searches)})")
            
            try:
                products = self._search_products(search_term)
                
                # Skip duplicates
                new_products = 0
                for product in products:
                    product_key = f"{product['name']}_{product['price']}"
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        all_products.append(product)
                        new_products += 1
                
                self.logger.info(f"Found {new_products} new products for '{search_term}' (Total: {len(all_products)})")
                
                # Wait between searches
                time.sleep(random.uniform(3.0, 6.0))
                
            except Exception as e:
                self.logger.error(f"Error searching for '{search_term}': {e}")
                continue
        
        # If we didn't find enough products, browse the shop pages
        if len(all_products) < 100:
            self.logger.info("Browsing shop pages for more products...")
            shop_products = self._browse_shop_pages(max_pages=5)
            
            for product in shop_products:
                product_key = f"{product['name']}_{product['price']}"
                if product_key not in seen_products:
                    seen_products.add(product_key)
                    all_products.append(product)
        
        # Filter out non-relevant products
        relevant_products = self._filter_relevant_products(all_products)
        
        self.logger.info(f"Scraping complete: {len(relevant_products)} relevant products from {len(all_products)} total")
        return relevant_products
    
    def _search_products(self, search_term: str) -> List[Dict]:
        """Search for products using the website's search function"""
        products = []
        
        try:
            # Format search URL
            search_url = f"{self.search_url}?term={search_term.replace(' ', '+')}"
            self.logger.debug(f"Searching: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(3)
            
            # Wait for products to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "product_box"))
                )
            except TimeoutException:
                self.logger.warning(f"No products found for '{search_term}'")
                return products
            
            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            page_products = self._extract_products_from_page(soup)
            products.extend(page_products)
            
            # Check for more pages
            self._handle_pagination(products, max_pages=3)
            
        except Exception as e:
            self.logger.error(f"Error in search: {e}")
        
        return products
    
    def _browse_shop_pages(self, max_pages: int = 5) -> List[Dict]:
        """Browse through the shop pages directly"""
        products = []
        
        try:
            self.driver.get(self.shop_url)
            time.sleep(3)
            
            # Go through each page
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
        """Extract products from a page using AFC's HTML structure"""
        products = []
        
        # Find all product elements
        product_elements = soup.select('.item .product_box')
        
        for element in product_elements:
            try:
                product = self._parse_product_element(element)
                if product:
                    products.append(product)
            except Exception as e:
                self.logger.debug(f"Error parsing product element: {e}")
                continue
        
        return products
    
    def _parse_product_element(self, element: BeautifulSoup) -> Optional[Dict]:
        """Parse individual product elements"""
        try:
            # Get product name
            name_elem = element.select_one('.caption h4 a')
            if not name_elem:
                return None
            
            product_name = name_elem.get_text(strip=True)
            
            # Check for size information
            size_elem = element.select_one('.unit_type')
            if size_elem:
                size_text = size_elem.get_text(strip=True)
                product_name = f"{product_name} {size_text}"
                self.logger.debug(f"Found product with size: {product_name}")
            
            # Get price
            price_elem = element.select_one('.price')
            if not price_elem:
                return None
            
            price = self.extract_price_from_text(price_elem.get_text())
            if not price:
                return None
            
            # Get product URL
            url_elem = element.select_one('a[href]')
            product_url = url_elem['href'] if url_elem else None
            if product_url and not product_url.startswith('http'):
                product_url = self.base_url + product_url
            
            # Get image URL
            img_elem = element.select_one('img')
            image_url = img_elem.get('src') if img_elem else None
            if image_url and not image_url.startswith('http'):
                image_url = self.base_url + "/" + image_url.lstrip('/')
            
            # Determine category and brand
            category = self._determine_category(product_name)
            brand = self._extract_brand(product_name)
            
            # Check for sale tag
            on_sale = bool(element.select_one('.sale-label, .discount'))
            
            return {
                'name': product_name,
                'price': price,
                'category': category,
                'brand': brand,
                'url': product_url,
                'image_url': image_url,
                'on_sale': on_sale,
                'source': 'AFC Grocery'
            }
            
        except Exception as e:
            self.logger.debug(f"Error parsing product: {e}")
            return None
    
    def _determine_category(self, product_name: str) -> str:
        """Categorize products based on keywords in their names"""
        product_lower = product_name.lower()
        
        for category, keywords in self.category_mapping.items():
            for keyword in keywords:
                if keyword in product_lower:
                    return category
        
        return "Other"
    
    def _extract_brand(self, product_name: str) -> Optional[str]:
        """Try to identify brand from product name"""
        brands = [
            'Tez', 'Fortune', 'Patanjali', 'Kissan', 'Sardarjee', 'Sher',
            'MDH', 'Everest', 'Shan', 'National', 'Ashoka', 'Haldiram',
            'Bikaji', 'Balaji', 'Priya', 'Mother\'s Recipe', 'Patak',
            'Deep', 'Swad', 'Laxmi', 'Badshah', 'Catch', 'Aashirvaad'
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
            'calling card', 'recharge', 'top up'
        ]
        
        for product in products:
            # Skip non-grocery items
            product_lower = product['name'].lower()
            if any(keyword in product_lower for keyword in irrelevant_keywords):
                continue
            
            # Keep products with clear categories or brands
            if product.get('category') != 'Other':
                relevant_products.append(product)
            elif product.get('brand'):
                relevant_products.append(product)
            # Keep products that look like Indian groceries
            elif any(keyword in product_lower for keyword in ['dal', 'atta', 'rice', 'masala', 'chai']):
                relevant_products.append(product)
        
        return relevant_products
    
    def _handle_pagination(self, products: List[Dict], max_pages: int = 3):
        """Handle multi-page results"""
        for page in range(2, max_pages + 1):
            try:
                # Find page navigation
                page_link = self.driver.find_element(
                    By.XPATH, 
                    f"//a[contains(@class, 'page-numbers') and text()='{page}']"
                )
                
                if page_link:
                    self.driver.execute_script("arguments[0].click();", page_link)
                    time.sleep(3)
                    
                    # Parse new page
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    page_products = self._extract_products_from_page(soup)
                    products.extend(page_products)
                    
                    self.logger.debug(f"Found {len(page_products)} products on page {page}")
            except:
                # Stop when no more pages
                break