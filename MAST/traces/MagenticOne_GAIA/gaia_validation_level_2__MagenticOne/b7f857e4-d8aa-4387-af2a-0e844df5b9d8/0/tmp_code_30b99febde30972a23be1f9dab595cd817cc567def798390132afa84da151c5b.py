import cv2
from PIL import Image
import pytesseract

# Load the image using OpenCV
image_path = "/workspace/b7f857e4-d8aa-4387-af2a-0e844df5b9d8.png"
image = cv2.imread(image_path)

# Convert to grayscale for easier processing
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# Use histogram equalization to improve the contrast
enhanced = cv2.equalizeHist(gray)

# Save the processed image
processed_image_path = "/workspace/processed.png"
cv2.imwrite(processed_image_path, enhanced)

# Perform OCR using pytesseract
text = pytesseract.image_to_string(Image.open(processed_image_path))

# Save to a text file
with open("/workspace/output.txt", "w") as text_file:
    text_file.write(text)

print("OCR text extraction complete. Saved to output.txt.")
