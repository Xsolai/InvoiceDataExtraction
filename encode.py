import base64

def encode_pdf_to_base64(pdf_path, output_text_file):
    try:
        # Open the PDF file in binary read mode
        with open(pdf_path, 'rb') as pdf_file:
            # Read the content of the file
            pdf_content = pdf_file.read()
            # Encode the content to Base64
            encoded_content = base64.b64encode(pdf_content)
            # Decode the Base64 bytes to a string for writing to the text file
            encoded_string = encoded_content.decode('utf-8')
        
        # Write the Base64 string to a text file
        with open(output_text_file, 'w') as text_file:
            text_file.write(encoded_string)
        
        print(f"PDF file encoded and written to {output_text_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
pdf_path = 'testfiles\Calibration Invoice.pdf'  # Path to your PDF file
output_text_file = 'testfiles\encoded_pdf.txt'  # Path to your output text file
encode_pdf_to_base64(pdf_path, output_text_file)
