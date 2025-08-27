#!/usr/bin/env python3
"""
Company Data Scraper
===================

Extracts detailed company information from Chamber of Commerce pages using Selenium.
Scrapes: VAT number, address, PEC email, revenue, employee data.

Usage: python company_data_scraper.py [--limit N] [--config config.yml] [--headless]
"""

import csv
import time
import argparse
import re
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager


class CompanyDataScraper:
    def __init__(self, config_path="config.yml", headless=True):
        """Initialize scraper with configuration"""
        self.config = self._load_config(config_path)
        self.headless = headless
        self.driver = None
        self.wait = None
        self._setup_driver()

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
            "file_paths": {
                "chamber_urls_output": "chamber_urls.csv",
                "detailed_data_output": "companies_detailed.csv",
            },
            "scraping": {
                "selenium_timeout": 10,
                "request_delay": 2,
                "browser_width": 1920,
                "browser_height": 1080,
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

    def extract_company_details(self, url):
        """Extract detailed company information from Chamber page"""
        details = {
            "vat_number": None,
            "address": None,
            "pec_email": None,
            "latest_revenue": None,
            "latest_revenue_year": None,
            "latest_employees": None,
            "latest_employees_year": None,
        }

        try:
            print(f"  Extracting data from: {url}")
            self.driver.get(url)

            # Wait for page to load
            time.sleep(3)

            # Get page text for pattern matching
            page_text = self.driver.find_element(By.TAG_NAME, "body").text

            # Extract VAT number (Partita IVA)
            vat_patterns = [
                r"partita\s+iva[:\s]*(\d{11})",
                r"p\.?\s*iva[:\s]*(\d{11})",
                r"codice\s+fiscale[:\s]*(\d{11})",
            ]
            for pattern in vat_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    details["vat_number"] = match.group(1)
                    break

            # Extract address - improved patterns to avoid form text
            address_patterns = [
                r"sede\s+legale[:\s]*([A-Z][^.\n]*(?:via|viale|piazza|corso|largo)[^.\n]*\d+[^.\n]*)",
                r"indirizzo[:\s]*([A-Z][^.\n]*(?:via|viale|piazza|corso|largo)[^.\n]*\d+[^.\n]*)",
                r"(via|viale|piazza|corso|largo)\s+([A-Z][^,\n]*\d+[^,\n]*(?:,\s*\d{5}[^,\n]*)?)",
                r"sede[:\s]*([A-Z][^.\n]*(?:via|viale|piazza|corso|largo)[^.\n]*)",
            ]
            for pattern in address_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    if len(match.groups()) > 1:
                        address = f"{match.group(1)} {match.group(2)}".strip()
                    else:
                        address = match.group(1).strip()

                    # Filter out form text and very short matches
                    if (
                        len(address) > 15
                        and "form" not in address.lower()
                        and "procedi" not in address.lower()
                        and "compilato" not in address.lower()
                    ):
                        details["address"] = address[:200]  # Limit length
                        break

            # Extract PEC email
            pec_patterns = [
                r"pec[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
                r"posta\s+elettronica\s+certificata[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
                r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]*pec[a-zA-Z0-9.-]*\.[a-zA-Z]{2,})",
            ]
            for pattern in pec_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    details["pec_email"] = match.group(1).lower()
                    break

            # Extract revenue data
            revenue_patterns = [
                r"fatturato[:\s]*€?\s*([0-9.,]+).*?(\d{4})",
                r"ricavi[:\s]*€?\s*([0-9.,]+).*?(\d{4})",
                r"volume\s+d'affari[:\s]*€?\s*([0-9.,]+).*?(\d{4})",
            ]
            for pattern in revenue_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    revenue_str = match.group(1).replace(",", "").replace(".", "")
                    try:
                        details["latest_revenue"] = int(revenue_str)
                        details["latest_revenue_year"] = int(match.group(2))
                        break
                    except ValueError:
                        continue

            # Extract employee data
            employee_patterns = [
                r"dipendenti[:\s]*(\d+).*?(\d{4})",
                r"addetti[:\s]*(\d+).*?(\d{4})",
                r"occupati[:\s]*(\d+).*?(\d{4})",
            ]
            for pattern in employee_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    try:
                        details["latest_employees"] = int(match.group(1))
                        details["latest_employees_year"] = int(match.group(2))
                        break
                    except ValueError:
                        continue

            # Create extraction summary for console output
            extracted_fields = []
            if details["vat_number"]:
                extracted_fields.append(f"VAT={details['vat_number']}")
            if details["address"]:
                extracted_fields.append(f"Address={details['address'][:50]}...")
            if details["pec_email"]:
                extracted_fields.append(f"PEC={details['pec_email']}")
            if details["latest_revenue"]:
                extracted_fields.append(
                    f"Revenue={details['latest_revenue']} ({details['latest_revenue_year']})"
                )
            if details["latest_employees"]:
                extracted_fields.append(
                    f"Employees={details['latest_employees']} ({details['latest_employees_year']})"
                )

            if extracted_fields:
                print(f"  ✓ Extracted: {', '.join(extracted_fields)}")
            else:
                print("  ✗ No data extracted")
            return details

        except Exception as e:
            print(f"  ✗ Extraction error: {e}")
            return details

    def process_companies(self, input_file=None, limit=None):
        """Process companies from Chamber URLs CSV to extract detailed data"""
        if input_file is None:
            input_file = self.config["file_paths"]["chamber_urls_output"]

        print(f"Reading Chamber URLs from {input_file}")

        try:
            with open(input_file, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                companies = list(reader)
        except FileNotFoundError:
            print(f"Error: {input_file} not found")
            return []

        # Filter only companies with URLs
        companies = [c for c in companies if c.get("chamber_url")]

        if limit:
            companies = companies[:limit]

        print(f"Processing {len(companies)} companies with Chamber URLs...")

        results = []
        for i, company in enumerate(companies, 1):
            company_name = company["company_name"]
            tax_code = company["tax_code"]
            legal_form = company["legal_form"]
            chamber_url = company["chamber_url"]

            print(f"\n[{i}/{len(companies)}] {company_name}")

            # Extract detailed data
            details = self.extract_company_details(chamber_url)

            # Combine base data with extracted details (no chamber_url in detailed CSV)
            result = {
                "company_name": company_name,
                "legal_form": legal_form,
                "tax_code": tax_code,
                **details,
            }
            results.append(result)

            # Be respectful with requests
            time.sleep(self.config["scraping"]["request_delay"])

        return results

    def save_results(self, results, output_file=None):
        """Save results to CSV file"""
        if output_file is None:
            output_file = self.config["file_paths"]["detailed_data_output"]

        if not results:
            print("No results to save")
            return

        fieldnames = [
            "company_name",
            "legal_form",
            "tax_code",
            "vat_number",
            "address",
            "pec_email",
            "latest_revenue",
            "latest_revenue_year",
            "latest_employees",
            "latest_employees_year",
        ]

        try:
            with open(output_file, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

            print(f"\nResults saved to {output_file}")

            # Print summary
            vat_count = sum(1 for r in results if r["vat_number"])
            address_count = sum(1 for r in results if r["address"])
            pec_count = sum(1 for r in results if r["pec_email"])
            revenue_count = sum(1 for r in results if r["latest_revenue"])
            employee_count = sum(1 for r in results if r["latest_employees"])

            print(f"Summary:")
            print(f"  VAT numbers found: {vat_count}/{len(results)}")
            print(f"  Addresses found: {address_count}/{len(results)}")
            print(f"  PEC emails found: {pec_count}/{len(results)}")
            print(f"  Revenue data found: {revenue_count}/{len(results)}")
            print(f"  Employee data found: {employee_count}/{len(results)}")

        except Exception as e:
            print(f"Error saving results: {e}")

    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Company Data Scraper")
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

    print("Company Data Scraper")
    print("=" * 40)
    print(f"Headless mode: {args.headless}")

    scraper = CompanyDataScraper(args.config, args.headless)

    try:
        # Process companies
        results = scraper.process_companies(args.input, args.limit)

        # Save results
        scraper.save_results(results, args.output)

        print("\nData scraping completed!")

    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
