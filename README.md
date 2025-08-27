# Company Data Scraper

A comprehensive, modular web scraping system for extracting Italian company information from official sources and finding their websites. Built with Python, Selenium, and BeautifulSoup following best practices for maintainability and configurability.

## Features

- **Three-stage scraping pipeline**: Chamber URLs → Company Details → Official Websites
- **Configurable parameters**: All settings externalized in YAML configuration
- **Headless/containerized compatible**: Works in Docker and headless environments
- **Robust validation**: Footer-based website validation with confidence scoring
- **Rate limiting**: Respectful delays and retry mechanisms
- **English naming**: Clean, readable code with English variable/column names
- **Modular design**: Each component can be run independently

## Architecture

### Component 1: Chamber URL Scraper (`chamber_url_scraper.py`)

- Finds company pages on Italian Chamber of Commerce website (ufficiocamerale.it)
- Uses requests + BeautifulSoup for headless compatibility
- Searches via Startpage with site-specific queries
- **Input**: `companies_base.csv` (company names, legal forms, tax codes)
- **Output**: `chamber_urls.csv` (URLs to Chamber of Commerce pages)

### Component 2: Company Data Scraper (`company_data_scraper.py`)

- Extracts detailed company information using Selenium
- Scrapes: VAT numbers, addresses, PEC emails, revenue, employee data
- Uses regex patterns to extract structured data from Chamber pages
- **Input**: `chamber_urls.csv`
- **Output**: `companies_detailed.csv` (enriched company data)

### Component 3: Website Finder (`company_website_finder.py`)

- Finds and validates official company websites
- Uses Startpage search with targeted queries including PEC data
- Validates websites using footer analysis and confidence scoring
- **Input**: `companies_detailed.csv`
- **Output**: `company_websites.csv` (validated official websites)

## Installation

### Prerequisites

- Python 3.8+
- Firefox browser (for Selenium)
- Virtual environment (recommended)

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd nexthera-matching

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

All parameters are configurable via `config.yml`:

```yaml
# Data Sources
data_sources:
  chamber_of_commerce_url: "https://www.ufficiocamerale.it"
  search_engine_url: "https://www.startpage.com/sp/search"

# File Paths
file_paths:
  input_file: "companies_base.csv"
  chamber_urls_output: "chamber_urls.csv"
  detailed_data_output: "companies_detailed.csv"
  websites_output: "company_websites.csv"

# Scraping Settings
scraping:
  request_delay: 2 # Seconds between requests
  validation_delay: 1 # Seconds between validations
  company_delay: 3 # Seconds between companies
  page_timeout: 15 # Page load timeout
  selenium_timeout: 10 # Selenium wait timeout
  max_candidate_websites: 8
  headless_mode: true
  browser_width: 1920
  browser_height: 1080

# Validation Settings
validation:
  confidence_threshold: 50 # Minimum score for valid website
  footer_score_cap: 60 # Maximum points from footer
  name_match_weight: 15 # Points per name match
  tax_code_score: 25 # Points for tax code match

# Search Settings
search:
  excluded_domains: # Domains to skip in search results
    - "facebook.com"
    - "linkedin.com"
    - "wikipedia.org"
    # ... more domains
```

## Usage

### Input Data Format

Create your input file based on `companies_base.csv.example`:

```csv
company_name,legal_form,tax_code
EXAMPLE COMPANY SPA,SPA,12345678901
SAMPLE SRL,S.R.L.,98765432109
```

### Running the Pipeline

#### Option 1: Run Complete Pipeline

```bash
# Run all three components sequentially
python chamber_url_scraper.py --limit 10
python company_data_scraper.py --limit 10 --headless
python company_website_finder.py --limit 10 --headless
```

#### Option 2: Run Individual Components

```bash
# Component 1: Find Chamber URLs
python chamber_url_scraper.py --config config.yml --limit 5

# Component 2: Extract company details
python company_data_scraper.py --input chamber_urls.csv --headless

# Component 3: Find official websites
python company_website_finder.py --input companies_detailed.csv --headless
```

### Command Line Options

All components support these options:

