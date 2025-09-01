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

            # Try multiple possible file paths
            possible_files = [
                self.config["file_paths"].get(
                    "companies_detailed", "companies_detailed.csv"
                ),
                "companies_detailed.csv",
                "company_websites.csv",
                "unified_company_data.csv",
            ]

            companies_file = None
            for file_path in possible_files:
                if Path(file_path).exists():
                    companies_file = file_path
                    break

            if not companies_file:
                print(f"Warning: No companies file found, tried: {possible_files}")
                return {}

            print(f"Loading companies from: {companies_file}")

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
            print(
                f"Loaded {unique_companies} companies for matching from {companies_file}"
            )
            return companies

        except FileNotFoundError as e:
            print(f"Warning: Companies file not found: {e}")
            return {}
        except Exception as e:
            print(f"Error loading companies data: {e}")
            return {}

    def extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyMuPDF for better handling"""
        try:
            # Set MuPDF to silent mode
            import warnings

            warnings.filterwarnings("ignore")

            # Suppress all MuPDF output by setting verbosity to 0
            if hasattr(fitz, "TOOLS") and hasattr(
                fitz.TOOLS, "set_small_glyph_heights"
            ):
                # Try to set MuPDF to quiet mode if available
                pass

            # Use subprocess to completely isolate MuPDF warnings
            import subprocess
            import tempfile

            # Create a temporary Python script to extract text
            script_content = f"""
import fitz
import sys
import os

# Redirect all output to devnull
sys.stderr = open(os.devnull, 'w')
sys.stdout = open(os.devnull, 'w')

try:
    doc = fitz.open("{pdf_path}")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    
    # Write result to a temp file
    with open("{pdf_path}.txt", "w", encoding="utf-8") as f:
        f.write(text)
except:
    pass
