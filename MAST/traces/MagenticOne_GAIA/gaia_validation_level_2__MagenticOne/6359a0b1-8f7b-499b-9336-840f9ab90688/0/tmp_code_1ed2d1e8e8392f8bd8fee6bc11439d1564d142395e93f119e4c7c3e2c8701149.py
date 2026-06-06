from PIL import Image, ImageEnhance, ImageOps
import pytesseract
import sys

try:
    # Path to the image file
    image_path = "6359a0b1-8f7b-499b-9336-840f9ab90688.png"

    # Open the image with PIL
    img = Image.open(image_path)

    # Convert the image to grayscale
    img_gray = ImageOps.grayscale(img)

    # Enhance the contrast of the image
    enhancer = ImageEnhance.Contrast(img_gray)
    img_contrast = enhancer.enhance(2)  # Adjust the factor as needed

    # Use pytesseract to perform OCR on the processed image
    extracted_text = pytesseract.image_to_string(img_contrast)

    # Print the extracted text
    print("Extracted Text from Image:")
    print(extracted_text)

except Exception as e:
    print(f"An error occurred: {e}", file=sys.stderr)
