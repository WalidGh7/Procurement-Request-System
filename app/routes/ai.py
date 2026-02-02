import io
import os
import base64
import logging
import fitz  # PyMuPDF

from fastapi import APIRouter, UploadFile, File, HTTPException
import PyPDF2
from mistralai import Mistral

from app.services.ai_service import extract_document, suggest_commodity_group

# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ai"])

# Maximum PDF file size: 10 MB
MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024

# Initialize Mistral client for OCR
mistral_client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))


async def extract_text_with_ocr(pdf_content: bytes) -> str:
    """Extract text from scanned PDF using Mistral OCR (Pixtral)"""
    # Convert PDF to images using PyMuPDF (no external dependencies needed)
    try:
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
    except Exception as e:
        raise Exception(f"Failed to open PDF: {str(e)}")

    all_text = []

    # Process each page
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]

        # Render page to image at 200 DPI
        pix = page.get_pixmap(dpi=200)

        # Convert to PNG bytes
        img_bytes = pix.tobytes("png")

        # Convert to base64
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        # Use Mistral Pixtral for OCR on this page
        response = mistral_client.chat.complete(
            model="pixtral-12b-2409",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Extract all text from this page (page {page_num + 1}). For tables, preserve the structure using | as column separator and include column headers. Example format for tables: | Pos | Menge | Einheit | Preis/Einh € | Gesamt € |. Return only the extracted text without any commentary."
                        },
                        {
                            "type": "image_url",
                            "image_url": f"data:image/png;base64,{img_base64}"
                        }
                    ]
                }
            ]
        )

        all_text.append(response.choices[0].message.content)

    pdf_document.close()

    # Combine all pages
    return "\n\n=== PAGE BREAK ===\n\n".join(all_text)


@router.post("/extract-document")
async def extract_document_endpoint(file: UploadFile = File(...)):
    """Extract procurement info from uploaded PDF using AI (uses both PyPDF2 + OCR for best results)"""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    content = await file.read()

    # Validate file size
    if len(content) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB"
        )

    # Strategy: PyPDF2 first, OCR only if extraction is poor quality

    # 1. Try PyPDF2 first (fast, free, good for digital text)
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
    pypdf_text = ""
    for page in pdf_reader.pages:
        pypdf_text += page.extract_text() or ""

    logger.info(f"PyPDF2 extracted {len(pypdf_text)} characters")

    # 2. Try extraction with PyPDF2 text
    pypdf_result = None
    if pypdf_text.strip():
        try:
            pypdf_result = extract_document(pypdf_text)
            logger.info(f"PyPDF2 extraction result: VAT ID = {pypdf_result.get('vat_id', 'MISSING')}")
        except Exception as e:
            logger.error(f"PyPDF2 AI extraction failed: {str(e)}")

    # 3. Check if extraction quality is poor (missing critical fields)
    needs_ocr = False
    if not pypdf_result:
        logger.info("No PyPDF2 result, will use OCR")
        needs_ocr = True
    else:
        # Check for missing critical fields
        vat_id = str(pypdf_result.get('vat_id', '')).strip()
        vendor_name = str(pypdf_result.get('vendor_name', '')).strip()
        department = str(pypdf_result.get('department', '')).strip()
        title = str(pypdf_result.get('title', '')).strip()
        order_lines = pypdf_result.get('order_lines', [])

        if not vat_id:
            logger.info("VAT ID missing, will use OCR")
            needs_ocr = True
        elif not vendor_name:
            logger.info("Vendor name missing, will use OCR")
            needs_ocr = True
        elif not department:
            logger.info("Department missing, will use OCR")
            needs_ocr = True
        elif not title:
            logger.info("Title missing, will use OCR")
            needs_ocr = True
        elif not order_lines or len(order_lines) == 0:
            logger.info("No order lines found, will use OCR")
            needs_ocr = True

    # 4. Use OCR only if necessary
    ocr_result = None
    if needs_ocr:
        try:
            logger.info("Starting OCR extraction with Mistral Pixtral (critical fields missing)...")
            ocr_text = await extract_text_with_ocr(content)
            logger.info(f"OCR extracted {len(ocr_text)} characters")

            ocr_result = extract_document(ocr_text)
            logger.info(f"OCR extraction result: VAT ID = {ocr_result.get('vat_id', 'MISSING')}")
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            if not pypdf_result:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not extract text from PDF. PyPDF2 and OCR both failed."
                )

    # 5. Prepare results for merging
    results = []
    if pypdf_result:
        results.append(('pypdf', pypdf_result))
    if ocr_result:
        results.append(('ocr', ocr_result))

    if not results:
        raise HTTPException(status_code=400, detail="Could not extract data from PDF")

    # 4. Merge results intelligently - prefer non-empty, longer, more complete values
    if len(results) == 1:
        return results[0][1]

    # Merge PyPDF2 and OCR results
    pypdf_result = next((r for src, r in results if src == 'pypdf'), {})
    ocr_result = next((r for src, r in results if src == 'ocr'), {})

    merged = {}

    # For each field, choose the better value
    all_fields = set(pypdf_result.keys()) | set(ocr_result.keys())

    for field in all_fields:
        pypdf_val = pypdf_result.get(field, '')
        ocr_val = ocr_result.get(field, '')

        # For order_lines, prefer the one with more items
        if field == 'order_lines':
            pypdf_lines = pypdf_val if isinstance(pypdf_val, list) else []
            ocr_lines = ocr_val if isinstance(ocr_val, list) else []
            merged[field] = pypdf_lines if len(pypdf_lines) >= len(ocr_lines) else ocr_lines
        # For vendor_name and department, prefer OCR (better document layout understanding)
        elif field in ('vendor_name', 'department'):
            ocr_str = str(ocr_val).strip() if ocr_val else ''
            pypdf_str = str(pypdf_val).strip() if pypdf_val else ''
            # Prefer OCR if available, fallback to PyPDF2
            merged[field] = ocr_val if ocr_str else pypdf_val
        # For other fields, prefer non-empty and longer values
        else:
            pypdf_str = str(pypdf_val).strip() if pypdf_val else ''
            ocr_str = str(ocr_val).strip() if ocr_val else ''

            # Prefer whichever is non-empty and longer
            if not pypdf_str and ocr_str:
                merged[field] = ocr_val
            elif not ocr_str and pypdf_str:
                merged[field] = pypdf_val
            elif len(ocr_str) > len(pypdf_str):
                merged[field] = ocr_val
            else:
                merged[field] = pypdf_val

    logger.info(f"Final merged result: VAT ID = {merged.get('vat_id', 'MISSING')}")
    return merged


@router.post("/suggest-commodity-group")
async def suggest_commodity_group_endpoint(data: dict):
    """Suggest the best commodity group based on request details"""
    return suggest_commodity_group(
        title=data.get('title', ''),
        vendor_name=data.get('vendor_name', ''),
        order_lines=data.get('order_lines', [])
    )
