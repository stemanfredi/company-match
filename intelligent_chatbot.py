#!/usr/bin/env python3
"""
Intelligent Chatbot Interface - Step 6
=====================================

CLI chatbot that leverages all collected data from steps 1-5 using Ollama.
Provides intelligent access to company information, website intelligence,
and chamber of commerce certifications through natural language queries.

Features:
- Natural language query processing
- Access to all pipeline data (steps 1-5)
- Dynamic information retrieval
- Graceful Ctrl+C exit handling
- Context-aware responses
- Targeted scraping triggers when information is missing

Usage: python intelligent_chatbot.py [--config config.yml]
"""

import json
import csv
import yaml
import argparse
import signal
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
import subprocess
import time


class IntelligentChatbot:
    """
    Intelligent chatbot that provides access to all company data through
    natural language queries using Ollama for query analysis and response generation.
    """

    def __init__(self, config_path="config.yml"):
        """Initialize the chatbot with configuration and data"""
        self.config = self._load_config(config_path)
        self.running = True
        self.data_cache = {}
        self._setup_signal_handlers()
        self._load_all_data()

    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                if "chatbot" not in config:
                    config["chatbot"] = self._default_chatbot_config()
                return config
        except FileNotFoundError:
            print(f"Warning: Config file {config_path} not found, using defaults")
            return self._default_config()

    def _default_config(self):
        """Default configuration if file not found"""
        return {
            "file_paths": {
                "chamber_urls_output": "chamber_urls.csv",
                "detailed_data_output": "companies_detailed.csv",
                "websites_output": "company_websites.csv",
                "intelligence_output": "company_intelligence.json",
                "chamber_analysis_output": "chamber_analysis.json",
            },
            "chatbot": self._default_chatbot_config(),
            "intelligence": {
                "ollama_endpoint": "http://ollama.lan:11434/api/generate",
                "ollama_model": "gemma3:12b",
                "ollama_stream": False,
                "ollama_temperature": 0.7,
                "ollama_timeout": 30,
            },
        }

    def _default_chatbot_config(self):
        """Default chatbot configuration"""
        return {
            "max_context_length": 6000,
            "response_max_length": 1000,
            "enable_dynamic_scraping": True,
            "conversation_history_limit": 10,
        }

    def _setup_signal_handlers(self):
        """Setup graceful exit on Ctrl+C"""

        def signal_handler(sig, frame):
            print("\n\n👋 Goodbye! Thanks for using the Company Intelligence Chatbot.")
            self.running = False
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

    def _load_all_data(self):
        """Load unified company data"""
        print("🔄 Loading unified company data...")

        # Load unified data structure
        unified_data_path = self.config["file_paths"].get(
            "unified_data_output", "unified_company_data.json"
        )
        unified_data_raw = self._load_json_data(unified_data_path)

        # Handle different data structures
        if isinstance(unified_data_raw, list) and len(unified_data_raw) > 0:
            # If it's a list, check if first item has 'companies' key
            if (
                isinstance(unified_data_raw[0], dict)
                and "companies" in unified_data_raw[0]
            ):
                companies_dict = unified_data_raw[0]["companies"]
            else:
                # It's a direct list of companies
                companies_dict = {
                    company.get("company_name", f"company_{i}"): company
                    for i, company in enumerate(unified_data_raw)
                }
        elif isinstance(unified_data_raw, dict) and "companies" in unified_data_raw:
            # It's a dict with companies key
            companies_dict = unified_data_raw["companies"]
        else:
            # Fallback - treat as single company or empty
            companies_dict = {}

        # Convert to list for compatibility
        self.unified_data = list(companies_dict.values())

        # Convert to dictionary for fast lookup
        self.company_lookup = {}
        for company in self.unified_data:
            company_name = company.get("company_name", "").strip()
            tax_code = company.get("tax_code", "").strip()

            if company_name:
                self.company_lookup[company_name.upper()] = company
            if tax_code:
                self.company_lookup[tax_code] = company

        # Print data summary
        self._print_unified_data_summary()

    def _print_unified_data_summary(self):
        """Print summary of unified data"""
        print("\n📊 Unified Data Summary:")
        print(f"  • Total companies: {len(self.unified_data)}")
        print(f"  • Company lookup entries: {len(self.company_lookup)}")

        # Count companies with different data types
        with_websites = sum(
            1
            for c in self.unified_data
            if c.get("website_data", {}).get("official_website")
        )
        with_intelligence = sum(
            1
            for c in self.unified_data
            if c.get("website_intelligence", {}).get("classification")
        )
        with_certifications = sum(
            1
            for c in self.unified_data
            if c.get("certifications", {}).get("direct_extraction")
        )
        with_financial = sum(
            1 for c in self.unified_data if c.get("financial_data", {}).get("revenue")
        )

        print(f"  • Companies with websites: {with_websites}")
        print(f"  • Companies with intelligence: {with_intelligence}")
        print(f"  • Companies with certifications: {with_certifications}")
        print(f"  • Companies with financial data: {with_financial}")

    def _load_csv_data(self, file_path: str) -> List[Dict]:
        """Load CSV data into list of dictionaries"""
        try:
            data = []
            with open(file_path, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                data = list(reader)
            return data
        except FileNotFoundError:
            return []

    def _load_json_data(self, file_path: str) -> List[Dict]:
        """Load JSON data"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else [data]
        except FileNotFoundError:
            return []

    def _create_lookup_indices(self):
        """Create lookup indices for fast company matching"""
        self.company_index = {}

        # Index by company name and tax code
        for dataset_name, dataset in self.data_cache.items():
            if not dataset:
                continue

            for item in dataset:
                # Get company identifiers
                company_name = item.get("company_name", "").strip()
                tax_code = item.get("tax_code", "").strip()

                if company_name:
                    key = company_name.upper()
                    if key not in self.company_index:
                        self.company_index[key] = {}
                    self.company_index[key][dataset_name] = item

                if tax_code:
                    if tax_code not in self.company_index:
                        self.company_index[tax_code] = {}
                    self.company_index[tax_code][dataset_name] = item

    def _print_data_summary(self):
        """Print summary of loaded data"""
        print("\n📊 Data Summary:")
        print(f"  • Chamber URLs: {len(self.data_cache['chamber_urls'])} companies")
        print(
            f"  • Detailed Data: {len(self.data_cache['companies_detailed'])} companies"
        )
        print(
            f"  • Company Websites: {len(self.data_cache['company_websites'])} companies"
        )
        print(
            f"  • Website Intelligence: {len(self.data_cache['website_intelligence'])} analyses"
        )
        print(
            f"  • Chamber Analysis: {len(self.data_cache['chamber_analysis'])} documents"
        )
        print(f"  • Company Index: {len(self.company_index)} unique identifiers")

    def analyze_query_ollama(self, query: str) -> Dict[str, Any]:
        """Analyze user query using Ollama to understand intent and extract parameters"""
        try:
            prompt = f"""Analizza la seguente domanda dell'utente su aziende italiane e determina:

DOMANDA UTENTE: "{query}"

ISTRUZIONI:
1. Identifica l'intento della domanda (ricerca azienda, informazioni specifiche, confronto, etc.)
2. Estrai nomi di aziende, codici fiscali, o altri identificatori
3. Determina che tipo di informazioni sono richieste
4. Suggerisci quale dataset consultare

IMPORTANTE: Se la domanda riguarda settori, tecnologie, attività, competenze, servizi o ambiti di business, usa "technologies" come information_type.

DATASET DISPONIBILI:
- chamber_urls: URL delle pagine camerali
- companies_detailed: Dati dettagliati aziende (indirizzo, PEC, fatturato, dipendenti)
- company_websites: Siti web ufficiali delle aziende
- website_intelligence: Analisi intelligente dei siti web (contatti, tecnologie, classificazione)
- chamber_analysis: Analisi documenti Camera di Commercio (certificazioni, abilitazioni)

FORMATO RISPOSTA JSON:
{{
    "intent": "search_company|get_info|compare|list|other",
    "company_identifiers": ["nome1", "codice_fiscale1"],
    "information_type": ["contacts", "certifications", "technologies", "financial", "websites", "all"],
    "datasets_needed": ["dataset1", "dataset2"],
    "search_terms": ["termine1", "termine2"],
    "response_type": "detailed|summary|list",
    "confidence": 0.85
}}

ESEMPI:
- "in quali settori opera COMPANY_X" → information_type: ["technologies"]
- "che tecnologie usa COMPANY_Y" → information_type: ["technologies"]
- "quali servizi offre COMPANY_Z" → information_type: ["technologies"]

Rispondi SOLO con JSON valido:"""

            ollama_request = {
                "model": self.config["intelligence"]["ollama_model"],
                "prompt": prompt,
                "stream": self.config["intelligence"]["ollama_stream"],
                "options": {
                    "temperature": self.config["intelligence"]["ollama_temperature"],
                },
            }

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
                    analysis = json.loads(json_str)
                    return analysis

        except Exception as e:
            print(f"⚠️ Query analysis error: {e}")

        # Enhanced fallback analysis with better keyword detection
        info_types = ["all"]
        datasets_needed = ["companies_detailed", "website_intelligence"]

        # Technology/Sector queries - MOVED TO TOP for priority
        if any(
            keyword in query.lower()
            for keyword in [
                "settori",
                "settore",
                "tecnologie",
                "tecnologia",
                "opera",
                "attività",
                "business",
                "servizi",
                "competenze",
                "specializzazioni",
                "campo",
                "ambito",
            ]
        ):
            info_types = ["technologies"]
            datasets_needed = [
                "website_intelligence",
                "chamber_analysis",
                "companies_detailed",
            ]

        # Certification queries
        elif any(
            keyword in query.lower()
            for keyword in [
                "certificazioni",
                "certificazione",
                "soa",
                "iso",
                "attestazioni",
            ]
        ):
            info_types = ["certifications"]
            datasets_needed = ["chamber_analysis", "companies_detailed"]

        # Contact queries
        elif any(
            keyword in query.lower()
            for keyword in [
                "contatti",
                "contatto",
                "telefono",
                "email",
                "indirizzo",
                "sede",
                "pec",
            ]
        ):
            info_types = ["contacts"]
            datasets_needed = ["companies_detailed", "website_intelligence"]

        # Financial queries
        elif any(
            keyword in query.lower()
            for keyword in ["fatturato", "ricavi", "dipendenti", "capitale", "bilancio"]
        ):
            info_types = ["financial"]
            datasets_needed = ["companies_detailed"]

        # Website queries
        elif any(keyword in query.lower() for keyword in ["sito", "website", "web"]):
            info_types = ["websites"]
            datasets_needed = ["company_websites"]

        # Check if this is a cross-company technology search query
        if any(
            phrase in query.lower()
            for phrase in [
                "quali aziende",
                "che aziende",
                "aziende che",
                "chi ha competenze",
                "chi opera",
                "aziende con",
                "aziende specializzate",
            ]
        ):
            return {
                "intent": "search_by_technology",
                "company_identifiers": [],
                "information_type": ["technologies"],
                "datasets_needed": ["website_intelligence", "chamber_analysis"],
                "search_terms": [query],
                "response_type": "list",
                "confidence": 0.7,
            }

        return {
            "intent": "search_company",
            "company_identifiers": [query],
            "information_type": info_types,
            "datasets_needed": datasets_needed,
            "search_terms": [query],
            "response_type": "detailed",
            "confidence": 0.5,
        }

    def search_companies(
        self, identifiers: List[str], search_terms: List[str]
    ) -> Dict[str, Any]:
        """Search for companies using identifiers and terms with improved matching"""
        found_companies = {}

        # Direct lookup by identifiers (exact match)
        for identifier in identifiers:
            key = identifier.upper().strip()
            if key in self.company_lookup:
                found_companies[key] = self.company_lookup[key]

        # If no exact matches, try fuzzy search
        if not found_companies:
            # Try partial matches with different strategies
            for search_term in search_terms:
                search_term_clean = search_term.upper().strip()

                # Skip very short search terms
                if len(search_term_clean) < 3:
                    continue

                # Strategy 1: Contains search term
                for company_key, company_data in self.company_lookup.items():
                    if search_term_clean in company_key:
                        found_companies[company_key] = company_data

                # Strategy 2: Search term contains company name (for abbreviations)
                if not found_companies:
                    for company_key, company_data in self.company_lookup.items():
                        # Extract main company name (before SPA, SRL, etc.)
                        company_main = (
                            company_key.split()[0]
                            if company_key.split()
                            else company_key
                        )
                        if len(company_main) >= 3 and company_main in search_term_clean:
                            found_companies[company_key] = company_data

                # Strategy 3: Word-by-word matching for multi-word searches
                if not found_companies and len(search_term_clean.split()) > 1:
                    search_words = search_term_clean.split()
                    for company_key, company_data in self.company_lookup.items():
                        company_words = company_key.split()
                        # Check if all search words are found in company name
                        if all(
                            any(
                                search_word in company_word
                                for company_word in company_words
                            )
                            for search_word in search_words
                        ):
                            found_companies[company_key] = company_data

        return found_companies

    def search_companies_by_technology(self, query: str) -> Dict[str, Any]:
        """Search for companies based on technology keywords across all companies"""
        found_companies = {}

        # Extract technology keywords from the query
        tech_keywords = []
        query_lower = query.lower()

        # Common technology terms to search for
        tech_terms = [
            "cloud",
            "virtualizzazione",
            "virtualization",
            "networking",
            "cybersecurity",
            "cyber security",
            "sicurezza",
            "data center",
            "datacenter",
            "iot",
            "ai",
            "artificial intelligence",
            "intelligenza artificiale",
            "machine learning",
            "blockchain",
            "big data",
            "analytics",
            "software",
            "sviluppo",
            "development",
            "web",
            "mobile",
            "app",
            "database",
            "erp",
            "crm",
            "telecomunicazioni",
            "telecommunications",
            "fiber",
            "fibra",
            "5g",
            "4g",
            "wireless",
            "voip",
            "automation",
            "automazione",
            "robotics",
            "robotica",
            "digital transformation",
            "trasformazione digitale",
            "integration",
            "integrazione",
            "api",
            "microservizi",
            "microservices",
            "devops",
            "agile",
            "scrum",
            "java",
            "python",
            "javascript",
            "react",
            "angular",
            "node",
            "docker",
            "kubernetes",
            "aws",
            "azure",
            "google cloud",
        ]

        # Find technology keywords in the query
        for term in tech_terms:
            if term in query_lower:
                tech_keywords.append(term)

        # If no specific tech terms found, extract general keywords
        if not tech_keywords:
            # Remove common words and extract potential tech terms
            stop_words = [
                "quali",
                "aziende",
                "hanno",
                "competenze",
                "in",
                "ambito",
                "di",
                "che",
                "con",
                "per",
                "su",
                "da",
                "a",
                "il",
                "la",
                "le",
                "i",
                "gli",
                "delle",
                "dei",
                "del",
                "della",
            ]
            words = query_lower.split()
            tech_keywords = [
                word for word in words if word not in stop_words and len(word) > 3
            ]

        # Search through all companies
        for company_name, company_data in self.company_lookup.items():
            match_score = 0
            match_reasons = []

            # Search in website intelligence
            if "website_intelligence" in company_data:
                intel_data = company_data["website_intelligence"]

                # Search in company references
                if (
                    "company_references" in intel_data
                    and intel_data["company_references"]
                ):
                    for ref in intel_data["company_references"]:
                        ref_lower = ref.lower()
                        for keyword in tech_keywords:
                            if keyword in ref_lower:
                                match_score += 1
                                if keyword not in match_reasons:
                                    match_reasons.append(keyword)

                # Search in other intelligence fields
                for field in ["business_activities", "key_services", "target_markets"]:
                    if field in intel_data and intel_data[field]:
                        field_text = str(intel_data[field]).lower()
                        for keyword in tech_keywords:
                            if keyword in field_text:
                                match_score += 1
                                if keyword not in match_reasons:
                                    match_reasons.append(keyword)

            # Search in chamber business activities
            if (
                "certifications" in company_data
                and "business_activities" in company_data["certifications"]
            ):
                business_activities = company_data["certifications"][
                    "business_activities"
                ]
                if "primary_activity" in business_activities:
                    activity_text = business_activities["primary_activity"].lower()
                    for keyword in tech_keywords:
                        if keyword in activity_text:
                            match_score += 1
                            if keyword not in match_reasons:
                                match_reasons.append(keyword)

            # If we found matches, add to results
            if match_score > 0:
                company_data_copy = company_data.copy()
                company_data_copy["_match_score"] = match_score
                company_data_copy["_match_reasons"] = match_reasons
                found_companies[company_name] = company_data_copy

        # Sort by match score (highest first)
        sorted_companies = dict(
            sorted(
                found_companies.items(),
                key=lambda x: x[1]["_match_score"],
                reverse=True,
            )
        )

        return sorted_companies

    def extract_relevant_data(
        self,
        companies: Dict[str, Any],
        datasets_needed: List[str],
        info_types: List[str],
    ) -> Dict[str, Any]:
        """Extract relevant data from unified company structure based on query analysis"""
        relevant_data = {}

        for company_key, company_data in companies.items():
            company_info = {"company_key": company_key}

            # Filter information based on requested types
            if "all" in info_types:
                # Return all available data
                company_info.update(company_data)
            else:
                # Extract specific information types
                if "contacts" in info_types:
                    # Extract contact information from various sections
                    contact_info = {}

                    # From contact_information section
                    if "contact_information" in company_data:
                        contact_info.update(company_data["contact_information"])

                    # From website_intelligence section
                    if "website_intelligence" in company_data:
                        intel_data = company_data["website_intelligence"]
                        contact_fields = [
                            "info_emails",
                            "phone_numbers",
                            "addresses",
                            "key_contacts",
                            "ceo_managing_director",
                        ]
                        for field in contact_fields:
                            if field in intel_data:
                                contact_info[field] = intel_data[field]

                    if contact_info:
                        company_info["contact_information"] = contact_info

                if "certifications" in info_types:
                    # Extract certification information
                    if "certifications" in company_data:
                        company_info["certifications"] = company_data["certifications"]

                if "technologies" in info_types:
                    # Extract technology information from website intelligence
                    if "website_intelligence" in company_data:
                        intel_data = company_data["website_intelligence"]
                        tech_info = {}

                        # Include all relevant technology and business fields
                        tech_fields = [
                            "classification",
                            "technology_stack",
                            "business_activities",
                            "key_services",
                            "target_markets",
                            "company_references",  # This contains the actual business descriptions
                        ]

                        for field in tech_fields:
                            if field in intel_data and intel_data[field]:
                                tech_info[field] = intel_data[field]

                        # Also include chamber analysis business activities if available
                        if (
                            "certifications" in company_data
                            and "business_activities" in company_data["certifications"]
                        ):
                            tech_info["chamber_business_activities"] = company_data[
                                "certifications"
                            ]["business_activities"]

                        if tech_info:
                            company_info["website_intelligence"] = tech_info

                if "financial" in info_types:
                    # Extract financial information
                    if "financial_data" in company_data:
                        company_info["financial_data"] = company_data["financial_data"]

                if "websites" in info_types:
                    # Extract website information
                    if "website_data" in company_data:
                        company_info["website_data"] = company_data["website_data"]

            if len(company_info) > 1:  # More than just company_key
                relevant_data[company_key] = company_info

        return relevant_data

    def generate_response_ollama(
        self, query: str, relevant_data: Dict[str, Any], query_analysis: Dict[str, Any]
    ) -> str:
        """Generate natural language response using Ollama"""
        try:
            # Prepare context with relevant data
            context = json.dumps(relevant_data, indent=2, ensure_ascii=False)
            if len(context) > self.config["chatbot"]["max_context_length"]:
                context = (
                    context[: self.config["chatbot"]["max_context_length"]] + "..."
                )

            prompt = f"""Sei un assistente esperto di informazioni aziendali italiane. Rispondi alla domanda dell'utente usando i dati forniti.

DOMANDA UTENTE: "{query}"

ANALISI QUERY:
- Intento: {query_analysis.get('intent', 'unknown')}
- Tipo informazioni: {', '.join(query_analysis.get('information_type', []))}

DATI DISPONIBILI:
{context}

ISTRUZIONI:
1. Rispondi in italiano in modo naturale e conversazionale
2. Usa i dati forniti per dare informazioni precise
3. Se non trovi informazioni specifiche, dillo chiaramente
4. Organizza la risposta in modo leggibile
5. Includi dettagli rilevanti ma mantieni la risposta concisa
6. Se ci sono più aziende, confrontale brevemente

FORMATO RISPOSTA:
- Inizia con un saluto amichevole
- Presenta le informazioni in modo strutturato
- Concludi offrendo ulteriore assistenza

Rispondi in modo naturale e utile:"""

            ollama_request = {
                "model": self.config["intelligence"]["ollama_model"],
                "prompt": prompt,
                "stream": self.config["intelligence"]["ollama_stream"],
                "options": {
                    "temperature": self.config["intelligence"]["ollama_temperature"],
                },
            }

            response = requests.post(
                self.config["intelligence"]["ollama_endpoint"],
                json=ollama_request,
                timeout=self.config["intelligence"]["ollama_timeout"],
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()

        except Exception as e:
            print(f"⚠️ Response generation error: {e}")

        # Fallback response
        return self._generate_fallback_response(relevant_data, query)

    def _generate_fallback_response(
        self, relevant_data: Dict[str, Any], query: str
    ) -> str:
        """Generate fallback response when Ollama is not available"""
        if not relevant_data:
            return f"❌ Non ho trovato informazioni per: {query}\n\nProva con un nome azienda più specifico o un codice fiscale."

        response = f"📋 Ecco le informazioni trovate per: {query}\n\n"

        for company_key, company_info in relevant_data.items():
            response += f"🏢 **{company_key}**\n"

            # Check if this is a technology/sector query
            is_tech_query = any(
                keyword in query.lower()
                for keyword in [
                    "settori",
                    "settore",
                    "tecnologie",
                    "tecnologia",
                    "opera",
                    "attività",
                    "business",
                    "servizi",
                ]
            )

            if is_tech_query and "website_intelligence" in company_info:
                intel_data = company_info["website_intelligence"]

                # Extract business information from company references
                if (
                    "company_references" in intel_data
                    and intel_data["company_references"]
                ):
                    response += "  🔍 **Settori e Attività:**\n"

                    # Process company references to extract key business activities
                    references = intel_data["company_references"]
                    business_activities = []

                    for ref in references[:5]:  # Limit to first 5 references
                        if len(ref) > 50:  # Only meaningful references
                            # Clean and extract key phrases
                            clean_ref = ref.replace("\n", " ").strip()
                            if clean_ref:
                                business_activities.append(
                                    f"    • {clean_ref[:200]}..."
                                )

                    if business_activities:
                        response += "\n".join(business_activities) + "\n\n"

                # Add chamber business activities if available
                if "chamber_business_activities" in intel_data:
                    chamber_activities = intel_data["chamber_business_activities"]
                    if "primary_activity" in chamber_activities:
                        response += f"  📋 **Attività Principale:** {chamber_activities['primary_activity']}\n"
                    if (
                        "ateco_codes" in chamber_activities
                        and chamber_activities["ateco_codes"]
                    ):
                        response += f"  🏷️ **Codici ATECO:** {', '.join(chamber_activities['ateco_codes'])}\n"
                    response += "\n"
            else:
                # Standard response for non-tech queries
                for dataset_name, dataset_info in company_info.items():
                    if dataset_name == "company_key":
                        continue

                    response += f"  📊 {dataset_name.replace('_', ' ').title()}:\n"

                    # Show key information
                    if isinstance(dataset_info, dict):
                        for key, value in list(dataset_info.items())[
                            :5
                        ]:  # Limit to 5 items
                            if value and str(value).strip():
                                if isinstance(value, list) and len(value) > 0:
                                    response += f"    • {key}: {', '.join(str(v) for v in value[:3])}\n"
                                else:
                                    response += f"    • {key}: {value}\n"

                    response += "\n"

        response += "💡 Chiedi informazioni più specifiche per dettagli aggiuntivi!"
        return response

    def trigger_dynamic_scraping(
        self, company_name: str, missing_info: List[str]
    ) -> bool:
        """Trigger targeted scraping for missing information"""
        if not self.config["chatbot"]["enable_dynamic_scraping"]:
            return False

        print(f"🔍 Avvio scraping mirato per {company_name}...")

        try:
            # This would trigger step 4 with specific parameters
            cmd = [
                "python",
                "company_intelligence_scraper.py",
                "--company",
                company_name,
                "--focus",
                ",".join(missing_info),
                "--headless",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                print("✅ Scraping completato, ricarico i dati...")
                self._load_all_data()
                return True
            else:
                print(f"❌ Errore durante lo scraping: {result.stderr}")

        except Exception as e:
            print(f"❌ Errore nell'avvio dello scraping: {e}")

        return False

    def process_query(self, query: str) -> str:
        """Process user query and return response"""
        if not query.strip():
            return "🤔 Puoi farmi una domanda su un'azienda italiana?"

        print("🤖 Analizzo la tua domanda...")

        # Analyze query with Ollama
        query_analysis = self.analyze_query_ollama(query)

        # Check if this is a cross-company technology search
        if query_analysis.get("intent") == "search_by_technology":
            print("🔍 Ricerca aziende per tecnologie/competenze...")
            found_companies = self.search_companies_by_technology(query)
        else:
            # Search for companies using standard method
            found_companies = self.search_companies(
                query_analysis.get("company_identifiers", []),
                query_analysis.get("search_terms", []),
            )

        if not found_companies:
            return f"❌ Non ho trovato aziende corrispondenti a: {query}\n\n💡 Prova con:\n• Nome completo dell'azienda\n• Codice fiscale\n• Parte del nome"

        # Extract relevant data
        relevant_data = self.extract_relevant_data(
            found_companies,
            query_analysis.get("datasets_needed", ["companies_detailed"]),
            query_analysis.get("information_type", ["all"]),
        )

        # Check if we need more information
        if self.config["chatbot"]["enable_dynamic_scraping"]:
            for company_key in found_companies.keys():
                missing_datasets = []
                for dataset in query_analysis.get("datasets_needed", []):
                    if dataset not in found_companies[company_key]:
                        missing_datasets.append(dataset)

                if missing_datasets and "website_intelligence" in missing_datasets:
                    company_name = company_key
                    if self.trigger_dynamic_scraping(company_name, missing_datasets):
                        # Re-search after scraping
                        found_companies = self.search_companies(
                            query_analysis.get("company_identifiers", []),
                            query_analysis.get("search_terms", []),
                        )
                        relevant_data = self.extract_relevant_data(
                            found_companies,
                            query_analysis.get("datasets_needed", []),
                            query_analysis.get("information_type", []),
                        )

        # Generate response
        response = self.generate_response_ollama(query, relevant_data, query_analysis)
        return response

    def run(self):
        """Main chatbot loop"""
        print("\n" + "=" * 60)
        print("🤖 Company Intelligence Chatbot")
        print("=" * 60)
        print("Ciao! Sono il tuo assistente per informazioni su aziende italiane.")
        print("Puoi chiedermi di:")
        print("• Cercare informazioni su un'azienda")
        print("• Trovare contatti e certificazioni")
        print("• Confrontare aziende")
        print("• Analizzare tecnologie e competenze")
        print("\n💡 Esempi di domande:")
        print("  - 'Dimmi tutto su [NOME AZIENDA]'")
        print("  - 'Quali certificazioni ha [AZIENDA]?'")
        print("  - 'Contatti di [AZIENDA]'")
        print("  - 'Confronta [AZIENDA1] e [AZIENDA2]'")
        print("  - 'In quali settori opera [AZIENDA]?'")
        print("\n⌨️  Scrivi 'exit' o premi Ctrl+C per uscire")
        print("-" * 60)

        while self.running:
            try:
                # Get user input
                query = input("\n🗣️  La tua domanda: ").strip()

                if not query:
                    continue

                if query.lower() in ["exit", "quit", "bye", "ciao"]:
                    print("\n👋 Arrivederci! Grazie per aver usato il chatbot.")
                    break

                # Process query
                response = self.process_query(query)

                # Display response
                print(f"\n🤖 Risposta:\n{response}")
                print("-" * 60)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Errore: {e}")
                print("Riprova con una domanda diversa.")

        self.running = False


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Intelligent Company Chatbot - Natural language access to company data"
    )
    parser.add_argument(
        "--config", default="config.yml", help="Configuration file path"
    )

    args = parser.parse_args()

    try:
        chatbot = IntelligentChatbot(config_path=args.config)
        chatbot.run()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")


if __name__ == "__main__":
    main()