- `--limit N`: Process only first N companies
- `--config FILE`: Use custom configuration file
- `--input FILE`: Override input file from config
- `--output FILE`: Override output file from config
- `--headless`: Run browser in headless mode (Components 2 & 3)

### Example Commands

```bash
# Process first 3 companies with custom config
python chamber_url_scraper.py --limit 3 --config my_config.yml

# Run data scraper in GUI mode for debugging
python company_data_scraper.py --limit 5

# Find websites with custom input/output files
python company_website_finder.py \
  --input my_companies.csv \
  --output my_websites.csv \
  --headless
```

## Output Files

### Chamber URLs (`chamber_urls.csv`)

```csv
company_name,legal_form,tax_code,chamber_url,status
SIELTE,SPA,00941910788,https://www.ufficiocamerale.it/...,found
```

### Company Details (`companies_detailed.csv`)

```csv
company_name,legal_form,tax_code,vat_number,address,pec_email,latest_revenue,latest_revenue_year,latest_employees,latest_employees_year
SIELTE,SPA,00941910788,00941910788,"Via Roma 1, Milano",direzione@pec.sielte.it,50000000,2023,250,2023
```

### Company Websites (`company_websites.csv`)

```csv
company_name,legal_form,tax_code,official_website,confidence_score,validation_status,page_title
SIELTE,SPA,00941910788,https://www.sielte.it/,100,validated,"SIELTE - Digital Solutions"
```

## Validation Logic

The website validation system uses a sophisticated scoring algorithm:

### Footer Analysis (Priority 1)

- **Company name in footer**: +20 points
- **Tax code in footer**: +30 points
- **VAT pattern in footer**: +25 points
- **Maximum footer score**: 60 points

### Content Analysis (Priority 2)

- **Company name variations**: +15 points each (max 45)
- **Tax code anywhere on page**: +25 points
- **Business registration patterns**: +10 points each (max 30)

### Confidence Threshold

- **Valid website**: ≥50 points
- **High confidence**: ≥80 points

## Best Practices

### Rate Limiting

- Default 2-second delays between requests
- Configurable timeouts and retry mechanisms
- Respectful of target websites

### Error Handling

- Graceful handling of network errors
- Detailed logging of failures
- Partial results saved on interruption

### Headless Compatibility

- Component 1 uses requests/BeautifulSoup (no browser needed)
- Components 2 & 3 support headless Firefox
- Docker-friendly configuration

## Troubleshooting

### Common Issues

**Firefox/Selenium Issues**

```bash
# Update webdriver-manager
pip install --upgrade webdriver-manager

# Run in non-headless mode for debugging
python company_data_scraper.py --limit 1
```

**Search Rate Limiting**

```bash
# Increase delays in config.yml
scraping:
  request_delay: 5
  company_delay: 10
```

**Memory Issues**

```bash
# Process in smaller batches
python chamber_url_scraper.py --limit 10
```

### Debug Mode

Run without `--headless` to see browser actions:

```bash
python company_data_scraper.py --limit 1
python company_website_finder.py --limit 1
```

## Development

### Project Structure

```
nexthera-matching/
├── chamber_url_scraper.py      # Component 1: Find Chamber URLs
├── company_data_scraper.py     # Component 2: Extract company data
├── company_website_finder.py   # Component 3: Find/validate websites
├── config.yml                  # Configuration file
├── requirements.txt            # Python dependencies
├── companies_base.csv.example  # Input format example
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

### Code Style

- **English naming**: All variables, functions, and columns in English
- **Type hints**: Function signatures include type information
- **Docstrings**: Comprehensive documentation for all methods
- **Configuration-driven**: No hardcoded values
- **Error handling**: Robust exception handling throughout

### Contributing

1. Follow existing code style and naming conventions
2. Add configuration options for new parameters
3. Include comprehensive error handling
4. Update documentation for new features
5. Test with small datasets first

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built for Italian company data extraction
- Uses official Chamber of Commerce sources
- Respects robots.txt and rate limiting
- Designed for research and business intelligence purposes

---

**Note**: This tool is designed for legitimate business research. Please respect website terms of service and applicable laws when scraping data.