"""

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as temp_script:
                temp_script.write(script_content)
                temp_script_path = temp_script.name

            try:
                # Run the script in complete isolation
                subprocess.run(
                    ["python", temp_script_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # Read the extracted text
                text_file = f"{pdf_path}.txt"
                if os.path.exists(text_file):
                    with open(text_file, "r", encoding="utf-8") as f:
                        text = f.read()
                    os.remove(text_file)
                    return text
                else:
                    raise Exception("Text extraction failed")

            finally:
                os.unlink(temp_script_path)

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

    def preprocess_content(self, text: str) -> Dict[str, str]:
        """Preprocess PDF content with intelligent segmentation"""
        # Clean up text
        text = re.sub(r"\s+", " ", text)  # Normalize whitespace
        text = re.sub(r"[^\w\s\.,;:()\-/]", "", text)  # Remove special chars

        # Segment content by relevance instead of truncating
        sections = {
            "certifications": self._extract_certification_sections(text),
            "business_activities": self._extract_business_sections(text),
            "technical_auth": self._extract_technical_sections(text),
            "financial": self._extract_financial_sections(text),
            "full_text": text,  # Keep full text for fallback
        }

        return sections

    def _extract_certification_sections(self, text: str) -> str:
        """Extract sections related to certifications"""
        cert_keywords = [
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
            "sistema di gestione",
            "certificato",
            "emesso da",
            "data prima emissione",
            "scadenza",
            "settore",
            "norma",
        ]

        return self._extract_sections_by_keywords(text, cert_keywords, context_lines=5)

    def _extract_business_sections(self, text: str) -> str:
        """Extract sections related to business activities"""
        business_keywords = [
            "oggetto sociale",
            "attività",
            "servizi",
            "prodotti",
            "settore",
            "specializzazione",
            "ateco",
            "codice attività",
            "descrizione attività",
            "settore di attività",
            "ramo di attività",
            "categoria merceologica",
        ]

        return self._extract_sections_by_keywords(
            text, business_keywords, context_lines=8
        )

    def _extract_technical_sections(self, text: str) -> str:
        """Extract sections related to technical authorizations"""
        tech_keywords = [
            "abilitazioni",
            "lettera a",
            "lettera b",
            "lettera c",
            "lettera d",
            "impiantistiche",
            "impianti elettrici",
            "impianti radiotelevisivi",
            "impianti elettronici",
            "autorizzazioni tecniche",
            "abilitazione tecnica",
        ]

        return self._extract_sections_by_keywords(text, tech_keywords, context_lines=4)

    def _extract_financial_sections(self, text: str) -> str:
        """Extract sections related to financial data"""
        financial_keywords = [
            "capitale sociale",
            "fatturato",
            "ricavi",
            "dipendenti",
            "addetti",
            "bilancio",
            "patrimonio netto",
            "utile",
            "perdita",
            "reddito",
        ]

        return self._extract_sections_by_keywords(
            text, financial_keywords, context_lines=3
        )

    def _extract_sections_by_keywords(
        self, text: str, keywords: List[str], context_lines: int = 3
    ) -> str:
        """Extract text sections containing specific keywords with context"""
        lines = text.split("\n")
        relevant_sections = []

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                # Include context around relevant lines
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                section = lines[start:end]
                relevant_sections.extend(section)

        # Remove duplicates while preserving order
        seen = set()
        unique_sections = []
        for line in relevant_sections:
            if line not in seen:
                seen.add(line)
                unique_sections.append(line)

        return "\n".join(unique_sections)

    def match_company(self, pdf_text: str, pdf_name: str) -> Optional[Dict]:
        """Match PDF document to company using name and tax code from first page only"""
        # Extract the first page content only (much more accurate for visure documents)
        lines = pdf_text.split("\n")

        # Estimate first page content (typically first 100-150 lines in a visura)
        # Look for page break indicators or use a reasonable line limit
        first_page_lines = []
        for i, line in enumerate(lines):
            # Stop at common page break indicators
            if i > 50 and any(
                indicator in line.lower()
                for indicator in ["pagina 2", "page 2", "pag. 2", "foglio 2"]
            ):
                break
            # Use reasonable limit for first page
            if i >= 150:
                break
            first_page_lines.append(line)

        first_page_content = "\n".join(first_page_lines)

        # Extract identifiers from first page only
        identifiers = []

        # Extract tax codes from first page
        tax_code_patterns = [
            r"codice fiscale[:\s]*([0-9]{11})",
            r"partita iva[:\s]*([0-9]{11})",
            r"c\.f\.[:\s]*([0-9]{11})",
            r"p\.iva[:\s]*([0-9]{11})",
        ]

        for pattern in tax_code_patterns:
            matches = re.findall(pattern, first_page_content.lower())
            identifiers.extend(matches)

        # Extract company names from first page
        name_patterns = [
            r"denominazione[:\s]*([A-Z][^.\n]{5,80})",
            r"ragione sociale[:\s]*([A-Z][^.\n]{5,80})",
            r"impresa[:\s]*([A-Z][^.\n]{5,80})",
        ]

        for pattern in name_patterns:
            matches = re.findall(pattern, first_page_content, re.IGNORECASE)
            for match in matches:
                clean_name = re.sub(r"\s+", " ", match.strip()).upper()
                # Filter out common false positives
                if len(clean_name) >= 5 and not any(
                    exclude in clean_name.lower()
                    for exclude in [
                        "del soggetto",
                        "alla data",
                        "denuncia",
                        "progetto",
                        "mediante",
                        "organismo",
                        "attestazione",
                    ]
                ):
                    identifiers.append(clean_name)

        # Remove duplicates while preserving order
        unique_identifiers = []
        seen = set()
        for identifier in identifiers:
            if identifier not in seen:
                seen.add(identifier)
                unique_identifiers.append(identifier)

        # Debug: Print identifiers being checked
        print(f"  Debug: Identifiers from first page: {unique_identifiers}")
        print(
            f"  Debug: First page content length: {len(first_page_content)} characters"
        )

        # Try to match with loaded companies - exact match only
        for identifier in unique_identifiers:
            if identifier in self.companies_data:
                matched_company = self.companies_data[identifier]
                print(
                    f"  Debug: Match found for '{identifier}' -> {matched_company.get('company_name', 'Unknown')}"
                )
                return matched_company

        print(f"  Debug: No match found for any identifier from first page")
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

        # Preprocess content with intelligent segmentation
        content_sections = self.preprocess_content(pdf_text)
        total_processed = sum(
            len(section)
            for section in content_sections.values()
            if isinstance(section, str)
        )
        print(
            f"  ✓ Segmented content: {total_processed} characters across {len(content_sections)} sections"
        )

        # Direct certification extraction
        direct_certifications = self.extract_certifications_direct(pdf_text)

        # AI analysis using Ollama with segmented content
        ai_analysis = self.analyze_content_ollama(
            content_sections.get("full_text", "")[:4000], company_name
        )

        # Combine results
        result = {
            "document_name": pdf_path.name,
            "company_name": company_name,
            "matched_company_data": matched_company,
            "analysis_status": "completed",
            "direct_extraction": direct_certifications,
            "ai_analysis": ai_analysis,
            "document_length": len(pdf_text),
            "processed_length": total_processed,
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
