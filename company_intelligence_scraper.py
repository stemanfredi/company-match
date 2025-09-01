#!/usr/bin/env python3
"""
Company Intelligence Scraper - Step 4
=====================================

Advanced intelligence gathering system that analyzes company websites to extract:
- Leadership information (CEO, directors)
- Contact details (emails, phone numbers, addresses)
- Business intelligence (services, technologies, market focus)
- AI-powered industry classification using Ollama

This is the consolidated version combining all intelligence gathering capabilities
developed through iterative improvements and testing.

Usage: python company_intelligence_scraper.py [--limit N] [--config config.yml] [--headless]
"""

import csv
import time
import argparse
import re
import yaml
import json
from urllib.parse import urlparse, urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager
import requests
from bs4 import BeautifulSoup


class CompanyIntelligenceScraper:
    """
    Advanced company intelligence scraper with AI-powered classification.

    Features:
    - Smart link discovery with technology-specific scoring
    - Enhanced contact information extraction (emails, phones, addresses)
    - Leadership detection with Italian business titles
    - Multi-technology classification using Ollama AI
    - Comprehensive business intelligence gathering
    """

    def __init__(self, config_path="config.yml", headless=True):
        """Initialize intelligence scraper with configuration"""
        self.config = self._load_config(config_path)
        self.headless = headless
        self.driver = None
        self.wait = None
        self.industry_taxonomy = self._load_taxonomy()
        self._setup_driver()

    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                if "intelligence" not in config:
                    config["intelligence"] = self._default_intelligence_config()
                return config
        except FileNotFoundError:
            print(f"Warning: Config file {config_path} not found, using defaults")
            return self._default_config()

    def _default_config(self):
        """Default configuration if file not found"""
        return {
            "file_paths": {
                "websites_output": "company_websites.csv",
                "intelligence_output": "company_intelligence.json",
                "taxonomy_file": "industry_classification.json",
            },
            "scraping": {
                "request_delay": 2,
                "company_delay": 3,
                "page_timeout": 15,
                "selenium_timeout": 10,
                "browser_width": 1920,
                "browser_height": 1080,
            },
            "intelligence": self._default_intelligence_config(),
        }

    def _default_intelligence_config(self):
        """Default intelligence-specific configuration"""
        return {
            "max_pages_per_site": 5,
            "content_analysis_timeout": 30,
            "classification_confidence_threshold": 0.6,
            "ollama_endpoint": "http://ollama.lan:11434/api/generate",
            "ollama_model": "gemma3:12b",
            "ollama_stream": False,
            "ollama_temperature": 0.3,
            "ollama_top_p": 0.9,
            "ollama_timeout": 60,
            "pages_to_analyze": [
                "/",
                "/about",
                "/chi-siamo",
                "/azienda",
                "/servizi",
                "/products",
                "/prodotti",
                "/contatti",
                "/contact",
            ],
        }

    def _load_taxonomy(self):
        """Load industry taxonomy from JSON file"""
        try:
            taxonomy_file = self.config["file_paths"]["taxonomy_file"]
            with open(taxonomy_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"Warning: Taxonomy file not found, using empty taxonomy")
            return {}

    def _setup_driver(self):
        """Setup Firefox WebDriver with options"""
        firefox_options = Options()
        if self.headless:
            firefox_options.add_argument("--headless")
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")
        firefox_options.add_argument(
            f"--width={self.config['scraping']['browser_width']}"
        )
        firefox_options.add_argument(
            f"--height={self.config['scraping']['browser_height']}"
        )
        firefox_options.set_preference(
            "general.useragent.override",
            "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
        )

        service = Service(GeckoDriverManager().install())
        self.driver = webdriver.Firefox(service=service, options=firefox_options)
        self.wait = WebDriverWait(
            self.driver, self.config["scraping"]["selenium_timeout"]
        )

    def extract_website_intelligence(self, url, company_name):
        """Extract comprehensive intelligence from company website"""
        intelligence = {
            "ceo_managing_director": None,
            "info_emails": [],
            "phone_numbers": [],
            "key_contacts": [],
            "addresses": [],
            "company_references": [],
            "website_content": "",
            "analyzed_pages": [],
        }

        if not url or not url.startswith("http"):
            return intelligence

        try:
            print(f"  Analyzing website: {url}")

            # Discover and analyze multiple pages
            pages_to_check = self._discover_pages_to_analyze(url)

            for page_url in pages_to_check:
                try:
                    print(f"    Analyzing page: {page_url}")
                    self.driver.get(page_url)
                    time.sleep(2)

                    # Get page content
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    page_html = self.driver.page_source

                    intelligence["analyzed_pages"].append(page_url)
                    intelligence[
                        "website_content"
                    ] += f"\n--- {page_url} ---\n{page_text}\n"

                    # Extract information
                    self._extract_leadership_info(page_text, intelligence)
                    self._extract_contact_info(page_html, intelligence)
                    self._extract_addresses(page_text, intelligence)
                    self._extract_company_references(
                        page_text, company_name, intelligence
                    )

                    time.sleep(self.config["scraping"]["request_delay"])

                except Exception as e:
                    print(f"    ✗ Error analyzing page {page_url}: {e}")
                    continue

            # Clean and deduplicate extracted data
            self._clean_intelligence_data(intelligence)

            print(
                f"  ✓ Extracted intelligence from {len(intelligence['analyzed_pages'])} pages"
            )
            return intelligence

        except Exception as e:
            print(f"  ✗ Intelligence extraction error: {e}")
            return intelligence

    def _discover_pages_to_analyze(self, base_url):
        """Smart page discovery with technology-specific scoring"""
        pages = []
        base_domain = urlparse(base_url).netloc

        # Always include the main page first
        homepage = base_url.rstrip("/") + "/"
        pages.append(homepage)

        try:
            print(f"    Discovering links from homepage...")
            self.driver.get(homepage)
            time.sleep(2)

            # Enhanced link discovery
            discovered_links = self._discover_internal_links(base_url)

            # Add discovered links (up to limit)
            max_additional_pages = self.config["intelligence"]["max_pages_per_site"] - 1
            pages.extend(discovered_links[:max_additional_pages])

        except Exception as e:
            print(f"    ✗ Link discovery failed: {e}, using fallback pages")
            # Fallback to predefined pages
            for path in self.config["intelligence"]["pages_to_analyze"][1:]:
                if len(pages) >= self.config["intelligence"]["max_pages_per_site"]:
                    break
                page_url = urljoin(base_url, path)
                pages.append(page_url)

        return pages[: self.config["intelligence"]["max_pages_per_site"]]

    def _discover_internal_links(self, base_url):
        """Enhanced link discovery with technology-specific scoring"""
        base_domain = urlparse(base_url).netloc
        discovered_links = []

        try:
            link_elements = self.driver.find_elements(By.TAG_NAME, "a")

            # Priority keywords with technology focus
            priority_keywords = [
                # Company info (high priority)
                "about",
                "chi-siamo",
                "azienda",
                "company",
                "about-us",
                # Services and solutions (high priority)
                "servizi",
                "services",
                "soluzioni",
                "solutions",
                "prodotti",
                "products",
                "portfolio",
                # Technology specific (high priority)
                "tecnologie",
                "technology",
                "tech",
                "innovation",
                "innovazione",
                "software",
                "hardware",
                "sistemi",
                "systems",
                # Market focus
                "settori",
                "markets",
                "industries",
                "clienti",
                "customers",
                # Contact and team
                "contatti",
                "contact",
                "contacts",
                "team",
                "staff",
                "people",
                # Additional useful pages
                "storia",
                "history",
                "mission",
                "news",
                "notizie",
                "press",
                "case-study",
                "progetti",
                "projects",
                "competenze",
                "expertise",
                "capabilities",
                "certificazioni",
                "certifications",
            ]

            # Score and collect links
            link_scores = []

            for link in link_elements:
                try:
                    href = link.get_attribute("href")
                    text = link.text.strip().lower()

                    if not href or not text:
                        continue

                    # Parse URL
                    parsed_url = urlparse(href)

                    # Only internal links
                    if parsed_url.netloc and parsed_url.netloc != base_domain:
                        continue

                    # Make absolute URL
                    if not parsed_url.netloc:
                        href = urljoin(base_url, href)

                    # Skip certain patterns
                    if any(
                        skip in href.lower()
                        for skip in [
                            "#",
                            "javascript:",
                            "mailto:",
                            "tel:",
                            ".pdf",
                            ".doc",
                            ".jpg",
                            ".png",
                            ".gif",
                        ]
                    ):
                        continue

                    # Calculate relevance score
                    score = 0
                    href_lower = href.lower()

                    # Keyword matching in text and URL
                    for keyword in priority_keywords:
                        if keyword in text or keyword in href_lower:
                            score += 10

                    # Enhanced bonus scoring
                    if any(
                        pattern in href_lower
                        for pattern in ["/about", "/chi-siamo", "/azienda"]
                    ):
                        score += 25  # Company info is crucial
                    if any(
                        pattern in href_lower
                        for pattern in ["/servizi", "/services", "/soluzioni"]
                    ):
                        score += 20  # Services are very important
                    if any(
                        pattern in href_lower
                        for pattern in ["/prodotti", "/products", "/portfolio"]
                    ):
                        score += 20  # Products are very important
                    if any(
                        pattern in href_lower
                        for pattern in ["/tecnologie", "/technology", "/tech"]
                    ):
                        score += 18  # Technology pages are important
                    if any(
                        pattern in href_lower for pattern in ["/contatti", "/contact"]
                    ):
                        score += 15  # Contact info is important

                    if score > 0:
                        link_scores.append((href, score, text))

                except Exception:
                    continue

            # Sort by score and remove duplicates
            link_scores.sort(key=lambda x: x[1], reverse=True)
            seen_urls = set()

            for href, score, text in link_scores:
                if href not in seen_urls and len(discovered_links) < 10:
                    discovered_links.append(href)
                    seen_urls.add(href)
                    print(f"      Found: {text[:30]}... (score: {score}) -> {href}")

        except Exception as e:
            print(f"    ✗ Error discovering links: {e}")

        return discovered_links

    def _extract_leadership_info(self, page_text, intelligence):
        """Enhanced CEO/managing director extraction with Italian titles"""
        leadership_patterns = [
            # Enhanced patterns with Italian titles
            r"(?:ceo|amministratore\s+delegato|direttore\s+generale|presidente|managing\s+director)[:\s]*([A-Z][a-zA-Z\s]+(?:[A-Z][a-zA-Z\s]*){1,3})",
            r"([A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)(?:\s*[-,]\s*(?:ceo|amministratore\s+delegato|direttore\s+generale|presidente))",
            r"(?:dott\.?\s*|ing\.?\s*|prof\.?\s*|dr\.?\s*)?([A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)(?:\s*[-,]\s*(?:ceo|amministratore\s+delegato|managing\s+director))",
            # New patterns for Italian business context
            r"(?:fondatore|founder)[:\s]*(?:dott\.?\s*|ing\.?\s*|prof\.?\s*)?([A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)",
            r"(?:direttore\s+tecnico|cto|chief\s+technology\s+officer)[:\s]*(?:dott\.?\s*|ing\.?\s*)?([A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)",
            r"(?:responsabile|manager)[:\s]*(?:dott\.?\s*|ing\.?\s*)?([A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)",
        ]

        for pattern in leadership_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                name = match.strip()
                if len(name) > 5 and len(name) < 60:
                    # Clean up common false positives
                    if not any(
                        word in name.lower()
                        for word in ["cookie", "privacy", "policy", "terms"]
                    ):
                        if not intelligence["ceo_managing_director"]:
                            intelligence["ceo_managing_director"] = name
                        break

    def _extract_contact_info(self, page_html, intelligence):
        """Enhanced contact extraction with Italian patterns and phone numbers"""
        soup = BeautifulSoup(page_html, "html.parser")

        # Enhanced email extraction
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, soup.get_text())

        for email in emails:
            email = email.lower()
            if email not in intelligence["info_emails"]:
                # Enhanced prioritization for Italian business emails
                if any(
                    prefix in email
                    for prefix in [
                        "info@",
                        "contact@",
                        "amministrazione@",
                        "segreteria@",
                        "commerciale@",
                        "vendite@",
                        "sales@",
                        "marketing@",
                    ]
                ):
                    intelligence["info_emails"].insert(0, email)
                else:
                    intelligence["info_emails"].append(email)

        # Phone number extraction with Italian patterns
        phone_patterns = [
            r"\+39\s*[0-9\s\-\.]{8,15}",  # Italian international format
            r"0[0-9]{1,3}[\s\-\.]*[0-9]{6,10}",  # Italian national format
            r"[0-9]{3}[\s\-\.]*[0-9]{3}[\s\-\.]*[0-9]{4}",  # Generic format
            r"tel[:\s]*([0-9\+\s\-\.]{8,20})",  # Tel: prefix
            r"telefono[:\s]*([0-9\+\s\-\.]{8,20})",  # Italian telefono prefix
        ]

        page_text = soup.get_text()
        for pattern in phone_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                phone = match.strip() if isinstance(match, str) else match
                # Clean up phone number
                phone = re.sub(r"[^\d\+]", "", phone)
                if len(phone) >= 8 and phone not in intelligence["phone_numbers"]:
                    intelligence["phone_numbers"].append(phone)

    def _extract_addresses(self, page_text, intelligence):
        """Enhanced address extraction with Italian patterns"""
        address_patterns = [
            # Enhanced Italian address patterns
            r"(?:via|viale|piazza|corso|largo|strada|vicolo)\s+([A-Z][^,\n]*\d+[^,\n]*(?:,\s*\d{5}[^,\n]*)?(?:,\s*[A-Z][a-zA-Z\s]*)?)",
            r"sede\s*(?:legale|operativa)?[:\s]*([A-Z][^.\n]*(?:via|viale|piazza|corso|largo)[^.\n]*)",
            r"indirizzo[:\s]*([A-Z][^.\n]*(?:via|viale|piazza|corso|largo)[^.\n]*)",
            # New patterns for complete addresses
            r"([A-Z][^,\n]*(?:via|viale|piazza|corso|largo)[^,\n]*,\s*\d{5}\s*[A-Z][a-zA-Z\s]*(?:\([A-Z]{2}\))?)",
            r"(?:presso|c/o)[:\s]*([A-Z][^.\n]*(?:via|viale|piazza|corso|largo)[^.\n]*)",
        ]

        for pattern in address_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                address = match.strip()
                if len(address) > 15 and address not in intelligence["addresses"]:
                    # Clean up address
                    address = re.sub(r"\s+", " ", address)  # Normalize whitespace
                    intelligence["addresses"].append(address[:250])

    def _extract_company_references(self, page_text, company_name, intelligence):
        """Extract relevant company references and business descriptions"""
        business_keywords = [
            "servizi",
            "products",
            "prodotti",
            "soluzioni",
            "solutions",
            "specializzati",
            "esperienza",
            "competenze",
            "tecnologie",
            "settori",
            "mercati",
            "clienti",
            "progetti",
            "innovation",
            "innovazione",
            "software",
            "hardware",
            "sistemi",
            "systems",
        ]

        sentences = re.split(r"[.!?]+", page_text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 25 and len(sentence) < 350:
                if any(keyword in sentence.lower() for keyword in business_keywords):
                    if sentence not in intelligence["company_references"]:
                        intelligence["company_references"].append(sentence)

    def _clean_intelligence_data(self, intelligence):
        """Enhanced data cleaning with appropriate limits"""
        # Set reasonable limits
        intelligence["info_emails"] = intelligence["info_emails"][:8]
        intelligence["phone_numbers"] = intelligence["phone_numbers"][:5]
        intelligence["addresses"] = intelligence["addresses"][:4]
        intelligence["company_references"] = intelligence["company_references"][:12]

        # Remove duplicates while preserving order
        intelligence["info_emails"] = list(dict.fromkeys(intelligence["info_emails"]))
        intelligence["phone_numbers"] = list(
            dict.fromkeys(intelligence["phone_numbers"])
        )
        intelligence["addresses"] = list(dict.fromkeys(intelligence["addresses"]))
        intelligence["company_references"] = list(
            dict.fromkeys(intelligence["company_references"])
        )

    def classify_company_content(self, content, company_name):
        """Classify company content using Ollama AI with fallback to direct analysis"""
        print(f"  Analyzing content for classification...")

        # Try Ollama AI first
        ollama_result = self._analyze_content_ollama(content, company_name)
        if ollama_result and ollama_result.get("confidence_score", 0) > 0:
            return ollama_result

        # Fallback to direct analysis
        print(f"  Falling back to direct content analysis...")
        return self._analyze_content_direct(content, company_name)

    def _analyze_content_ollama(self, content, company_name):
        """Enhanced Ollama analysis with improved prompts"""
        try:
            # Prepare taxonomy categories for the prompt
            categories_list = []
            for category, subcategories in self.industry_taxonomy.items():
                categories_list.append(
                    f"- {category}: {', '.join(subcategories[:4])}..."
                )

            taxonomy_text = "\n".join(categories_list)

            # Enhanced prompt for comprehensive multi-category classification
            prompt = f"""Analizza il seguente contenuto di un sito web di un'azienda italiana e identifica TUTTE le aree industriali in cui opera secondo la tassonomia fornita.

AZIENDA: {company_name}

CONTENUTO SITO WEB:
{content[:4000]}

TASSONOMIA DISPONIBILE:
{taxonomy_text}

ISTRUZIONI CRITICHE:
1. NON limitarti a una sola categoria - identifica TUTTE le aree operative dell'azienda
2. Cerca evidenze per 15-25 tecnologie/servizi diversi se presenti nel contenuto
3. Analizza ogni paragrafo per tecnologie, servizi, prodotti, competenze, certificazioni
4. Includi categorie anche con confidence basso (0.3+) se c'è evidenza testuale
5. Considera sinonimi, acronimi e terminologie tecniche specifiche
6. Analizza sia servizi offerti che tecnologie utilizzate internamente

FORMATO RISPOSTA JSON ESTESO:
{{
    "all_applicable_categories": [
        {{
            "category": "nome_categoria",
            "confidence": 0.85,
            "subcategories_found": ["sub1", "sub2", "sub3"],
            "evidence_keywords": ["keyword1", "keyword2"],
            "text_evidence": ["frase_dal_contenuto_1", "frase_dal_contenuto_2"],
            "relevance_score": 0.75
        }}
    ],
    "comprehensive_technology_analysis": {{
        "total_technologies_identified": 18,
        "primary_business_areas": ["area1", "area2", "area3"],
        "secondary_business_areas": ["area4", "area5"],
        "emerging_areas": ["area6"],
        "technology_stack": ["tech1", "tech2", "tech3", "tech4", "tech5"],
        "service_offerings": ["servizio1", "servizio2", "servizio3"],
        "market_verticals": ["verticale1", "verticale2"],
        "certifications_mentioned": ["cert1", "cert2"],
        "partnerships_technologies": ["partner_tech1", "partner_tech2"]
    }},
    "business_intelligence": {{
        "company_size_indicators": "piccola/media/grande",
        "geographic_scope": "locale/nazionale/internazionale",
        "business_model": "descrizione_modello",
        "competitive_advantages": ["vantaggio1", "vantaggio2"],
        "target_markets": ["mercato1", "mercato2"]
    }},
    "confidence_analysis": {{
        "overall_confidence": 0.82,
        "content_quality": "alta/media/bassa",
        "technical_depth": "alta/media/bassa",
        "coverage_completeness": 0.75
    }}
}}

IMPORTANTE: Identifica OGNI possibile area operativa, anche quelle secondarie o di supporto. Un'azienda può operare in 6-12 categorie diverse.
Rispondi SOLO con JSON valido:"""

            # Prepare Ollama request
            ollama_request = {
                "model": self.config["intelligence"]["ollama_model"],
                "prompt": prompt,
                "stream": self.config["intelligence"]["ollama_stream"],
                "options": {
                    "temperature": self.config["intelligence"]["ollama_temperature"],
                    "top_p": self.config["intelligence"]["ollama_top_p"],
                },
            }

            # Make request to Ollama API
            response = requests.post(
                self.config["intelligence"]["ollama_endpoint"],
                json=ollama_request,
                timeout=self.config["intelligence"]["ollama_timeout"],
            )

            if response.status_code == 200:
                result = response.json()
                ollama_response = result.get("response", "")

                # Extract JSON from response
                json_start = ollama_response.find("{")
                json_end = ollama_response.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = ollama_response[json_start:json_end]
                    classification = json.loads(json_str)

                    # Enhanced validation and normalization for new format
                    all_categories = classification.get("all_applicable_categories", [])
                    tech_analysis = classification.get(
                        "comprehensive_technology_analysis", {}
                    )
                    business_intel = classification.get("business_intelligence", {})
                    confidence_analysis = classification.get("confidence_analysis", {})

                    # Convert to compatible format while preserving new data
                    normalized_classification = {
                        "all_applicable_categories": all_categories,
                        "comprehensive_technology_analysis": tech_analysis,
                        "business_intelligence": business_intel,
                        "confidence_analysis": confidence_analysis,
                        # Legacy format for compatibility
                        "primary_category": (
                            all_categories[0]["category"] if all_categories else None
                        ),
                        "secondary_categories": (
                            [cat["category"] for cat in all_categories[1:6]]
                            if len(all_categories) > 1
                            else []
                        ),
                        "technologies": all_categories,  # Use new comprehensive format
                        "confidence_score": confidence_analysis.get(
                            "overall_confidence", 0.0
                        ),
                        "matched_keywords": [
                            kw
                            for cat in all_categories
                            for kw in cat.get("evidence_keywords", [])
                        ],
                        "business_focus": business_intel.get("business_model", ""),
                        "technology_stack": tech_analysis.get("technology_stack", []),
                        "market_segments": tech_analysis.get("market_verticals", []),
                        "total_categories_found": len(all_categories),
                        "total_technologies_identified": tech_analysis.get(
                            "total_technologies_identified", 0
                        ),
                    }

                    print(
                        f"  ✓ Ollama comprehensive analysis: {len(all_categories)} categories found"
                    )
                    if all_categories:
                        primary = all_categories[0]["category"]
                        confidence = all_categories[0].get("confidence", 0.0)
                        print(f"    Primary: {primary} (confidence: {confidence:.2f})")
                        print(
                            f"    Total technologies: {tech_analysis.get('total_technologies_identified', 0)}"
                        )

                    return normalized_classification

        except Exception as e:
            print(f"  ✗ Ollama integration error: {e}")

        return None

    def _analyze_content_direct(self, content, company_name):
        """Enhanced direct content analysis with improved multi-technology detection"""
        content_lower = content.lower()

        classification = {
            "technologies": [],
            "business_focus": "",
            "technology_stack": [],
            "market_segments": [],
            "overall_confidence": 0.0,
            "matched_keywords": [],
            "suggested_new_categories": [],
        }

        # Enhanced analysis against taxonomy
        category_scores = {}

        for category, subcategories in self.industry_taxonomy.items():
            category_score = 0
            matched_keywords = []
            matched_subcategories = []
            evidence = []

            # Check category name
            if category.lower() in content_lower:
                category_score += 15
                matched_keywords.append(category)
                evidence.append(f"Category name '{category}' found")

            # Enhanced subcategory analysis
            for subcategory in subcategories:
                subcategory_lower = subcategory.lower()
                subcategory_score = 0

                # Direct subcategory match
                keyword_matches = content_lower.count(subcategory_lower)
                if keyword_matches > 0:
                    subcategory_score += keyword_matches * 8
                    matched_keywords.append(subcategory)
                    matched_subcategories.append(
                        {
                            "name": subcategory,
                            "matches": keyword_matches,
                            "confidence": min(keyword_matches * 0.25, 1.0),
                        }
                    )
                    evidence.append(
                        f"'{subcategory}' mentioned {keyword_matches} times"
                    )

                # Enhanced key terms matching
                key_terms = self._extract_key_terms(subcategory_lower)
                for term in key_terms:
                    if len(term) > 3 and term in content_lower:
                        subcategory_score += 3
                        if term not in matched_keywords:
                            matched_keywords.append(term)

                category_score += subcategory_score

            if category_score > 0:
                confidence = min(category_score / 40.0, 1.0)

                category_scores[category] = {
                    "score": category_score,
                    "confidence": confidence,
                    "keywords": matched_keywords,
                    "subcategories": matched_subcategories,
                    "evidence": evidence,
                }

        # Build enhanced technology list
        if category_scores:
            sorted_categories = sorted(
                category_scores.items(), key=lambda x: x[1]["score"], reverse=True
            )

            # Include more categories with lower threshold
            for cat, data in sorted_categories:
                if data["confidence"] >= 0.08:
                    classification["technologies"].append(
                        {
                            "category": cat,
                            "confidence": data["confidence"],
                            "subcategories": [
                                sub["name"] for sub in data["subcategories"]
                            ],
                            "evidence": data["evidence"][:3],
                            "keywords": data["keywords"][:5],
                        }
                    )

            # Set overall confidence
            classification["overall_confidence"] = sorted_categories[0][1]["confidence"]

            # Collect all matched keywords
            all_keywords = []
            for cat, data in sorted_categories:
                all_keywords.extend(data["keywords"])
            classification["matched_keywords"] = list(dict.fromkeys(all_keywords))[:20]

        # Enhanced business focus detection
        classification["business_focus"] = self._detect_business_focus(content_lower)

        # Get comprehensive technology stack
        tech_stack_result = self._detect_technology_stack(content_lower)
        classification["technology_stack"] = tech_stack_result.get("simple_list", [])
        classification["comprehensive_technology_stack"] = tech_stack_result

        classification["market_segments"] = self._detect_market_segments(content_lower)

        return classification

    def _extract_key_terms(self, text):
        """Enhanced key terms extraction"""
        common_words = {
            "di",
            "e",
            "il",
            "la",
            "per",
            "con",
            "su",
            "in",
            "a",
            "da",
            "del",
            "della",
            "dei",
            "delle",
            "nel",
            "nella",
            "nei",
            "nelle",
            "and",
            "or",
            "the",
            "of",
            "to",
            "for",
            "with",
            "on",
            "at",
        }
        words = re.findall(r"\b\w+\b", text.lower())
        return [word for word in words if len(word) > 3 and word not in common_words]

    def _detect_business_focus(self, content):
        """Detect primary business focus from content"""
        focus_patterns = [
            (r"specializzat[oi]\s+in\s+([^.]{10,50})", "Specialized in"),
            (r"leader\s+nel\s+([^.]{10,50})", "Leader in"),
            (r"esperti?\s+di\s+([^.]{10,50})", "Expert in"),
            (r"focus\s+su\s+([^.]{10,50})", "Focus on"),
        ]

        for pattern, prefix in focus_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return f"{prefix} {matches[0].strip()}"

        return ""

    def _detect_technology_stack(self, content):
        """Enhanced comprehensive technology stack detection"""
        # Expanded technology categories with scoring
        tech_categories = {
            # Programming Languages & Frameworks
            "programming": {
                "java": ["java", "jvm", "spring", "hibernate"],
                "python": ["python", "django", "flask", "pandas", "numpy"],
                "javascript": ["javascript", "js", "node.js", "nodejs"],
                "react": ["react", "reactjs", "jsx"],
                "angular": ["angular", "angularjs", "typescript"],
                "vue": ["vue", "vuejs", "vue.js"],
                "php": ["php", "laravel", "symfony", "wordpress"],
                "c#": ["c#", "csharp", ".net", "dotnet", "asp.net"],
                "c++": ["c++", "cpp"],
                "go": ["golang", "go"],
                "rust": ["rust"],
                "kotlin": ["kotlin"],
                "swift": ["swift"],
                "ruby": ["ruby", "rails", "ruby on rails"],
            },
            # Cloud & Infrastructure
            "cloud": {
                "aws": ["aws", "amazon web services", "ec2", "s3", "lambda"],
                "azure": ["azure", "microsoft azure"],
                "google cloud": ["google cloud", "gcp", "google cloud platform"],
                "docker": ["docker", "containerization"],
                "kubernetes": ["kubernetes", "k8s", "container orchestration"],
                "terraform": ["terraform", "infrastructure as code"],
                "ansible": ["ansible", "automation"],
                "jenkins": ["jenkins", "ci/cd"],
                "gitlab": ["gitlab", "git"],
                "github": ["github"],
            },
            # Databases
            "databases": {
                "mysql": ["mysql"],
                "postgresql": ["postgresql", "postgres"],
                "mongodb": ["mongodb", "mongo"],
                "redis": ["redis", "cache"],
                "elasticsearch": ["elasticsearch", "elastic", "elk"],
                "oracle": ["oracle", "oracle db"],
                "sql server": ["sql server", "mssql"],
                "cassandra": ["cassandra"],
                "neo4j": ["neo4j", "graph database"],
            },
            # Operating Systems & Virtualization
            "systems": {
                "linux": ["linux", "ubuntu", "centos", "redhat", "debian"],
                "windows": ["windows", "windows server"],
                "vmware": ["vmware", "vsphere", "vcenter"],
                "citrix": ["citrix", "xenapp", "xendesktop"],
                "hyper-v": ["hyper-v", "hyperv"],
            },
            # Networking & Security
            "networking": {
                "cisco": ["cisco", "catalyst", "nexus", "asa"],
                "juniper": ["juniper", "junos"],
                "fortinet": ["fortinet", "fortigate"],
                "palo alto": ["palo alto", "paloalto", "pan-os"],
                "checkpoint": ["checkpoint", "check point"],
                "f5": ["f5", "big-ip"],
                "nginx": ["nginx"],
                "apache": ["apache", "httpd"],
            },
            # Business Applications
            "business": {
                "sap": ["sap", "sap erp", "sap hana"],
                "salesforce": ["salesforce", "sfdc"],
                "microsoft 365": ["microsoft 365", "office 365", "o365"],
                "sharepoint": ["sharepoint"],
                "dynamics": ["dynamics", "dynamics 365"],
                "servicenow": ["servicenow"],
                "jira": ["jira", "atlassian"],
                "confluence": ["confluence"],
            },
            # Data & Analytics
            "analytics": {
                "tableau": ["tableau"],
                "power bi": ["power bi", "powerbi"],
                "qlik": ["qlik", "qlikview", "qliksense"],
                "splunk": ["splunk"],
                "hadoop": ["hadoop", "big data"],
                "spark": ["apache spark", "spark"],
                "kafka": ["kafka", "apache kafka"],
            },
            # AI & Machine Learning
            "ai_ml": {
                "tensorflow": ["tensorflow"],
                "pytorch": ["pytorch"],
                "scikit-learn": ["scikit-learn", "sklearn"],
                "opencv": ["opencv"],
                "nlp": ["nlp", "natural language processing"],
                "machine learning": [
                    "machine learning",
                    "ml",
                    "artificial intelligence",
                    "ai",
                ],
            },
            # Mobile & Frontend
            "mobile": {
                "android": ["android", "kotlin", "java android"],
                "ios": ["ios", "swift", "objective-c"],
                "react native": ["react native"],
                "flutter": ["flutter", "dart"],
                "xamarin": ["xamarin"],
            },
        }

        found_technologies = {}

        # Enhanced detection with context and scoring
        for category, technologies in tech_categories.items():
            for tech_name, keywords in technologies.items():
                score = 0
                matched_keywords = []

                for keyword in keywords:
                    # Case-insensitive search with word boundaries
                    import re

                    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
                    matches = len(re.findall(pattern, content.lower()))

                    if matches > 0:
                        score += matches * (
                            len(keyword) / 5
                        )  # Longer keywords get higher scores
                        matched_keywords.append(keyword)

                if score > 0:
                    found_technologies[tech_name] = {
                        "category": category,
                        "score": score,
                        "keywords": matched_keywords,
                        "confidence": min(score / 10.0, 1.0),
                    }

        # Sort by score and return comprehensive list
        sorted_tech = sorted(
            found_technologies.items(), key=lambda x: x[1]["score"], reverse=True
        )

        # Return detailed technology information
        comprehensive_stack = []
        for tech_name, details in sorted_tech[:25]:  # Up to 25 technologies
            comprehensive_stack.append(
                {
                    "technology": tech_name,
                    "category": details["category"],
                    "confidence": details["confidence"],
                    "keywords_found": details["keywords"][:3],  # Top 3 matched keywords
                    "mentions": int(details["score"]),
                }
            )

        # Also return simple list for backward compatibility
        simple_list = [tech["technology"] for tech in comprehensive_stack[:15]]

        return {
            "detailed_stack": comprehensive_stack,
            "simple_list": simple_list,
            "total_technologies": len(comprehensive_stack),
            "categories_covered": len(
                set(tech["category"] for tech in comprehensive_stack)
            ),
        }

    def _detect_market_segments(self, content):
        """Detect market segments from content"""
        segment_keywords = [
            ("banking", "Banking & Finance"),
            ("healthcare", "Healthcare"),
            ("manufacturing", "Manufacturing"),
            ("retail", "Retail & E-commerce"),
            ("education", "Education"),
            ("government", "Government & Public Sector"),
            ("automotive", "Automotive"),
            ("energy", "Energy & Utilities"),
            ("logistics", "Logistics & Transportation"),
            ("real estate", "Real Estate"),
            ("insurance", "Insurance"),
            ("telecommunications", "Telecommunications"),
            ("media", "Media & Entertainment"),
            ("food", "Food & Beverage"),
            ("pharma", "Pharmaceutical"),
        ]

        found_segments = []
        for keyword, segment in segment_keywords:
            if keyword in content and segment not in found_segments:
                found_segments.append(segment)

        return found_segments[:8]

    def analyze_company_intelligence(self, company_data):
        """Main method to analyze company intelligence"""
        company_name = company_data.get("company_name", "")
        website_url = company_data.get("official_website", "") or company_data.get(
            "website_url", ""
        )

        print(f"\n=== Intelligence Analysis: {company_name} ===")

        if not website_url or website_url.lower() in ["n/a", "none", ""]:
            print(f"  ✗ No website available for {company_name}")
            return {
                "company_name": company_name,
                "website_url": website_url,
                "analysis_status": "no_website",
                "intelligence": {},
                "classification": {},
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

        try:
            # Extract intelligence
            intelligence = self.extract_website_intelligence(website_url, company_name)

            # Content analysis and classification
            full_content = intelligence.get("website_content", "")
            if full_content:
                classification = self.classify_company_content(
                    full_content, company_name
                )
            else:
                classification = {"error": "No content extracted"}

            result = {
                "company_name": company_name,
                "website_url": website_url,
                "analysis_status": "completed",
                "intelligence": intelligence,
                "classification": classification,
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pages_analyzed": len(intelligence.get("analyzed_pages", [])),
                "scraper_version": "4.0",
            }

            print(f"  ✓ Analysis completed for {company_name}")
            return result

        except Exception as e:
            print(f"  ✗ Analysis failed for {company_name}: {e}")
            return {
                "company_name": company_name,
                "website_url": website_url,
                "analysis_status": "error",
                "error": str(e),
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

    def process_companies(self, limit=None):
        """Process companies with intelligence analysis"""
        websites_file = self.config["file_paths"]["websites_output"]
        output_file = self.config["file_paths"]["intelligence_output"]

        print(f"Company Intelligence Scraper v4.0")
        print(f"Reading companies from: {websites_file}")
        print(f"Output file: {output_file}")

        try:
            with open(websites_file, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                companies = list(reader)

            if limit:
                companies = companies[:limit]
                print(f"Processing first {limit} companies (development mode)")

            # Filter companies with websites
            companies_with_websites = [
                company
                for company in companies
                if (company.get("official_website") or company.get("website_url"))
                and (
                    company.get("official_website", "")
                    or company.get("website_url", "")
                ).lower()
                not in ["n/a", "none", "", "null"]
            ]

            print(f"Found {len(companies_with_websites)} companies with websites")

            results = []
            for i, company in enumerate(companies_with_websites, 1):
                print(
                    f"\n[{i}/{len(companies_with_websites)}] Processing: {company.get('company_name', 'Unknown')}"
                )

                result = self.analyze_company_intelligence(company)
                results.append(result)

                # Delay between companies
                if i < len(companies_with_websites):
                    delay = self.config["scraping"]["company_delay"]
                    print(f"  Waiting {delay}s before next company...")
                    time.sleep(delay)

            # Save results to JSON
            with open(output_file, "w", encoding="utf-8") as file:
                json.dump(results, file, indent=2, ensure_ascii=False)

            print(f"\n✓ Intelligence analysis completed!")
            print(f"✓ Results saved to: {output_file}")
            print(f"✓ Processed {len(results)} companies")

            # Summary statistics
            successful = len(
                [r for r in results if r.get("analysis_status") == "completed"]
            )
            with_classification = len(
                [r for r in results if r.get("classification", {}).get("technologies")]
            )

            print(f"✓ Successful analyses: {successful}/{len(results)}")
            print(
                f"✓ With technology classification: {with_classification}/{successful}"
            )

            return results

        except FileNotFoundError:
            print(f"✗ Error: Could not find input file {websites_file}")
            return []
        except Exception as e:
            print(f"✗ Error processing companies: {e}")
            return []

    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("✓ Browser driver closed")


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Company Intelligence Scraper v4.0 - Advanced intelligence gathering with AI classification"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of companies to process (for development/testing)",
    )
    parser.add_argument(
        "--config", default="config.yml", help="Configuration file path"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser with GUI (overrides --headless)",
    )

    args = parser.parse_args()

    # Handle headless mode
    headless_mode = args.headless and not args.no_headless

    print("=" * 60)
    print("Company Intelligence Scraper v4.0")
    print("=" * 60)
    print(f"Configuration: {args.config}")
    print(f"Headless mode: {headless_mode}")
    if args.limit:
        print(f"Development mode: Processing {args.limit} companies")
    print("=" * 60)

    scraper = None
    try:
        scraper = CompanyIntelligenceScraper(
            config_path=args.config, headless=headless_mode
        )
        results = scraper.process_companies(limit=args.limit)

        if results:
            print(f"\n✓ Intelligence scraping completed successfully!")
            print(f"✓ Check the output file for detailed results")
        else:
            print(f"\n✗ No results generated")

    except KeyboardInterrupt:
        print(f"\n⚠ Process interrupted by user")
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
    finally:
        if scraper:
            scraper.cleanup()


if __name__ == "__main__":
    main()
