import uuid
from fastapi import FastAPI, HTTPException,Form
from pydantic import BaseModel, ValidationError
from typing import List, Optional, Dict
import openai
import base64
import logging
import os
from dotenv import load_dotenv
from PIL import Image
import io
import json
import requests
from pdf2image import convert_from_path
from typing import Any, Union
# Load environment variables
load_dotenv()

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OpenAI API key is missing. Please set it in the environment variables.")

openai.api_key = OPENAI_API_KEY

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the JSON schema
from typing import Any, Dict, List, Optional, Union

class VendorDetails(BaseModel):
    name: Optional[str]
    address: Optional[str]
    contact: Optional[str]
    tax_id: Optional[str]
    extra_fields: Optional[Dict[str, Any]] = {}

class CustomerDetails(BaseModel):
    name: Optional[str]
    address: Optional[str]
    contact: Optional[str]
    tax_id: Optional[str]
    extra_fields: Optional[Dict[str, Any]] = {}

class LineItem(BaseModel):
    transaction_date: Optional[str]
    description: Optional[str]
    transaction_type: Optional[str]
    quantity: Optional[float]
    unit: Optional[str]
    unit_price: Optional[float]
    tax_rate: Optional[float]
    tax_amount: Optional[float]
    subtotal: Optional[float]
    total: Optional[float]
    status: Optional[str]
    sub_items: Optional[List[Any]] = []  # Allow empty sub-items
    extra_details: Optional[Union[str, Dict[str, Any]]] = ""  # Default to an empty string or dictionary
    extra_fields: Optional[Dict[str, Any]] = {}

# Define BankDetails model
class BankDetails(BaseModel):
    account_name: Optional[str]
    account_number: Optional[str]
    bank_name: Optional[str]
    extra_fields: Optional[Dict[str, Any]] = {}

# Define PaymentSlip model
class PaymentSlip(BaseModel):
    payment_amount: Optional[float]
    payment_due_date: Optional[str]
    reference_number: Optional[str]
    bank_details: Optional[BankDetails] = None
    extra_fields: Optional[Dict[str, Any]] = {}

class Totals(BaseModel):
    previous_balance: Optional[float]
    current_charges: Optional[float]
    partial_totals: Optional[List[Any]] = []  # Allow partial totals to be an empty list
    taxes: Optional[List[Any]] = []  # Allow taxes to be an empty list
    discounts: Optional[float]
    adjustments: Optional[float]
    grand_total: Optional[float]
    amount_in_words: Optional[str]
    currency: Optional[str]
    extra_fields: Optional[Dict[str, Any]] = {}

class InvoiceMetadata(BaseModel):
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    due_date: Optional[str]
    currency: Optional[str]
    vendor_details: VendorDetails
    customer_details: CustomerDetails
    additional_metadata: Optional[Dict[str, Any]] = {}  # Allow additional metadata to be optional
    extra_fields: Optional[Dict[str, Any]] = {}

class InvoiceData(BaseModel):
    document_type: Optional[str]
    invoice_metadata: InvoiceMetadata
    line_items: List[LineItem]
    totals: Totals
    payment_slip: Optional[PaymentSlip] = None
    unstructured_content: Optional[Union[str, Dict[str, Any]]] = ""  # Allow either string or dictionary
    extra_fields: Optional[Dict[str, Any]] = {}


# Initialize FastAPI app
app = FastAPI(
    title="Universal Invoice Processing API",
    description="Extract structured data from invoices of any format using OpenAI GPT.",
    version="1.0.0",
)

# Define the input schema
class InvoiceRequest(BaseModel):
    data: str  # Base64 encoded file content
    ext: str   # File extension

@app.post("/extract", response_model=InvoiceData)
async def extract_invoice(request: InvoiceRequest):
    """
    Extract structured data from an uploaded invoice image.
    Save the image locally for processing and delete it afterward.
    """
    try:
        # Normalize and validate file extension
        ext = request.ext.lower().strip('.')
        allowed_extensions = ['pdf']
        if ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension. Allowed extensions: {', '.join(allowed_extensions)}")

        # Decode base64 string
        try:
            file_data = base64.b64decode(request.data)
        except (base64.binascii.Error, TypeError) as decode_error:
            logger.error(f"Invalid base64 data: {decode_error}")
            raise HTTPException(status_code=400, detail="Invalid base64-encoded file data.")

        # Ensure the upload directory exists
        upload_dir = "./uploads"
        os.makedirs(upload_dir, exist_ok=True)

        # Generate unique filename with correct extension
        file_path = f"{upload_dir}/{uuid.uuid4()}.{ext}"

        # Save the decoded file
        with open(file_path, "wb") as f:
            f.write(file_data)

        # Convert PDF to image
        try:
            images = convert_from_path(file_path, poppler_path=os.path.abspath(r'poppler-24.08.0\Library\bin'))
            if not images:
                raise ValueError("No pages found in the uploaded PDF.")
            image = images[0]  # Use the first page
            image = image.resize((800, 800))  # Resize to reduce size
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=70)
            encoded_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Error converting PDF to image: {e}")
            raise HTTPException(status_code=500, detail="Failed to process the uploaded PDF.")

        # Send the base64-encoded image to the GPT API
        try:
            response = call_gpt_api(encoded_image)
        except Exception as api_error:
            logger.error(f"Error calling GPT API: {api_error}")
            raise HTTPException(status_code=500, detail="An error occurred while communicating with the GPT API.")

        if "error" in response:
            logger.error(f"GPT API returned an error: {response['error']}")
            raise HTTPException(status_code=500, detail=response["error"])

        # Parse and return the GPT response
        try:
            invoice_data = parse_gpt_response(response)
        except Exception as parse_error:
            logger.error(f"Error parsing GPT response: {parse_error}")
            raise HTTPException(status_code=500, detail="Failed to parse the GPT API response.")
        
        return invoice_data

    finally:
        # Ensure the local file is deleted after processing
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Temporary file {file_path} deleted successfully.")
        except Exception as cleanup_error:
            logger.error(f"Error deleting temporary file {file_path}: {cleanup_error}")

