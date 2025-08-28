#!/usr/bin/env python3
"""
Comprehensive Chatbot Data Source Testing
========================================

Tests the chatbot's ability to retrieve information from all data sources
using MET as the test company.
"""

from intelligent_chatbot import IntelligentChatbot
import json


def test_data_source_retrieval():
    """Test chatbot retrieval from each data source"""

    print("=" * 60)
    print("COMPREHENSIVE CHATBOT DATA SOURCE TESTING")
    print("=" * 60)
    print("Test Company: MET")
    print("=" * 60)

    # Initialize chatbot
    chatbot = IntelligentChatbot("config.yml")

    # Test queries for different data sources
    test_queries = [
        {
            "query": "qual è l'indirizzo di MET",
            "expected_source": "companies_detailed",
            "expected_info": "address, pec_email",
        },
        {
            "query": "qual è il sito web di MET",
            "expected_source": "company_websites",
            "expected_info": "official_website, confidence_score",
        },
        {
            "query": "quali sono i contatti di MET",
            "expected_source": "website_intelligence",
            "expected_info": "phone_numbers, info_emails, addresses",
        },
        {
            "query": "quali certificazioni ha MET",
            "expected_source": "chamber_analysis",
            "expected_info": "certifications, soa_attestations",
        },
        {
            "query": "qual è il fatturato di MET",
            "expected_source": "companies_detailed",
            "expected_info": "latest_revenue, latest_employees",
        },
        {
            "query": "dimmi tutto su MET",
            "expected_source": "all",
            "expected_info": "comprehensive data from all sources",
        },
    ]

    results = []

    for i, test in enumerate(test_queries, 1):
        print(f"\n[TEST {i}/6] {test['query']}")
        print(f"Expected source: {test['expected_source']}")
        print(f"Expected info: {test['expected_info']}")
        print("-" * 40)

        try:
            # Get query analysis
            query_analysis = chatbot.analyze_query_ollama(test["query"])
            print(f"Query analysis: {query_analysis}")

            # Search for companies
            found_companies = chatbot.search_companies(
                query_analysis.get("company_identifiers", []),
                query_analysis.get("search_terms", []),
            )
            print(f"Found companies: {list(found_companies.keys())}")

            # Extract relevant data
            relevant_data = chatbot.extract_relevant_data(
                found_companies,
                query_analysis.get("datasets_needed", []),
                query_analysis.get("information_type", []),
            )

            print(
                f"Relevant data sources: {list(relevant_data.get('MET', {}).keys()) if 'MET' in relevant_data else 'None'}"
            )

            # Generate response
            response = chatbot.process_query(test["query"])

            print(f"RESPONSE:\n{response}")

            # Map unified data fields to legacy source names for comparison
            source_mapping = {
                "companies_detailed": [
                    "financial_data",
                    "contact_information",
                    "company_key",
                    "company_name",
                    "legal_form",
                    "tax_code",
                    "vat_number",
                ],
                "company_websites": ["website_data", "company_key"],
                "website_intelligence": [
                    "website_intelligence",
                    "contact_information",
                    "company_key",
                ],
                "chamber_analysis": ["certifications", "company_key"],
                "all": [
                    "company_key",
                    "company_name",
                    "legal_form",
                    "tax_code",
                    "vat_number",
                    "financial_data",
                    "contact_information",
                    "website_data",
                    "certifications",
                    "chamber_url",
                    "data_sources",
                    "last_updated",
                    "website_intelligence",
                ],
            }

            found_sources = (
                list(relevant_data.get("MET", {}).keys())
                if "MET" in relevant_data
                else []
            )

            # Check if expected source is covered by found sources
            expected_fields = source_mapping.get(test["expected_source"], [])
            sources_match = (
                test["expected_source"] == "all" and len(found_sources) >= 5
            ) or any(field in found_sources for field in expected_fields)

            # Analyze response quality
            test_result = {
                "query": test["query"],
                "expected_source": test["expected_source"],
                "found_sources": found_sources,
                "sources_match": sources_match,
                "response_length": len(response),
                "contains_specific_info": any(
                    keyword in response.lower()
                    for keyword in [
                        "perry johnson",
                        "bolzano",
                        "met.it",
                        "945157900",
                        "945.157.900",
                        "albo nazionale",
                        "marie curie",
                        "pcert.postecert.it",
                    ]
                ),
                "response": response[:200] + "..." if len(response) > 200 else response,
            }

            results.append(test_result)

        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"query": test["query"], "error": str(e)})

        print("=" * 60)

    # Summary
    print("\nTEST RESULTS SUMMARY:")
    print("=" * 60)

    for i, result in enumerate(results, 1):
        if "error" in result:
            print(f"[{i}] ❌ FAILED: {result['query']} - {result['error']}")
        else:
            sources_match = result.get("sources_match", False)
            has_info = result["contains_specific_info"]
            status = "✅ PASSED" if sources_match and has_info else "⚠️ PARTIAL"

            print(f"[{i}] {status}: {result['query']}")
            print(f"    Expected: {result['expected_source']}")
            print(f"    Found: {result['found_sources']}")
            print(f"    Sources match: {sources_match}")
            print(f"    Has specific info: {has_info}")
            print(f"    Response length: {result['response_length']} chars")

    return results


if __name__ == "__main__":
    results = test_data_source_retrieval()

    # Save detailed results
    with open("chatbot_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Detailed test results saved to: chatbot_test_results.json")
