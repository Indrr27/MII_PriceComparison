# scrapers/base_scraper.py

from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Optional

class BaseScraper(ABC):
    """Base class for all grocery store scrapers"""
    
    def __init__(self, headless: bool = True, delay: float = 1.0):
        self.headless = headless
        self.delay = delay
        self.driver = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def setup_driver(self):
        """Initialize Chrome WebDriver with anti-detection options"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Anti-detection measures
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Rotate user agents to appear more human
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0"
        ]
        import random
        selected_ua = random.choice(user_agents)
        chrome_options.add_argument(f"--user-agent={selected_ua}")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # Execute script to remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.driver.implicitly_wait(15)  # Longer implicit wait
        
    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            
    def wait_and_get_page_source(self, url: str, wait_element: str = None) -> str:
        """Navigate to URL and return page source"""
        self.driver.get(url)
        
        if wait_element:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_element))
                )
            except Exception as e:
                self.logger.warning(f"Wait element {wait_element} not found: {e}")
        
        time.sleep(self.delay)
        return self.driver.page_source
    
    def extract_price_from_text(self, text: str) -> Optional[float]:
        """Extract price from text string"""
        import re
        # Common price patterns: $3.99, 3.99, CAD 3.99
        price_patterns = [
            r'\$(\d+\.?\d*)',
            r'CAD\s*(\d+\.?\d*)',
            r'(\d+\.\d{2})',
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text.replace(',', ''))
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None
    
    @abstractmethod
    def scrape_products(self) -> List[Dict]:
        """Scrape products from the store. Must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def get_store_info(self) -> Dict:
        """Return store information"""
        pass
    
    def scrape_with_error_handling(self) -> List[Dict]:
        """Main scraping method with error handling"""
        try:
            self.setup_driver()
            products = self.scrape_products()
            self.logger.info(f"Successfully scraped {len(products)} products")
            return products
        except Exception as e:
            self.logger.error(f"Scraping failed: {e}")
            return []
        finally:
            self.close_driver()