import os
import logging

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.data.commodity_groups import get_commodity_list

# Setup logging
logger = logging.getLogger(__name__)

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Document extraction chain
extraction_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a procurement document extraction assistant. Extract structured information from vendor offer documents.
Always return valid JSON with these fields:
- vendor_name: string (the SELLER - found in the letterhead/header, usually on the FIRST line, often with their full address. This is the company SENDING the offer, NOT the recipient. do not include the adress just name of the company)
- vat_id: string (Umsatzsteuer-Identifikationsnummer)
- department: string (the BUYER's company name - found in the recipient address block BELOW the letterhead. This is who the offer is addressed TO. Extract ONLY the company name or department, no person names or addresses)
- title: string (brief description of the offer)
- order_lines: array of objects with: description, unit_price (number), amount (number), unit, total_price (number)
  IMPORTANT for order_lines:
  - For the total of an order line use the "Gesamt" column (after any discounts/Rabatt are applied), NOT the base unit price
- total_cost: number
  IMPORTANT for total_cost:
  - Always use the Endsumme/Gesamtsumme/Bruttosumme (final total INCLUDING VAT/MwSt/USt)
  - Do NOT use Nettosumme/net sum
  - Do NOT calculate from order_lines - use the exact final total shown in the document
- suggested_commodity_group_id: string (pick the most appropriate from the commodity groups list)

IMPORTANT for vat_id:
- Only extract a VAT ID if it is explicitly labeled (e.g., "USt-IdNr", "USt-Id", "Id-Nr", "UID")
- The VAT ID should typically start with a 2-letter country code (A–Z) followed by 2–12 alphanumeric characters.
- The vat_id must be taken from a SINGLE line only; stop extraction at the first line break and do NOT include any text or numbers from following lines
- Do NOT guess or use other numeric IDs (invoice numbers, customer IDs, IBAN, order numbers)"""),
    ("human", """Extract procurement information from this vendor offer document.

Commodity Groups:
{commodity_list}

Document text:
{document_text}

Return only valid JSON.""")
])
#- Only extract a VAT ID that starts with DE
extraction_chain = extraction_prompt | llm | JsonOutputParser()


# Commodity suggestion chain
suggestion_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a procurement categorization assistant. Suggest the most appropriate commodity group for procurement requests.
Always return valid JSON with: commodity_group_id and reason."""),
    ("human", """Based on this procurement request, suggest the single most appropriate commodity group.

Request details:
- Title: {title}
- Vendor: {vendor_name}
- Items: {order_lines}

Available Commodity Groups:
{commodity_list}

Return only JSON with: {{"commodity_group_id": "XXX", "reason": "brief explanation"}}""")
])

suggestion_chain = suggestion_prompt | llm | JsonOutputParser()


def extract_document(text: str) -> dict:
    """Extract procurement data from document text using LangChain"""
    # Uncomment below for debugging:
    # print("=" * 50)
    # print("DOCUMENT TEXT BEING SENT TO AI:")
    # print("=" * 50)
    # print(text[:3000] if len(text) > 3000 else text)
    # print("=" * 50)

    result = extraction_chain.invoke({
        "commodity_list": get_commodity_list(),
        "document_text": text
    })

    # Uncomment below for debugging:
    # print("AI EXTRACTION RESULT:")
    # print(f"vendor_name: {result.get('vendor_name')}")
    # print(f"department: {result.get('department')}")
    # print("=" * 50)

    return result


def suggest_commodity_group(title: str, vendor_name: str, order_lines: list) -> dict:
    """Suggest commodity group based on request details"""
    return suggestion_chain.invoke({
        "title": title,
        "vendor_name": vendor_name,
        "order_lines": str(order_lines),
        "commodity_list": get_commodity_list()
    })
