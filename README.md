# Grocery Store Price Comparison & AI Matching System

A comprehensive price comparison tool that scrapes grocery stores, uses AI to match similar products, and provides detailed pricing analysis with per-unit comparisons. Specializes in Indian grocery stores with mainstream Canadian retailers.

## Features

- **Multi-Store Web Scraping**: Automated scraping of grocery store websites using Selenium
- **AI-Powered Product Matching**: Hybrid semantic + fuzzy matching using transformer models
- **Per-Unit Price Analysis**: Normalize prices by weight/volume for accurate comparisons
- **Indian Grocery Specialization**: Tailored classification and matching for Indian products
- **Interactive CLI**: User-friendly command-line interface for scraping and analysis
- **Detailed Reporting**: Comprehensive price difference reports by category

## Supported Stores

### Primary Store (Indian Grocery)
- **Made in India Grocery** (Georgetown, Ontario)

### Competitor Stores  
- **Real Canadian Superstore**
- **No Frills**
- **Indian Frootland** (Brampton, Ontario)
- **AFC Grocery** (Toronto, Ontario)

## Architecture

```
├── app/
│   ├── models.py          # SQLAlchemy database models
│   ├── crud.py            # Database operations
│   └── database.py        # Database configuration
├── scrapers/
│   ├── base_scraper.py    # Base scraper class
│   ├── made_in_india_scraper.py
│   └── competitor_scrapers/
├── ai_matching/
│   ├── product_matcher.py # AI matching engine
│   └── config/            # JSON configuration files
├── match_products.py      # Unified matching system
└── scrape_and_compare_*.py # Store-specific scripts
```

## Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd grocery-price-comparison
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install Chrome WebDriver**
- Download ChromeDriver from [https://chromedriver.chromium.org/](https://chromedriver.chromium.org/)
- Add to your PATH or place in project directory

4. **Set up configuration files**
Create JSON configuration files in `ai_matching/config/`:
- `classifications.json` - Product type classifications
- `forbidden.json` - Forbidden match combinations  
- `synonyms.json` - Regional term synonyms
- `brands.json` - Known brand names

## Quick Start

### 1. Scrape Primary Store
```bash
python scrape_made_in_india.py
```

### 2. Scrape Competitor Store
```bash
python scrape_and_compare_superstore.py
python scrape_and_compare_nofrills.py
python scrape_and_compare_indianfrootland.py
```

### 3. Run AI Matching & Analysis
```bash
python match_products.py --primary "Made in India Grocery" --competitor "Real Canadian Superstore"
```

## AI Matching System

### Hybrid Similarity Calculation
- **40% Semantic Similarity**: Using sentence-transformers (all-MiniLM-L6-v2)
- **60% Fuzzy Matching**: Token-based fuzzy string matching
- **Product Classification**: Type and subtype classification for Indian groceries
- **Forbidden Pairs**: Prevents incorrect matches (e.g., spices vs baking items)

### Configuration Examples

**classifications.json**
```json
{
  "categories": [
    {
      "type": "spice",
      "subtype": "cooking_spice", 
      "keywords": ["turmeric", "cumin", "coriander"],
      "description": "Culinary spices for cooking"
    }
  ]
}
```

**forbidden.json**
```json
{
  "pairs": [
    ["baking", "spice"],
    ["frozen:vegetable", "fresh:fruit"]
  ]
}
```

## Usage Examples

### Basic Price Comparison
```bash
python match_products.py --confidence 0.65
```

### Advanced Analysis with Normalization  
```bash
python match_products.py --confidence 0.75 --competitor "No Frills"
```

### Generate Reports Only
```bash
python match_products.py --report-only --primary "Made in India Grocery"
```

## Key Components

### ProductMatcher Class
- Loads external JSON configurations
- Classifies products by type/subtype
- Calculates hybrid similarity scores
- Validates matches with forbidden pair checking

### DatabaseMatcher Class  
- Unified interface for store-to-store matching
- Per-unit price normalization
- Quality validation and reporting
- Generates detailed analysis reports

### Enhanced Size Extraction
- Parses weight, volume, and count units
- Normalizes units (g → kg, ml → l)
- Confidence scoring for size extraction
- Handles Indian grocery naming conventions

## Sample Output

```
🎯 AI MATCHING RESULTS - Made in India Grocery vs Real Canadian Superstore
================================================================================
✅ Found 127 validated matches (confidence ≥ 0.65)

📊 QUALITY METRICS:
  • Average confidence: 0.78
  • Per-unit normalization success: 89.3%
  • Size extraction success: 76.4%

🏷️ SPICES & SEASONINGS CATEGORY ANALYSIS
--------------------------------------------------------------------------------
Top 5 Price Differences:
┌─────────────────────────────────┬────────────┬──────────────┬─────────────┐
│ Product                         │ Our Price  │ Their Price  │ Advantage   │
├─────────────────────────────────┼────────────┼──────────────┼─────────────┤
│ Turmeric Powder 500g            │ $3.99      │ $8.47        │ Made in India│
│ Cumin Seeds 200g                │ $2.49      │ $5.23        │ Made in India│ 
└─────────────────────────────────┴────────────┴──────────────┴─────────────┘
```


## Requirements

- Python 3.8+
- Chrome/Chromium browser
- ChromeDriver
- SQLAlchemy database (SQLite by default)
- Internet connection for scraping
