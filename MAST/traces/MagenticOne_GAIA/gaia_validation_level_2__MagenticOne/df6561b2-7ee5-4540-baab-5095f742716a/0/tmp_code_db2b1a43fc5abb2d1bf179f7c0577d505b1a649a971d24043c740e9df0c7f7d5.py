import cv2
import pytesseract
import numpy as np

# Ensure you have Tesseract installed and configured in your environment
pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"  # Update this path to your Tesseract binary if needed

def extract_colored_numbers(image, lower_bound, upper_bound):
    # Convert BGR to HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Create a mask for the given color range
    mask = cv2.inRange(hsv, lower_bound, upper_bound)
    # Bitwise-AND mask and original image
    masked_image = cv2.bitwise_and(image, image, mask=mask)
    # Convert to grayscale
    gray = cv2.cvtColor(masked_image, cv2.COLOR_BGR2GRAY)
    # Use OCR to extract text
    ocr_result = pytesseract.image_to_string(gray, config='--psm 6')
    # Extract numbers
    numbers = [int(s) for s in ocr_result.split() if s.isdigit()]
    return numbers

def main():
    # Load image
    image = cv2.imread('/workspace/df6561b2-7ee5-4540-baab-5095f742716a.png')

    # Define color ranges in HSV (adjust as necessary)
    lower_red = np.array([0, 70, 50])
    upper_red = np.array([10, 255, 255])
    lower_red2 = np.array([170, 70, 50])
    upper_red2 = np.array([180, 255, 255])

    lower_green = np.array([40, 40, 40])
    upper_green = np.array([70, 255, 255])

    # Extract numbers based on color
    red_numbers = extract_colored_numbers(image, lower_red, upper_red) + \
                  extract_colored_numbers(image, lower_red2, upper_red2)
    green_numbers = extract_colored_numbers(image, lower_green, upper_green)

    print("Red numbers:", red_numbers)
    print("Green numbers:", green_numbers)

if __name__ == "__main__":
    main()
