import pytesseract
from PIL import Image
import cv2
import numpy as np

# Path to the image
image_path = '/workspace/cca530fc-4052-43b2-b130-b30968d8aa44.png'

def preprocess_image(image_path):
    # Read image using OpenCV
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    # Apply Gaussian blur to the image
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    # Use thresholding to convert image to binary
    _, binary_image = cv2.threshold(blurred, 150, 255, cv2.THRESH_BINARY_INV)
    return binary_image

def extract_text_from_image(image_path):
    # Preprocess the image for better OCR results
    preprocessed_image = preprocess_image(image_path)
    # Convert image to PIL format
    pil_image = Image.fromarray(preprocessed_image)
    # Use Tesseract to do OCR on the image
    text = pytesseract.image_to_string(pil_image, config='--psm 6')
    return text

# Extract text from the image
extracted_text = extract_text_from_image(image_path)

# Output the extracted text
print(extracted_text)