def generate_prompt(image_base64: str) -> str:
    """
    Generate a detailed prompt for GPT to extract invoice data universally.
    """
    return """
You are an expert in invoice data extraction. Analyze the following base64-encoded image of an invoice and extract data into this structured JSON format:

JSON Structure:
1. Use the predefined sections (e.g., "invoice_metadata", "line_items", "totals").
2. Include any unknown or additional fields in a dedicated "extra_fields" dictionary at the appropriate level.
3. Ensure the response is a **valid JSON object**.
4. In line items add all line items ,for simplicity in schema there is one but we need all to be added in the array of line items

Schema:
{
  "document_type": "invoice",
  "invoice_metadata": {
    "invoice_number": "string",
    "invoice_date": "string",
    "due_date": "string",
    "currency": "string",
    "vendor_details": {
      "name": "string",
      "address": "string",
      "contact": "string",
      "tax_id": "string",
      "extra_fields": {"key": "value"  // Additional vendor-specific fields}
    },
    "customer_details": {
      "name": "string",
      "address": "string",
      "contact": "string",
      "tax_id": "string",
      "extra_fields": {
        "key": "value"  // Additional customer-specific fields
      }
    },
    "additional_metadata": {
      "payment_terms": "string",
      "reference_numbers": ["string"],
      "notes": "string",
      "extra_fields": {
        "key": "value"  // Any other metadata fields
      }
    }
  },
  "line_items": [
    {
      "transaction_date": "string",
      "description": "string",
      "transaction_type": "string",
      "quantity": "number",
      "unit": "string",
      "unit_price": "number",
      "tax_rate": "number",
      "tax_amount": "number",
      "subtotal": "number",
      "total": "number",
      "status": "string",
      "sub_items": [
        {
          "description": "string",
          "quantity": "number",
          "unit_price": "number",
          "total": "number"
        }
      ],
      "extra_fields": {
        "key": "value"  // Additional line-item-specific fields
      }
    }
  ],
  "totals": {
    "previous_balance": "number",
    "current_charges": "number",
    "partial_totals": [
      {
        "type": "string",
        "amount": "number"
      }
    ],
    "taxes": [
      {
        "type": "string",
        "amount": "number",
        "rate": "number"
      }
    ],
    "discounts": "number",
    "adjustments": "number",
    "grand_total": "number",
    "amount_in_words": "string",
    "currency": "string",
    "extra_fields": {
      "key": "value"  // Additional totals-related fields
    }
  },
  "payment_slip": {
    "payment_amount": "number",
    "payment_due_date": "string",
    "reference_number": "string",
    "bank_details": {
      "account_name": "string",
      "account_number": "string",
      "bank_name": "string",
      "extra_fields": {
        "key": "value"  // Additional bank-related fields
      }
    },
    "extra_fields": {
      "key": "value"  // Additional payment-slip-specific fields
    }
  },
  "unstructured_content": {
    "raw_text": "string",
    "notes": "string",
    "extra_fields": {
      "key": "value"  // Any other unstructured content fields
    }
  },
  "extra_fields": {
    "key": "value"  // Any top-level unknown fields
  }
}
"""+f"""
Image (Base64):
{image_base64}

Ensure all relevant details are captured. Gracefully handle missing fields with 'null' values. only json response is required . STRICTLY do not return any other text with json.
""".strip()

def call_gpt_api(image_base64: str) -> dict:
    """
    Call OpenAI GPT API to process the invoice image and extract data.
    """
    try:
        prompt = generate_prompt(image_base64)

        # Convert the image to a base64-encoded string
        encoded_image = image_base64
        # Construct the payload for the OpenAI API request
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI specialized in invoice data extraction."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4095
        }

        # Send the request to the OpenAI API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        # Handle the response from the OpenAI API
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"OpenAI API Error: {response.text}")

        response_json = response.json()

        # Extract the assistant's message from the response
        assistant_message = response_json['choices'][0]['message']['content']
        assistant_message = assistant_message.strip().lstrip('```json').rstrip('```').replace("“", '"').replace("”", '"')
        print(assistant_message)
        return assistant_message

    except Exception as e:
        logger.error(f"Error calling GPT API: {e}")
        return {"error": str(e)}

