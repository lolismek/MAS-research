import pytesseract
from PIL import Image

# Load the image from a file
image_path = 'b7f857e4-d8aa-4387-af2a-0e844df5b9d8.png'
image = Image.open(image_path)

# Perform OCR using pytesseract
extracted_text = pytesseract.image_to_string(image)

# Save the extracted text to a file
with open('extracted_script.py', 'w') as file:
    file.write(extracted_text)

print("Text extraction complete. The text has been saved to 'extracted_script.py'.")
