# Universal Invoice Processing API

## Description

The **Universal Invoice Processing API** is a powerful tool built with FastAPI that extracts structured data from invoices of any format. Leveraging OpenAI's GPT API, this system can handle various invoice formats, decode base64-encoded files, process PDFs, and extract critical invoice details such as metadata, line items, totals, payment slips, and unstructured content.

---

## Features

- **Base64-Encoded File Support**: Accepts base64-encoded files (currently supports PDF format).
- **Invoice Parsing**: Extracts structured data such as vendor details, customer details, line items, totals, and more.
- **Customizable JSON Schema**: Handles additional fields dynamically using `extra_fields`.
- **PDF to Image Conversion**: Processes multi-page PDFs using `pdf2image` and converts the first page to an image.
- **Integration with OpenAI's GPT API**: Sends the image to the GPT model for data extraction.
- **Error Handling**: Handles invalid inputs, unsupported formats, and API errors gracefully.
- **Temporary File Management**: Saves files locally for processing and ensures cleanup after use.

---

## Technologies Used

- **Python 3.9+**
- **FastAPI** for building the API
- **Pillow** for image processing
- **pdf2image** for PDF-to-image conversion
- **OpenAI API** for invoice data extraction
- **Pydantic** for data validation
- **Uvicorn** for running the server

---

## Installation

### Prerequisites

1. Install Python 3.9+.
2. Install `poppler` for PDF-to-image conversion:
   - [Poppler for Windows](https://blog.alivate.com.au/poppler-windows/)
   - Install `poppler-utils` via your package manager on Linux.

### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git
   cd <your-repo>
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Create a `.env` file in the root directory:
     ```env
     OPENAI_API_KEY=<your-openai-api-key>
     ```
   - Replace `<your-openai-api-key>` with your OpenAI API key.

5. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

---

## API Endpoints

### **POST /extract**
Extracts structured invoice data from a base64-encoded file.

#### **Request**

- **URL**: `/extract`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Body**:
  ```json
  {
    "data": "<base64-encoded-file>",
    "ext": "pdf"
  }
  ```

#### **Response**

- **200 OK**: Returns structured invoice data.
  ```json
  {
    "document_type": "invoice",
    "invoice_metadata": { ... },
    "line_items": [ ... ],
    "totals": { ... },
    "payment_slip": { ... },
    "unstructured_content": { ... },
    "extra_fields": { ... }
  }
  ```

- **400 Bad Request**: Invalid file extension or base64 data.
- **500 Internal Server Error**: Errors during file processing or API communication.

---

## How It Works

1. **Input**:
   - Accepts a base64-encoded file and its extension (`ext`).
2. **Processing**:
   - Validates the file extension (`pdf` only).
   - Converts the PDF to an image (first page only).
   - Compresses and encodes the image in base64.
3. **Integration**:
   - Sends the base64-encoded image to OpenAI's GPT API.
   - Generates a detailed prompt to extract invoice data.
4. **Output**:
   - Returns structured JSON containing invoice metadata, line items, totals, and unstructured content.

---

## Example Usage

### **Request**
```bash
curl -X POST "http://localhost:8000/extract" \
-H "Content-Type: application/json" \
-d '{
  "data": "<base64-encoded-pdf>",
  "ext": "pdf"
}'
```

### **Response**
```json
{
  "document_type": "invoice",
  "invoice_metadata": {
    "invoice_number": "EC/092024/0016",
    "invoice_date": "01-10-2024",
    "due_date": "03-10-2024",
    "currency": "PKR",
    "vendor_details": { ... },
    "customer_details": { ... },
    "additional_metadata": { ... }
  },
  "line_items": [
    { "description": "Usage Charges", "total": 800.0, ... },
    { "description": "One-Time Charges", "total": 267.0, ... }
  ],
  "totals": {
    "previous_balance": 266546.34,
    "current_charges": 1992.12,
    "grand_total": 270737.67
  },
  "payment_slip": {
    "payment_amount": 270737.67,
    "payment_due_date": "03-11-2024"
  }
}
```

---

## Error Handling

- **Invalid Base64 Data**:
  - Returns a `400 Bad Request` with the message: `"Invalid base64-encoded file data."`
- **Unsupported File Extension**:
  - Returns a `400 Bad Request` with the message: `"Unsupported file extension. Allowed extensions: pdf."`
- **Empty or Corrupt PDF**:
  - Returns a `500 Internal Server Error` with the message: `"Failed to process the uploaded PDF."`
- **GPT API Errors**:
  - Returns a `500 Internal Server Error` with detailed error messages from the GPT API.

---

## Project Structure

```plaintext
.
├── main.py              # FastAPI application code
├── requirements.txt     # Project dependencies
├── .env                 # Environment variables (ignored by Git)
├── uploads/             # Temporary directory for uploaded files
└── README.md            # Project documentation
```

---

## Future Enhancements

1. **Multi-Page PDFs**:
   - Extend support for extracting data from all pages.
2. **Enhanced Schema**:
   - Add more fields for domain-specific invoices.
3. **Cloud Storage Integration**:
   - Use S3 or similar services for large file uploads.
4. **Multi-Language Support**:
   - Enhance the GPT prompt to process invoices in various languages.

---

## Contributing

1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature/<feature-name>
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add <feature-name>"
   ```
4. Push to your branch:
   ```bash
   git push origin feature/<feature-name>
   ```
5. Open a pull request.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