def parse_gpt_response(response: str) -> InvoiceData:
    """
    Parse the JSON response from GPT into the InvoiceData model with enhanced type handling and normalization.
    Fixes duplicate `bank_details` keyword argument issue.
    """
    try:
        logger.info("Parsing the JSON response from GPT.")
        invoice_dict = json.loads(response)

        # Preprocess JSON to handle commas in numbers and normalize invalid values
        def preprocess_json(json_str):
            import re
            # Remove commas from numbers
            json_str = re.sub(r'(?<=\d),(?=\d)', '', json_str)
            return json_str

        preprocessed_response = preprocess_json(response)
        invoice_dict = json.loads(preprocessed_response)

        # Normalize "null" strings and other invalid values
        def normalize_nulls(data):
            if isinstance(data, dict):
                return {k: normalize_nulls(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [normalize_nulls(v) for v in data]
            elif data in ["null", "NA"]:  # Convert "null" and "NA" strings to None
                return None
            return data

        normalized_invoice_dict = normalize_nulls(invoice_dict)
        logger.debug(f"Normalized JSON response: {normalized_invoice_dict}")

        logger.info("Successfully parsed JSON response. Checking for unknown fields.")
        unknown_top_fields = [
            key for key in normalized_invoice_dict.keys() if key not in InvoiceData.model_fields
        ]
        if unknown_top_fields:
            logger.warning(f"Unknown top-level fields detected: {unknown_top_fields}")

        # Normalize `extra_details` in line_items
        normalized_line_items = []
        for item in normalized_invoice_dict.get("line_items", []):
            logger.debug(f"Processing line item: {item}")
            extra_fields = item.pop("extra_fields", {})
            if "extra_details" not in item or item["extra_details"] is None:
                item["extra_details"] = ""
            normalized_line_items.append(LineItem(**item, extra_fields=extra_fields))
        logger.debug(f"Final normalized line items: {normalized_line_items}")

        # Normalize `extra_fields` in metadata
        metadata = normalized_invoice_dict.get("invoice_metadata", {})
        metadata_extra_fields = metadata.pop("extra_fields", {})

        # Normalize `totals` and extract `extra_fields`
        totals = normalized_invoice_dict.get("totals", {})
        totals_extra_fields = totals.pop("extra_fields", {})  # Extract and remove extra_fields

        # Normalize `payment_slip` and extract `extra_fields`
        payment_slip = normalized_invoice_dict.get("payment_slip", {})
        payment_slip_extra_fields = payment_slip.pop("extra_fields", {})  # Extract `extra_fields`
        bank_details = payment_slip.pop("bank_details", {})  # Extract `bank_details`
        bank_details_extra_fields = bank_details.pop("extra_fields", {})  # Extract `extra_fields` from bank_details

        # Normalize `reference_numbers` in additional_metadata to ensure it's a list
        additional_metadata = metadata.get("additional_metadata", {})
        if isinstance(additional_metadata.get("reference_numbers"), str):
            additional_metadata["reference_numbers"] = [additional_metadata["reference_numbers"]]
        if not isinstance(additional_metadata.get("extra_fields"), dict):
            additional_metadata["extra_fields"] = {}

        # Map data to models
        invoice_data = InvoiceData(
            document_type=normalized_invoice_dict.get("document_type"),
            invoice_metadata=InvoiceMetadata(
                **metadata,
                extra_fields=metadata_extra_fields
            ),
            line_items=normalized_line_items,
            totals=Totals(
                **totals,  # Pass all fields except `extra_fields`
                extra_fields=totals_extra_fields
            ),
            payment_slip=PaymentSlip(
                **payment_slip,  # Pass all fields except `bank_details`
                bank_details=BankDetails(
                    **bank_details,  # Pass all fields explicitly
                    extra_fields=bank_details_extra_fields  # Explicitly add `extra_fields`
                ),
                extra_fields=payment_slip_extra_fields  # Explicitly add `extra_fields`
            ) if normalized_invoice_dict.get("payment_slip") else None,
            unstructured_content=normalized_invoice_dict.get("unstructured_content", ""),
            extra_fields={
                k: v for k, v in normalized_invoice_dict.items() if k not in InvoiceData.model_fields
            }
        )
        logger.info("Successfully mapped GPT response to InvoiceData model.")
        return invoice_data

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from GPT: {e}")
        raise HTTPException(status_code=500, detail="Received invalid JSON from GPT.")
    except ValidationError as e:
        logger.error(f"Validation error while mapping GPT response: {e}")
        raise HTTPException(status_code=422, detail="Validation error in GPT response data.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while parsing GPT response: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while parsing GPT response.")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
