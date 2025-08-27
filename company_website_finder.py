#!/usr/bin/env python3
"""
Company Website Finder & Validator
=================================

Searches for official company websites using Startpage and validates them using Selenium.
Uses company data and PEC information to find and score potential websites.

Usage: python company_website_finder.py [--limit N] [--config config.yml] [--headless]
"""

import csv
import time
import argparse
import re
import yaml
from urllib.parse import urlparse
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


class CompanyWebsiteFinder:
    def __init__(self, config_path="config.yml", headless=True):
        """Initialize website finder with configuration"""
        self.config = self._load_config(config_path)
        self.headless = headless
        self.driver = None
        self.wait = None
        self.search_session = None
        self._setup_driver()
        self._setup_search_session()

    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Warning: Config file {config_path} not found, using defaults")
            return self._default_config()

    def _default_config(self):
        """Default configuration if file not found"""
        return {
            "data_sources": {
                "search_engine_url": "https://www.startpage.com/sp/search"
            },
            "file_paths": {
                "detailed_data_output": "companies_detailed.csv",
                "websites_output": "company_websites.csv",
            },
            "scraping": {
                "request_delay": 2,
                "validation_delay": 1,
                "company_delay": 3,
                "page_timeout": 15,
                "selenium_timeout": 10,
                "max_candidate_websites": 8,
                "browser_width": 1920,
                "browser_height": 1080,
            },
            "validation": {
                "confidence_threshold": 50,
                "footer_score_cap": 60,
                "name_match_weight": 15,
                "max_name_match_score": 45,
                "tax_code_score": 25,
            },
            "search": {
                "excluded_domains": [
                    "startpage.com",
                    "google.com",
                    "bing.com",
                    "yahoo.com",
                    "facebook.com",
                    "linkedin.com",
                    "twitter.com",
                    "instagram.com",
                    "wikipedia.org",
                    "youtube.com",
                    "amazon.com",
                    "ebay.com",
                    "ufficiocamerale.it",
                    "registroimprese.it",
                    "infocamere.it",
                    "paginegialle.it",
                ]
            },
        }

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

    def _setup_search_session(self):
        """Setup requests session for search"""
        self.search_session = requests.Session()
        self.search_session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

    def search_company_websites(
        self, company_name, tax_code, legal_form, pec_email=None
    ):
        """Search for company websites using multiple strategies"""
        # Clean legal form
        clean_legal_form = (
            legal_form.replace(".", "").replace(",", "").strip() if legal_form else ""
        )

        # Build search queries
        search_queries = [
            (
                f"{company_name} {clean_legal_form} sito ufficiale"
                if clean_legal_form
                else f"{company_name} sito ufficiale"
            ),
            (
                f"{company_name} {clean_legal_form} {tax_code}"
                if clean_legal_form
                else f"{company_name} {tax_code}"
            ),
        ]

        # Add PEC search if available
        if pec_email:
            search_queries.append(
                f"{company_name} {clean_legal_form} {pec_email}"
                if clean_legal_form
                else f"{company_name} {pec_email}"
            )

        found_websites = []

        for query in search_queries:
            try:
                print(f"  Searching: {query}")

                params = {"query": query, "cat": "web", "pl": "opensearch"}

                response = self.search_session.get(
                    self.config["data_sources"]["search_engine_url"],
                    params=params,
                    timeout=self.config["scraping"]["page_timeout"],
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")

                # Extract URLs from search results
                for link in soup.find_all("a", href=True):
                    href = link.get("href")
                    if href and self._is_potential_website(href, company_name):
                        # Extract clean URL
                        if "url=" in href:
                            clean_url = href.split("url=")[1].split("&")[0]
                        elif href.startswith("http"):
                            clean_url = href
                        else:
                            continue

                        # Clean URL and validate
                        clean_url = clean_url.split("?")[0]
                        if self._is_valid_website_url(clean_url):
                            # Normalize to main domain
                            main_domain_url = self._normalize_to_main_domain(clean_url)
                            found_websites.append(main_domain_url)

                time.sleep(self.config["scraping"]["request_delay"])

            except Exception as e:
                print(f"  ✗ Search error for query '{query}': {e}")
                continue

        # Remove duplicates and return top candidates
        unique_websites = list(dict.fromkeys(found_websites))  # Preserve order
        return unique_websites[: self.config["scraping"]["max_candidate_websites"]]

    def _normalize_to_main_domain(self, url):
        """Normalize URL to main domain (remove paths, keep only domain)"""
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}/"
        except:
            return url

    def _is_potential_website(self, url, company_name):
        """Check if URL could be a company website"""
        if not url:
            return False

        # Skip excluded domains
        for domain in self.config["search"]["excluded_domains"]:
            if domain in url.lower():
                return False

        return True

    def _is_valid_website_url(self, url):
        """Basic validation for website URLs"""
        if not url or not url.startswith("http"):
            return False

        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and "." in parsed.netloc)
        except:
            return False

    def validate_website(self, url, company_name, tax_code):
        """Validate if website belongs to the company using Selenium"""
        try:
            print(f"  Validating: {url}")
            self.driver.get(url)

            # Wait for page to load
            time.sleep(3)

            # Get page content
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                page_title = self.driver.title.lower()

                # Get footer content (most important for validation)
                footer_text = ""
                try:
                    footer_elements = self.driver.find_elements(
                        By.XPATH,
                        "//footer | //*[contains(@class, 'footer')] | //*[contains(@id, 'footer')]",
                    )
                    for footer in footer_elements:
                        footer_text += " " + footer.text.lower()
                except:
                    pass

            except Exception as e:
                print(f"  ✗ Error getting page content: {e}")
                return self._create_validation_result(url, False, "content_error", {})

            # Calculate validation score
            validation_score = 0
            validation_hints = {}

            # Priority 1: Footer validation (most reliable)
            footer_score = self._validate_footer_details(
                footer_text, company_name, tax_code
            )
            validation_score += footer_score
            if footer_score > 0:
                validation_hints["footer_validation"] = footer_score

            # Priority 2: Company name matches
            company_variations = self._generate_company_variations(company_name)
            name_matches = 0
            for variation in company_variations:
                if variation in page_text or variation in page_title:
                    name_matches += 1

            if name_matches > 0:
                validation_score += min(
                    name_matches * self.config["validation"]["name_match_weight"],
                    self.config["validation"]["max_name_match_score"],
                )
                validation_hints["name_matches"] = name_matches

            # Priority 3: Tax code validation
            if tax_code in page_text:
                validation_score += self.config["validation"]["tax_code_score"]
                validation_hints["tax_code_found"] = True

            # Determine validation result
            is_valid = (
                validation_score >= self.config["validation"]["confidence_threshold"]
            )
            confidence = min(validation_score, 100)

            validation_hints["confidence_score"] = confidence
            validation_hints["page_title"] = self.driver.title[:100]

            return self._create_validation_result(
                url, is_valid, "validated", validation_hints
            )

        except TimeoutException:
            return self._create_validation_result(url, False, "timeout", {})
        except Exception as e:
            print(f"  ✗ Validation error for {url}: {e}")
            return self._create_validation_result(
                url, False, "error", {"error": str(e)}
            )

    def _validate_footer_details(self, footer_text, company_name, tax_code):
        """Validate footer for official company registration details"""
        if not footer_text:
            return 0

        score = 0

        # Check for company name in footer
        company_variations = self._generate_company_variations(company_name)
        for variation in company_variations:
            if variation in footer_text:
                score += 20
                break

        # Check for tax code in footer
        if tax_code in footer_text:
            score += 30

        # Check for VAT patterns in footer
        vat_patterns = [
            r"partita\s+iva[:\s]*\d{11}",
            r"p\.?\s*iva[:\s]*\d{11}",
        ]
        for pattern in vat_patterns:
            if re.search(pattern, footer_text):
                score += 25
                break

        return min(score, self.config["validation"]["footer_score_cap"])

    def _generate_company_variations(self, company_name):
        """Generate variations of company name for matching"""
        variations = set()

        # Original name
        variations.add(company_name.lower())

        # Remove legal forms
        legal_forms = [
            "spa",
            "s.p.a.",
            "srl",
            "s.r.l.",
            "s.a.s.",
            "sas",
            "snc",
            "s.n.c.",
        ]
        clean_name = company_name.lower()
        for form in legal_forms:
            clean_name = clean_name.replace(form, "").strip()
        variations.add(clean_name)

        # Remove punctuation
        clean_punct = re.sub(r"[^\w\s]", " ", clean_name).strip()
        variations.add(clean_punct)

        # Split into words and use main words
        words = clean_punct.split()
        if len(words) > 1:
            variations.add(words[0])
            if len(words) > 1:
                variations.add(f"{words[0]} {words[1]}")

        return [v for v in variations if len(v) > 2]

    def _create_validation_result(self, url, is_valid, status, hints):
        """Create standardized validation result"""
        return {"url": url, "is_valid": is_valid, "status": status, "hints": hints}

    def process_companies(self, input_file=None, limit=None):
        """Process companies to find and validate their websites"""
        if input_file is None:
            input_file = self.config["file_paths"]["detailed_data_output"]

        print(f"Reading company data from {input_file}")

        try:
            with open(input_file, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                companies = list(reader)
        except FileNotFoundError:
            print(f"Error: {input_file} not found")
            return []

        if limit:
            companies = companies[:limit]

        print(f"Processing {len(companies)} companies...")

        results = []
        for i, company in enumerate(companies, 1):
            company_name = company["company_name"]
            tax_code = company["tax_code"]
            legal_form = company["legal_form"]
            pec_email = company.get("pec_email")

            print(f"\n[{i}/{len(companies)}] {company_name}")

            # Search for websites
            candidate_websites = self.search_company_websites(
                company_name, tax_code, legal_form, pec_email
            )

            if not candidate_websites:
                result = {
                    "company_name": company_name,
                    "legal_form": legal_form,
                    "tax_code": tax_code,
                    "official_website": None,
                    "confidence_score": 0,
                    "validation_status": "no_websites_found",
                    "page_title": "",
                }
                results.append(result)
                print("  ✗ No websites found")
                continue

            print(f"  Found {len(candidate_websites)} candidate websites")

            # Validate each candidate
            best_website = None
            best_score = 0
            best_validation = None

            for url in candidate_websites:
                validation = self.validate_website(url, company_name, tax_code)

                if validation["is_valid"]:
                    score = validation["hints"].get("confidence_score", 0)
                    if score > best_score:
                        best_score = score
                        best_website = url
                        best_validation = validation
                    print(f"  ✓ {url} (score: {score})")
                else:
                    print(f"  ✗ {url} (invalid)")

                time.sleep(self.config["scraping"]["validation_delay"])

            # Create result
            if best_website:
                result = {
                    "company_name": company_name,
                    "legal_form": legal_form,
                    "tax_code": tax_code,
                    "official_website": best_website,
                    "confidence_score": best_score,
                    "validation_status": "validated",
                    "page_title": best_validation["hints"].get("page_title", ""),
                }
                print(f"  ✓ Best website: {best_website} (score: {best_score})")
            else:
                result = {
                    "company_name": company_name,
                    "legal_form": legal_form,
                    "tax_code": tax_code,
                    "official_website": (
                        candidate_websites[0] if candidate_websites else None
                    ),
                    "confidence_score": 0,
                    "validation_status": "validation_failed",
                    "page_title": "",
                }
                print("  ✗ No valid websites found")

            results.append(result)

            # Be respectful with requests
            time.sleep(self.config["scraping"]["company_delay"])

        return results

    def save_results(self, results, output_file=None):
        """Save results to CSV file"""
        if output_file is None:
            output_file = self.config["file_paths"]["websites_output"]

        if not results:
            print("No results to save")
            return

        fieldnames = [
            "company_name",
            "legal_form",
            "tax_code",
            "official_website",
            "confidence_score",
            "validation_status",
            "page_title",
        ]

        try:
            with open(output_file, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

            print(f"\nResults saved to {output_file}")

            # Print summary
            valid_count = sum(
                1
                for r in results
                if r["confidence_score"]
                >= self.config["validation"]["confidence_threshold"]
            )
            print(
                f"Summary: {valid_count}/{len(results)} websites validated successfully"
            )

        except Exception as e:
            print(f"Error saving results: {e}")

    def close(self):
        """Close the WebDriver and session"""
        if self.driver:
            self.driver.quit()
        if self.search_session:
            self.search_session.close()


def main():
    parser = argparse.ArgumentParser(description="Company Website Finder & Validator")
    parser.add_argument(
        "--limit", type=int, help="Limit number of companies to process"
    )
    parser.add_argument(
        "--config", default="config.yml", help="Configuration file path"
    )
    parser.add_argument("--input", help="Input CSV file (overrides config)")
    parser.add_argument("--output", help="Output CSV file (overrides config)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    args = parser.parse_args()

    print("Company Website Finder & Validator")
    print("=" * 40)
    print(f"Headless mode: {args.headless}")

    finder = CompanyWebsiteFinder(args.config, args.headless)

    try:
        # Process companies
        results = finder.process_companies(args.input, args.limit)

        # Save results
        finder.save_results(results, args.output)

        print("\nWebsite finding completed!")

    except KeyboardInterrupt:
        print("\nWebsite finding interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        finder.close()


if __name__ == "__main__":
    main()
