#!/usr/bin/env python3
"""
Unified Company Data Creator
===========================

Creates a single, well-structured JSON file that consolidates all company
information from multiple sources for better Ollama ingestion and processing.
"""

import json
import csv
import yaml
from pathlib import Path
from typing import Dict, List, Any


class UnifiedCompanyDataCreator:
    """Creates unified company data structure from all pipeline sources"""

    def __init__(self, config_path="config.yml"):
        """Initialize with configuration"""
        self.config = self._load_config(config_path)
        self.unified_data = {}

    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            return self._default_config()

    def _default_config(self):
        """Default configuration"""
        return {
            "file_paths": {
                "chamber_urls_output": "chamber_urls.csv",
                "detailed_data_output": "companies_detailed.csv",
                "websites_output": "company_websites.csv",
                "intelligence_output": "company_intelligence.json",
                "chamber_analysis_output": "chamber_analysis.json",
                "unified_data_output": "companies_unified.json",
            }
        }

    def load_csv_data(self, file_path: str) -> List[Dict]:
        """Load CSV data"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return list(csv.DictReader(file))
        except FileNotFoundError:
            print(f"Warning: {file_path} not found")
            return []

    def load_json_data(self, file_path: str) -> List[Dict]:
        """Load JSON data"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else [data]
        except FileNotFoundError:
            print(f"Warning: {file_path} not found")
            return []

    def format_financial_data(
        self, revenue: str, year: str, employees: str, emp_year: str
    ) -> Dict:
        """Format financial data with proper context"""
        formatted = {}

        if revenue and revenue.isdigit():
            revenue_num = int(revenue)
            formatted["revenue"] = {
                "amount_eur": revenue_num,
                "formatted": f"€{revenue_num:,}".replace(",", "."),
                "year": year or "N/A",
            }

        if employees and employees.isdigit():
            formatted["employees"] = {
                "count": int(employees),
                "year": emp_year or "N/A",
            }

        return formatted

    def format_contact_data(self, detailed_data: Dict, intelligence_data: Dict) -> Dict:
        """Format comprehensive contact information"""
        contacts = {}

        # From detailed data
        if detailed_data.get("address"):
            contacts["registered_address"] = detailed_data["address"]
        if detailed_data.get("pec_email"):
            contacts["pec_email"] = detailed_data["pec_email"]

        # From intelligence data
        if intelligence_data:
            if intelligence_data.get("phone_numbers"):
                contacts["phone_numbers"] = intelligence_data["phone_numbers"]
            if intelligence_data.get("info_emails"):
                contacts["info_emails"] = intelligence_data["info_emails"]
            if intelligence_data.get("addresses"):
                contacts["operational_addresses"] = intelligence_data["addresses"]
            if intelligence_data.get("key_contacts"):
                contacts["key_contacts"] = intelligence_data["key_contacts"]
            if intelligence_data.get("ceo_managing_director"):
                contacts["ceo_managing_director"] = intelligence_data[
                    "ceo_managing_director"
                ]

        return contacts

    def format_certification_data(self, chamber_analysis: Dict) -> Dict:
        """Format comprehensive certification information"""
        if not chamber_analysis:
            return {}

        certifications = {}

        # Direct extraction
        if chamber_analysis.get("direct_extraction"):
            direct = chamber_analysis["direct_extraction"]
            certifications["direct_extraction"] = {
                "soa_attestations": direct.get("soa_attestations", []),
                "quality_certifications": direct.get("quality_certifications", []),
                "environmental_certifications": direct.get(
                    "environmental_certifications", []
                ),
                "safety_certifications": direct.get("safety_certifications", []),
                "environmental_registrations": direct.get(
                    "environmental_registrations", []
                ),
                "technical_authorizations": direct.get("technical_authorizations", []),
            }

        # AI analysis
        if chamber_analysis.get("ai_analysis"):
            ai = chamber_analysis["ai_analysis"]
            certifications["ai_analysis"] = ai.get("certifications", {})

            # Add business activities from AI analysis
            if ai.get("business_activities"):
                certifications["business_activities"] = ai["business_activities"]

            # Add financial data from AI analysis
            if ai.get("financial_data"):
                certifications["chamber_financial_data"] = ai["financial_data"]

        return certifications

    def create_unified_structure(self) -> Dict[str, Any]:
        """Create unified company data structure"""
        print("🔄 Loading data from all sources...")

        # Load all data sources
        chamber_urls = self.load_csv_data(
            self.config["file_paths"]["chamber_urls_output"]
        )
        companies_detailed = self.load_csv_data(
            self.config["file_paths"]["detailed_data_output"]
        )
        company_websites = self.load_csv_data(
            self.config["file_paths"]["websites_output"]
        )
        website_intelligence = self.load_json_data(
            self.config["file_paths"]["intelligence_output"]
        )
        chamber_analysis = self.load_json_data(
            self.config["file_paths"]["chamber_analysis_output"]
        )

        print(f"✓ Loaded {len(chamber_urls)} chamber URLs")
        print(f"✓ Loaded {len(companies_detailed)} detailed company records")
        print(f"✓ Loaded {len(company_websites)} website records")
        print(f"✓ Loaded {len(website_intelligence)} intelligence analyses")
        print(f"✓ Loaded {len(chamber_analysis)} chamber analyses")

        # Create lookup dictionaries
        detailed_lookup = {item["company_name"]: item for item in companies_detailed}
        websites_lookup = {item["company_name"]: item for item in company_websites}
        intelligence_lookup = {
            item["company_name"]: item for item in website_intelligence
        }
        chamber_lookup = {item["company_name"]: item for item in chamber_analysis}

        unified_companies = {}

        # Use detailed companies as the base
        for company in companies_detailed:
            company_name = company["company_name"]

            # Basic company information
            unified_company = {
                "company_name": company_name,
                "legal_form": company.get("legal_form", ""),
                "tax_code": company.get("tax_code", ""),
                "vat_number": company.get("vat_number", ""),
                # Financial information (formatted)
                "financial_data": self.format_financial_data(
                    company.get("latest_revenue", ""),
                    company.get("latest_revenue_year", ""),
                    company.get("latest_employees", ""),
                    company.get("latest_employees_year", ""),
                ),
                # Contact information (comprehensive)
                "contact_information": self.format_contact_data(
                    company, intelligence_lookup.get(company_name, {})
                ),
                # Website information
                "website_data": {},
                # Certifications and chamber analysis
                "certifications": {},
                # Chamber URL
                "chamber_url": "",
                # Metadata
                "data_sources": [],
                "last_updated": "2025-08-28",
            }

            # Add website data
            if company_name in websites_lookup:
                website_data = websites_lookup[company_name]
                confidence_score = website_data.get("confidence_score", "0")
                confidence_score = (
                    int(confidence_score)
                    if confidence_score and confidence_score.isdigit()
                    else 0
                )

                unified_company["website_data"] = {
                    "official_website": website_data.get("official_website", ""),
                    "confidence_score": confidence_score,
                    "validation_status": website_data.get("validation_status", ""),
                    "page_title": website_data.get("page_title", ""),
                }
                unified_company["data_sources"].append("company_websites")

            # Add intelligence data
            if company_name in intelligence_lookup:
                intelligence_data = intelligence_lookup[company_name]
                unified_company["website_intelligence"] = {
                    "analysis_status": intelligence_data.get("analysis_status", ""),
                    "company_references": intelligence_data.get("intelligence", {}).get(
                        "company_references", []
                    ),
                    "classification": intelligence_data.get("intelligence", {}).get(
                        "classification", {}
                    ),
                }
                unified_company["data_sources"].append("website_intelligence")

            # Add certification data
            if company_name in chamber_lookup:
                unified_company["certifications"] = self.format_certification_data(
                    chamber_lookup[company_name]
                )
                unified_company["data_sources"].append("chamber_analysis")

            # Add chamber URL
            chamber_url_data = next(
                (item for item in chamber_urls if item["company_name"] == company_name),
                None,
            )
            if chamber_url_data:
                unified_company["chamber_url"] = chamber_url_data.get("chamber_url", "")
                unified_company["data_sources"].append("chamber_urls")

            # Mark as having detailed data
            unified_company["data_sources"].append("companies_detailed")

            unified_companies[company_name] = unified_company

        return {
            "companies": unified_companies,
            "metadata": {
                "total_companies": len(unified_companies),
                "creation_date": "2025-08-28",
                "data_sources": [
                    "chamber_urls",
                    "companies_detailed",
                    "company_websites",
                    "website_intelligence",
                    "chamber_analysis",
                ],
                "structure_version": "1.0",
            },
        }

    def save_unified_data(self, unified_data: Dict[str, Any]) -> str:
        """Save unified data to JSON file"""
        output_file = self.config["file_paths"]["unified_data_output"]

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(unified_data, file, indent=2, ensure_ascii=False)

        return output_file

    def generate_summary_report(self, unified_data: Dict[str, Any]) -> str:
        """Generate summary report of unified data"""
        companies = unified_data["companies"]

        # Statistics
        total_companies = len(companies)
        with_websites = len(
            [c for c in companies.values() if c["website_data"].get("official_website")]
        )
        with_certifications = len(
            [c for c in companies.values() if c["certifications"]]
        )
        with_intelligence = len(
            [c for c in companies.values() if "website_intelligence" in c]
        )
        with_financial = len([c for c in companies.values() if c["financial_data"]])

        report = f"""
UNIFIED COMPANY DATA SUMMARY REPORT
==================================

Total Companies: {total_companies}

Data Coverage:
• Companies with websites: {with_websites}/{total_companies} ({with_websites/total_companies*100:.1f}%)
• Companies with certifications: {with_certifications}/{total_companies} ({with_certifications/total_companies*100:.1f}%)
• Companies with intelligence data: {with_intelligence}/{total_companies} ({with_intelligence/total_companies*100:.1f}%)
• Companies with financial data: {with_financial}/{total_companies} ({with_financial/total_companies*100:.1f}%)

Sample Company Structure (MET):
"""

        # Add sample structure
        if "MET" in companies:
            met_sample = (
                json.dumps(companies["MET"], indent=2, ensure_ascii=False)[:1000]
                + "..."
            )
            report += met_sample

        return report

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("UNIFIED COMPANY DATA CREATOR")
        print("=" * 60)

        # Create unified structure
        unified_data = self.create_unified_structure()

        # Save to file
        output_file = self.save_unified_data(unified_data)
        print(f"\n✅ Unified data saved to: {output_file}")

        # Generate and save report
        report = self.generate_summary_report(unified_data)
        report_file = "unified_data_report.txt"
        with open(report_file, "w", encoding="utf-8") as file:
            file.write(report)

        print(f"✅ Summary report saved to: {report_file}")
        print(
            f"✅ Total companies processed: {unified_data['metadata']['total_companies']}"
        )

        return output_file


if __name__ == "__main__":
    creator = UnifiedCompanyDataCreator()
    creator.run()
