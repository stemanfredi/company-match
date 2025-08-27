#!/usr/bin/env python3
"""
Chamber of Commerce URL Scraper
===============================

Finds URLs for companies on the Italian Chamber of Commerce website (ufficiocamerale.it)
using requests and BeautifulSoup for headless/containerized compatibility.

Usage: python chamber_url_scraper.py [--limit N] [--config config.yml]
"""

import csv
import time
import argparse
import re
import yaml
from pathlib import Path
import requests
from bs4 import BeautifulSoup


class ChamberURLScraper:
    def __init__(self, config_path="config.yml"):
        """Initialize scraper with configuration"""
        self.config = self._load_config(config_path)
        self.session = self._setup_session()

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
                "chamber_of_commerce_url": "https://www.ufficiocamerale.it"
            },
            "file_paths": {
                "input_file": "companies_base.csv",
                "chamber_urls_output": "chamber_urls.csv",
            },
            "scraping": {"request_delay": 2, "page_timeout": 15, "max_retries": 3},
        }

    def _setup_session(self):
        """Setup requests session with headers"""
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        return session

    def search_company_url(self, company_name, tax_code, max_retries=None):
        """Search for company URL on Chamber of Commerce website using Startpage"""
        if max_retries is None:
            max_retries = self.config["scraping"]["max_retries"]

        # Clean company name for search
        clean_name = re.sub(r"[^\w\s-]", "", company_name.lower())

        # Build search query (using www.ufficiocamerale.it as in original)
        search_query = f"site:www.ufficiocamerale.it {clean_name} {tax_code}"

        # Use search engine URL from config
        search_engine_url = self.config["data_sources"]["search_engine_url"]

        params = {"query": search_query, "cat": "web", "pl": "opensearch"}

        for attempt in range(max_retries):
            try:
                print(f"  Searching: {search_query} (attempt {attempt + 1})")

                response = self.session.get(
                    search_engine_url,
                    params=params,
                    timeout=self.config["scraping"]["page_timeout"],
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")

                # Look for search results containing ufficiocamerale.it URLs
                results = []

                # Find all links in search results
                for link in soup.find_all("a", href=True):
                    href = link.get("href")
                    if href and "ufficiocamerale.it" in href:
                        # Skip internal Startpage links
                        if href.startswith("/sp/"):
                            continue

                        # Extract actual URL if it's wrapped
                        if "url=" in href:
                            actual_url = href.split("url=")[1].split("&")[0]
                            # Clean URL by removing query parameters
                            clean_url = actual_url.split("?")[0]
                            results.append(clean_url)
                        elif href.startswith("http") and "ufficiocamerale.it" in href:
                            # Clean URL by removing query parameters
                            clean_url = href.split("?")[0]
                            results.append(clean_url)

                # Remove duplicates and return first result
                unique_results = list(set(results))
                if unique_results:
                    print(f"  ✓ Found: {unique_results[0]}")
                    return unique_results[0]

                time.sleep(self.config["scraping"]["request_delay"])

            except Exception as e:
                print(f"  ✗ Search error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.config["scraping"]["request_delay"] * 2)
                continue

        print(f"  ✗ No URL found after {max_retries} attempts")
        return None

    def _is_valid_chamber_url(self, url, company_name):
        """Validate if URL is a valid Chamber of Commerce company page"""
        if not url or not url.startswith("http"):
            return False

        # Must be from Chamber of Commerce site
        if self.config["data_sources"]["chamber_of_commerce_url"] not in url:
            return False

        # Should contain company-related path indicators
        company_indicators = ["impresa", "azienda", "company", "dettaglio"]
        url_lower = url.lower()

        return any(indicator in url_lower for indicator in company_indicators)

    def process_companies(self, input_file=None, limit=None):
        """Process companies from CSV file to find their Chamber URLs"""
        if input_file is None:
            input_file = self.config["file_paths"]["input_file"]

        print(f"Reading companies from {input_file}")

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

            print(f"\n[{i}/{len(companies)}] {company_name}")

            # Search for Chamber URL
            chamber_url = self.search_company_url(company_name, tax_code)

            result = {
                "company_name": company_name,
                "legal_form": legal_form,
                "tax_code": tax_code,
                "chamber_url": chamber_url,
            }
            results.append(result)

            # Be respectful with requests
            time.sleep(self.config["scraping"]["request_delay"])

        return results

    def save_results(self, results, output_file=None):
        """Save results to CSV file"""
        if output_file is None:
            output_file = self.config["file_paths"]["chamber_urls_output"]

        if not results:
            print("No results to save")
            return

        fieldnames = ["company_name", "legal_form", "tax_code", "chamber_url"]

        try:
            with open(output_file, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

            print(f"\nResults saved to {output_file}")

            # Print summary
            found_count = sum(1 for r in results if r["chamber_url"])
            print(f"Summary: {found_count}/{len(results)} URLs found")

        except Exception as e:
            print(f"Error saving results: {e}")


def main():
    parser = argparse.ArgumentParser(description="Chamber of Commerce URL Scraper")
    parser.add_argument(
        "--limit", type=int, help="Limit number of companies to process"
    )
    parser.add_argument(
        "--config", default="config.yml", help="Configuration file path"
    )
    parser.add_argument("--input", help="Input CSV file (overrides config)")
    parser.add_argument("--output", help="Output CSV file (overrides config)")

    args = parser.parse_args()

    print("Chamber of Commerce URL Scraper")
    print("=" * 40)

    scraper = ChamberURLScraper(args.config)

    try:
        # Process companies
        results = scraper.process_companies(args.input, args.limit)

        # Save results
        scraper.save_results(results, args.output)

        print("\nURL scraping completed!")

    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
