#!/usr/bin/env python3
"""
Chamber of Commerce Document Analyzer - Step 5
==============================================

Analyzes PDF documents from the Chamber of Commerce (visure) to extract
business certifications and relevant company information. Uses Ollama for
intelligent content analysis and matches documents to companies using
business names and tax codes.

Features:
- PDF text extraction and preprocessing
- Company matching using business names and tax codes
- Certification extraction (SOA, Quality, Environmental, Safety)
- AI-powered content analysis using Ollama
- Structured output in JSON format

Usage: python chamber_document_analyzer.py [--limit N] [--config config.yml]
"""

import os
import json
import yaml
import argparse
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
import PyPDF2
import fitz  # PyMuPDF for better PDF handling


class ChamberDocumentAnalyzer:
    """
    Analyzes Chamber of Commerce PDF documents to extract business certifications
    and relevant company information with AI-powered content analysis.
    """

    def __init__(self, config_path="config.yml"):
        """Initialize the analyzer with configuration"""
        self.config = self._load_config(config_path)
        self.visure_folder = Path("visure")
        self.companies_data = self._load_companies_data()

    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                if "chamber_analysis" not in config:
                    config["chamber_analysis"] = self._default_chamber_config()
                return config
        except FileNotFoundError:
            print(f"Warning: Config file {config_path} not found, using defaults")
            return self._default_config()

    def _default_config(self):
        """Default configuration if file not found"""
        return {
            "file_paths": {
                "companies_detailed": "companies_detailed.csv",
                "chamber_analysis_output": "chamber_analysis.json",
            },
            "chamber_analysis": self._default_chamber_config(),
            "intelligence": {
                "ollama_endpoint": "http://ollama.lan:11434/api/generate",
                "ollama_model": "gemma3:12b",
                "ollama_stream": False,
                "ollama_temperature": 0.3,
                "ollama_timeout": 60,
            },
        }

    def _default_chamber_config(self):
        """Default chamber analysis configuration"""
        return {
            "max_content_length": 8000,
            "certification_keywords": [
                "certificazione",
                "attestazione",
                "qualità",
                "quality",
                "ambientale",
                "environmental",
                "sicurezza",
                "safety",
                "soa",
                "iso",
                "uni",
                "accredia",
            ],
            "business_keywords": [
                "oggetto sociale",
                "attività",
                "servizi",
                "prodotti",
                "settore",
                "specializzazione",
            ],
        }

    def _load_companies_data(self):
        """Load companies data for matching"""
        companies = {}
        try:
            import csv

            companies_file = self.config["file_paths"]["detailed_data_output"]
            with open(companies_file, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Create multiple keys for matching
                    company_name = row.get("company_name", "").strip()
                    tax_code = row.get("tax_code", "").strip()
                    vat_number = row.get("vat_number", "").strip()

                    if company_name:
                        companies[company_name.upper()] = row
                    if tax_code:
                        companies[tax_code] = row
                    if vat_number and vat_number != tax_code:
                        companies[vat_number] = row

            # Count unique companies by counting unique tax codes
            unique_companies = len(
                set(
                    row.get("tax_code", "")
                    for row in companies.values()
                    if row.get("tax_code")
                )
            )
            print(f"Loaded {unique_companies} companies for matching")
            return companies

        except FileNotFoundError:
            print(f"Warning: Companies file not found, proceeding without matching")
            return {}

    def extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyMuPDF for better handling"""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            print(f"  ✗ Error extracting text from {pdf_path.name}: {e}")
            # Fallback to PyPDF2
            try:
                with open(pdf_path, "rb") as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text()
                return text
            except Exception as e2:
                print(f"  ✗ Fallback extraction also failed: {e2}")
                return ""

    def preprocess_content(self, text: str) -> str:
        """Preprocess PDF content for better analysis"""
        # Clean up text
        text = re.sub(r"\s+", " ", text)  # Normalize whitespace
        text = re.sub(r"[^\w\s\.,;:()\-/]", "", text)  # Remove special chars

        # Limit content length for Ollama
        max_length = self.config["chamber_analysis"]["max_content_length"]
        if len(text) > max_length:
            # Try to find relevant sections
            cert_keywords = self.config["chamber_analysis"]["certification_keywords"]
            business_keywords = self.config["chamber_analysis"]["business_keywords"]

            relevant_sections = []
            lines = text.split("\n")

            for i, line in enumerate(lines):
                line_lower = line.lower()
                if any(
                    keyword in line_lower
                    for keyword in cert_keywords + business_keywords
                ):
                    # Include context around relevant lines
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    relevant_sections.extend(lines[start:end])

            if relevant_sections:
                text = "\n".join(relevant_sections)

            # If still too long, truncate
            if len(text) > max_length:
                text = text[:max_length] + "..."

        return text

    def match_company(self, pdf_text: str, pdf_name: str) -> Optional[Dict]:
        """Match PDF document to company using name and tax code"""
        # Extract potential company identifiers from PDF
        identifiers = []

        # Extract from filename
        filename_parts = pdf_name.replace("_decrypted.pdf", "").split(" - ")
        if filename_parts:
            identifiers.append(filename_parts[0].strip().upper())

        # Extract tax codes from text
        tax_code_patterns = [
            r"codice fiscale[:\s]*([0-9]{11})",
            r"partita iva[:\s]*([0-9]{11})",
            r"c\.f\.[:\s]*([0-9]{11})",
            r"p\.iva[:\s]*([0-9]{11})",
        ]

        for pattern in tax_code_patterns:
            matches = re.findall(pattern, pdf_text.lower())
            identifiers.extend(matches)

        # Extract company names
        name_patterns = [
            r"denominazione[:\s]*([A-Z][^.\n]{10,80})",
            r"ragione sociale[:\s]*([A-Z][^.\n]{10,80})",
        ]

        for pattern in name_patterns:
            matches = re.findall(pattern, pdf_text, re.IGNORECASE)
            for match in matches:
                clean_name = re.sub(r"\s+", " ", match.strip()).upper()
                identifiers.append(clean_name)

        # Try to match with loaded companies
        for identifier in identifiers:
            if identifier in self.companies_data:
                return self.companies_data[identifier]

        return None

    def extract_certifications_direct(self, text: str) -> Dict[str, Any]:
        """Direct extraction of certifications from text with detailed information"""
        certifications = {
            "soa_attestations": [],
            "quality_certifications": [],
            "environmental_certifications": [],
            "safety_certifications": [],
            "environmental_registrations": [],
            "technical_authorizations": [],
            "other_certifications": [],
        }

        # Split text into lines for better context extraction
        lines = text.split("\n")

        # SOA Attestations - Enhanced patterns
        soa_patterns = [
            r"codice soa[:\s]*([0-9]{11})",
            r"numero attestazione[:\s]*([0-9/]+)",
            r"attestazione[:\s]*n[°\.\s]*([0-9/]+)",
            r"rilasciata il[:\s]*([0-9/]+)",
            r"scadenza[:\s]*([0-9/]+)",
            r"og[0-9]+.*?classe\s+[ivx]+.*?€\s*[\d\.,]+",
            r"os[0-9]+.*?classe\s+[ivx]+.*?€\s*[\d\.,]+",
        ]

        # Look for SOA sections in text
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(
                keyword in line_lower
                for keyword in ["attestazione soa", "codice soa", "categorie"]
            ):
                # Extract context around SOA information
                context_start = max(0, i - 3)
                context_end = min(len(lines), i + 10)
                soa_context = "\n".join(lines[context_start:context_end])

                for pattern in soa_patterns:
                    matches = re.findall(pattern, soa_context, re.IGNORECASE)
                    for match in matches:
                        if match.strip() and len(match.strip()) > 3:
                            certifications["soa_attestations"].append(match.strip())

        # Quality Certifications - Enhanced with certificate details
        quality_patterns = [
            r"uni en iso 9001:([0-9]{4})",
            r"certificato n[°\.\s]*([C0-9\-R]+)",
            r"emesso da[:\s]*([^.\n]{10,80})",
            r"data prima emissione[:\s]*([0-9/]+)",
            r"settore[:\s]*([0-9]+\s*-\s*[^.\n]+)",
        ]

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(
                keyword in line_lower for keyword in ["iso 9001", "qualità", "quality"]
            ):
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 8)
                quality_context = "\n".join(lines[context_start:context_end])

                for pattern in quality_patterns:
                    matches = re.findall(pattern, quality_context, re.IGNORECASE)
                    for match in matches:
                        if match.strip():
                            certifications["quality_certifications"].append(
                                match.strip()
                            )

        # Environmental Certifications - Enhanced
        env_patterns = [
            r"uni en iso 14001:([0-9]{4})",
            r"sistema di gestione ambientale",
            r"certificato n[°\.\s]*([C0-9\-R]+)",
            r"emesso da[:\s]*([^.\n]{10,80})",
            r"data prima emissione[:\s]*([0-9/]+)",
        ]

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(
                keyword in line_lower
                for keyword in ["iso 14001", "ambientale", "environmental"]
            ):
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 8)
                env_context = "\n".join(lines[context_start:context_end])

                for pattern in env_patterns:
                    matches = re.findall(pattern, env_context, re.IGNORECASE)
                    for match in matches:
                        if match.strip():
                            certifications["environmental_certifications"].append(
                                match.strip()
                            )

        # Safety Certifications - Enhanced
        safety_patterns = [
            r"uni iso 45001:([0-9]{4})",
            r"ohsas 18001:([0-9]{4})",
            r"salute e sicurezza sul lavoro",
            r"certificato n[°\.\s]*([C0-9\-R]+)",
            r"emesso da[:\s]*([^.\n]{10,80})",
            r"data prima emissione[:\s]*([0-9/]+)",
        ]

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(
                keyword in line_lower
                for keyword in ["45001", "18001", "sicurezza", "safety"]
            ):
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 8)
                safety_context = "\n".join(lines[context_start:context_end])

                for pattern in safety_patterns:
                    matches = re.findall(pattern, safety_context, re.IGNORECASE)
                    for match in matches:
                        if match.strip():
                            certifications["safety_certifications"].append(
                                match.strip()
                            )

        # Environmental Registrations (Albo Gestori Ambientali)
        env_reg_patterns = [
            r"albo nazionale gestori ambientali",
            r"numero iscrizione[:\s]*([A-Z0-9/]+)",
            r"sezione[:\s]*([^.\n]+)",
            r"categoria[:\s]*([^.\n]+)",
            r"scadenza[:\s]*([0-9/]+)",
        ]

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if "albo" in line_lower and "gestori" in line_lower:
                context_start = max(0, i - 1)
                context_end = min(len(lines), i + 6)
                albo_context = "\n".join(lines[context_start:context_end])

                for pattern in env_reg_patterns:
                    matches = re.findall(pattern, albo_context, re.IGNORECASE)
                    for match in matches:
                        if match.strip():
                            certifications["environmental_registrations"].append(
                                match.strip()
                            )

        # Technical Authorizations (Abilitazioni impiantistiche)
        tech_auth_patterns = [
            r"lettera [a-z][:\s]*([^.\n]+)",
            r"abilitazioni impiantistiche",
            r"l\.p\.\s*bz[^.\n]*",
            r"impianti elettrici[^.\n]*",
            r"impianti radiotelevisivi[^.\n]*",
        ]

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(
                keyword in line_lower
                for keyword in [
                    "abilitazioni",
                    "lettera a",
                    "lettera b",
                    "impiantistiche",
                ]
            ):
                context_start = max(0, i - 1)
                context_end = min(len(lines), i + 4)
                auth_context = "\n".join(lines[context_start:context_end])

                for pattern in tech_auth_patterns:
                    matches = re.findall(pattern, auth_context, re.IGNORECASE)
                    for match in matches:
                        if match.strip():
                            certifications["technical_authorizations"].append(
                                match.strip()
                            )

        # Clean up duplicates and empty entries
        for key in certifications:
            certifications[key] = list(
                dict.fromkeys([cert for cert in certifications[key] if cert.strip()])
            )

        return certifications

    def analyze_content_ollama(self, content: str, company_name: str) -> Optional[Dict]:
        """Analyze content using Ollama AI"""
        try:
            prompt = f"""Analizza il seguente documento della Camera di Commercio per l'azienda italiana "{company_name}" ed estrai informazioni strutturate dettagliate sui seguenti aspetti:

CONTENUTO DOCUMENTO:
{content[:4000]}

ISTRUZIONI DETTAGLIATE:
1. Estrai TUTTE le certificazioni con dettagli completi (numeri certificato, enti emittenti, date)
2. Trova attestazioni SOA con codici, categorie e classi specifiche
3. Identifica iscrizioni ad albi professionali e ambientali
4. Estrai abilitazioni tecniche e impiantistiche
5. Trova dati finanziari, dipendenti e informazioni societarie

FORMATO RISPOSTA JSON DETTAGLIATO:
{{
    "certifications": {{
        "soa_attestations": [
            {{
                "codice_soa": "numero codice",
                "numero_attestazione": "numero/codice",
                "rilasciata_il": "data",
                "scadenza": "data",
                "categorie": ["OG3 Classe I", "OS19 Classe V", "etc"],
                "ente_rilascio": "nome ente"
            }}
        ],
        "quality_certifications": [
            {{
                "norma": "UNI EN ISO 9001:2015",
                "certificato_numero": "numero certificato",
                "emesso_da": "ente certificatore",
                "data_prima_emissione": "data",
                "settore": "settore applicazione",
                "descrizione": "Sistema di Gestione per la Qualità"
            }}
        ],
        "environmental_certifications": [
            {{
                "norma": "UNI EN ISO 14001:2015",
                "certificato_numero": "numero certificato",
                "emesso_da": "ente certificatore",
                "data_prima_emissione": "data",
                "descrizione": "Sistema di Gestione Ambientale"
            }}
        ],
        "safety_certifications": [
            {{
                "norma": "UNI ISO 45001:2018",
                "certificato_numero": "numero certificato",
                "emesso_da": "ente certificatore",
                "data_prima_emissione": "data",
                "descrizione": "Sistema di Gestione per la Salute e Sicurezza sul Lavoro"
            }}
        ],
        "environmental_registrations": [
            {{
                "albo": "Albo Nazionale Gestori Ambientali",
                "numero_iscrizione": "codice iscrizione",
                "sezione": "sezione territoriale",
                "categoria": "categoria e descrizione",
                "scadenza": "data scadenza"
            }}
        ],
        "technical_authorizations": [
            {{
                "tipo": "Abilitazioni impiantistiche",
                "riferimento_normativo": "L.P. BZ-1/2008",
                "lettere": ["Lettera A: descrizione", "Lettera B: descrizione"]
            }}
        ]
    }},
    "business_activities": {{
        "primary_activity": "attività principale dettagliata",
        "secondary_activities": ["attività secondarie"],
        "ateco_codes": ["codici ATECO con descrizione"],
        "specializations": ["specializzazioni tecniche"]
    }},
    "financial_data": {{
        "share_capital": "capitale sociale",
        "employees": "numero dipendenti",
        "revenue": "fatturato se disponibile"
    }},
    "analysis_confidence": 0.85,
    "key_insights": ["insight dettagliati sulle certificazioni e competenze"]
}}

IMPORTANTE: Estrai TUTTI i numeri di certificato, date, enti emittenti e dettagli specifici che trovi nel documento.
Rispondi SOLO con JSON valido:"""

            # Prepare Ollama request
            ollama_request = {
                "model": self.config["intelligence"]["ollama_model"],
                "prompt": prompt,
                "stream": self.config["intelligence"]["ollama_stream"],
                "options": {
                    "temperature": self.config["intelligence"]["ollama_temperature"],
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
                    analysis = json.loads(json_str)
                    return analysis

        except Exception as e:
            print(f"  ✗ Ollama analysis error: {e}")

        return None

    def analyze_document(self, pdf_path: Path) -> Dict[str, Any]:
        """Analyze a single Chamber of Commerce document"""
        print(f"\n=== Analyzing: {pdf_path.name} ===")

        # Extract text from PDF
        pdf_text = self.extract_pdf_text(pdf_path)
        if not pdf_text:
            return {
                "document_name": pdf_path.name,
                "analysis_status": "failed",
                "error": "Could not extract text from PDF",
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

        print(f"  ✓ Extracted {len(pdf_text)} characters from PDF")

        # Match to company
        matched_company = self.match_company(pdf_text, pdf_path.name)
        company_name = (
            matched_company.get("company_name", "Unknown")
            if matched_company
            else "Unknown"
        )

        print(f"  Company match: {company_name}")

        # Preprocess content
        processed_content = self.preprocess_content(pdf_text)
        print(f"  ✓ Preprocessed content: {len(processed_content)} characters")

        # Direct certification extraction
        direct_certifications = self.extract_certifications_direct(pdf_text)

        # AI analysis using Ollama
        ai_analysis = self.analyze_content_ollama(processed_content, company_name)

        # Combine results
        result = {
            "document_name": pdf_path.name,
            "company_name": company_name,
            "matched_company_data": matched_company,
            "analysis_status": "completed",
            "direct_extraction": direct_certifications,
            "ai_analysis": ai_analysis,
            "document_length": len(pdf_text),
            "processed_length": len(processed_content),
            "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        print(f"  ✓ Analysis completed for {company_name}")
        return result

    def process_documents(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Process all PDF documents in the visure folder"""
        print("Chamber of Commerce Document Analyzer")
        print("=" * 50)

        if not self.visure_folder.exists():
            print(f"✗ Error: Visure folder '{self.visure_folder}' not found")
            return []

        # Find PDF files
        pdf_files = list(self.visure_folder.glob("*.pdf"))
        if not pdf_files:
            print(f"✗ No PDF files found in '{self.visure_folder}'")
            return []

        if limit:
            pdf_files = pdf_files[:limit]
            print(f"Processing first {limit} documents (development mode)")

        print(f"Found {len(pdf_files)} PDF documents to analyze")

        results = []
        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")

            try:
                result = self.analyze_document(pdf_path)
                results.append(result)

                # Delay between documents
                if i < len(pdf_files):
                    delay = 2
                    print(f"  Waiting {delay}s before next document...")
                    time.sleep(delay)

            except Exception as e:
                print(f"  ✗ Error processing {pdf_path.name}: {e}")
                results.append(
                    {
                        "document_name": pdf_path.name,
                        "analysis_status": "error",
                        "error": str(e),
                        "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

        # Save results
        output_file = self.config["file_paths"]["chamber_analysis_output"]
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(results, file, indent=2, ensure_ascii=False)

        print(f"\n✓ Chamber document analysis completed!")
        print(f"✓ Results saved to: {output_file}")
        print(f"✓ Processed {len(results)} documents")

        # Summary statistics
        successful = len(
            [r for r in results if r.get("analysis_status") == "completed"]
        )
        with_ai_analysis = len([r for r in results if r.get("ai_analysis")])
        matched_companies = len([r for r in results if r.get("matched_company_data")])

        print(f"✓ Successful analyses: {successful}/{len(results)}")
        print(f"✓ With AI analysis: {with_ai_analysis}/{successful}")
        print(f"✓ Matched to companies: {matched_companies}/{len(results)}")

        return results


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Chamber of Commerce Document Analyzer - Extract business certifications from PDF documents"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of documents to process (for development/testing)",
    )
    parser.add_argument(
        "--config", default="config.yml", help="Configuration file path"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Chamber of Commerce Document Analyzer")
    print("=" * 60)
    print(f"Configuration: {args.config}")
    if args.limit:
        print(f"Development mode: Processing {args.limit} documents")
    print("=" * 60)

    try:
        analyzer = ChamberDocumentAnalyzer(config_path=args.config)
        results = analyzer.process_documents(limit=args.limit)

        if results:
            print(f"\n✓ Chamber document analysis completed successfully!")
            print(f"✓ Check the output file for detailed results")
        else:
            print(f"\n✗ No results generated")

    except KeyboardInterrupt:
        print(f"\n⚠ Process interrupted by user")
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")


if __name__ == "__main__":
    main()
