# Company Intelligence Pipeline

A comprehensive 7-step pipeline for extracting, analyzing, and providing intelligent access to Italian company data from Chamber of Commerce sources.

## 🎯 Overview

This project implements a complete company intelligence system that systematically processes Italian companies through multiple data sources to create a comprehensive business intelligence database. The system is designed to work in headless/containerized environments and provides both structured data output and natural language access through an AI-powered chatbot.

### Key Features

- **Headless Operation**: Fully compatible with Docker and containerized environments
- **Multi-Source Integration**: Combines official Chamber of Commerce data with web intelligence
- **AI-Powered Analysis**: Uses Ollama for natural language processing and content analysis
- **Comprehensive Coverage**: Extracts financial data, certifications, contact information, and business intelligence
- **Italian Language Support**: Optimized for Italian business data and queries

## 🔄 Pipeline Architecture

The system follows a sequential 7-step process:

1. **Chamber URL Discovery** → Finds official Chamber of Commerce pages
2. **Detailed Data Extraction** → Scrapes comprehensive company information
3. **Website Discovery** → Identifies and validates official company websites
4. **Intelligence Analysis** → Analyzes websites for business intelligence
5. **Document Analysis** → Processes Chamber PDF documents for certifications
6. **Data Consolidation** → Creates unified data structure for AI access
7. **AI Chatbot Interface** → Provides natural language access to all data

## Pipeline Steps

### Step 1: Chamber URL Scraper

**Script:** `chamber_url_scraper.py`

- Searches Chamber of Commerce database for companies
- Extracts official chamber URLs for each company
- **Output:** `chamber_urls.csv`

### Step 2: Company Data Scraper

**Script:** `company_data_scraper.py`

- Scrapes detailed company information from chamber URLs
- Extracts financial data, contact information, legal details
- **Output:** `companies_detailed.csv`

### Step 3: Website Finder

**Script:** `company_website_finder.py`

- Finds and validates official company websites
- Uses intelligent scoring to determine website authenticity
- **Output:** `company_websites.csv`

### Step 4: Website Intelligence

**Script:** `company_intelligence_scraper.py`

- Analyzes company websites for business intelligence
- Extracts technologies, contacts, business classification
- **Output:** `company_intelligence.json`

### Step 5: Chamber Document Analysis

**Script:** `chamber_document_analyzer.py`

- Downloads and analyzes Chamber of Commerce PDF documents
- Extracts certifications, SOA attestations, technical authorizations
- **Output:** `chamber_analysis.json`

### Step 6: Data Consolidation

**Script:** `create_unified_company_data.py`

- Consolidates all pipeline data into a single, optimized structure
- Creates AI-friendly format for improved chatbot performance
- **Output:** `unified_company_data.json`

### Step 7: AI Chatbot Interface

**Script:** `intelligent_chatbot.py`

- Provides natural language access to all collected data
- Uses Ollama for query analysis and response generation
- Supports Italian language queries about companies

## Additional Tools

### Testing Framework

**Script:** `test_chatbot_data_sources.py`

- Comprehensive testing of chatbot data access capabilities
- Validates all query types and data sources

## Setup

### Prerequisites

- Python 3.8+
- Virtual environment recommended

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd <project-directory>

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Copy `companies_base.csv.example` to `companies_base.csv`
2. Add your target companies to the CSV file
3. Configure `config.yml` with your settings:
   - Ollama endpoint and model
   - Scraping delays and timeouts
   - File paths and validation settings

## Usage

### Running the Complete Pipeline

Execute each step in sequence:

```bash
# Step 1: Get Chamber URLs
python chamber_url_scraper.py

# Step 2: Extract Company Details
python company_data_scraper.py --headless

# Step 3: Find Company Websites
python company_website_finder.py --headless

# Step 4: Analyze Websites
python company_intelligence_scraper.py --headless

# Step 5: Analyze Chamber Documents
python chamber_document_analyzer.py

# Step 6: Consolidate Data
python create_unified_company_data.py

# Step 7: Start Chatbot
python intelligent_chatbot.py
```

### Command Line Options

Most scripts support the following options:

- `--limit N`: Process only the first N companies (useful for testing)
- `--headless`: Run browser in headless mode (required for containerized environments)
- `--config PATH`: Use custom configuration file (default: config.yml)

**Examples:**

```bash
# Process only 5 companies for testing
python chamber_url_scraper.py --limit 5

# Run in headless mode for production/containers
python company_data_scraper.py --headless

# Use custom configuration
python company_intelligence_scraper.py --config my_config.yml

# Combine options
python company_website_finder.py --limit 10 --headless --config production.yml
```

### Using the Chatbot

The chatbot supports Italian language queries such as:

- "Dimmi tutto su [COMPANY NAME]"
- "Quali certificazioni ha [COMPANY NAME]?"
- "Contatti di [COMPANY NAME]"
- "Qual è il fatturato di [COMPANY NAME]?"

## Features

### Data Sources Integration

- Chamber of Commerce official data
- Company websites and business intelligence
- PDF document analysis for certifications
- Financial and contact information

### Intelligent Analysis

- Website content classification
- Technology stack detection
- Certification extraction from documents
- Business activity categorization

### Natural Language Interface

- Italian language support
- Context-aware responses
- Multi-source data integration
- Ollama-powered AI responses

## Configuration Options

### Scraping Settings

- Request delays and timeouts
- Browser settings (headless mode)
- Retry limits and validation thresholds

### AI Integration

- Ollama model selection
- Temperature and response settings
- Context length limits

### Data Processing

- Industry classification taxonomy
- Validation scoring weights
- Output format preferences

## Output Files

All output files are excluded from git via `.gitignore`:

- `chamber_urls.csv` - Chamber of Commerce URLs
- `companies_detailed.csv` - Detailed company information
- `company_websites.csv` - Validated company websites
- `company_intelligence.json` - Website analysis results
- `chamber_analysis.json` - Document analysis results
- `unified_company_data.json` - Consolidated data structure

## Industry Classification

The system includes a comprehensive industry classification taxonomy in `industry_classification.json` covering:

- Information Technology and Software
- Telecommunications and Networking
- Industrial Automation
- Construction and Infrastructure
- Energy and Utilities
- And many more specialized sectors

## Requirements

See `requirements.txt` for complete dependency list. Key dependencies:

- `selenium` - Web scraping and browser automation
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `pyyaml` - Configuration management
- `PyPDF2` & `PyMuPDF` - PDF document processing
- `lxml` - XML/HTML parsing
- `webdriver-manager` - Automatic browser driver management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is provided as-is for educational and research purposes.

## Disclaimer

This tool is designed for legitimate business intelligence and research purposes. Users are responsible for ensuring compliance with applicable laws and website terms of service when scraping data.
