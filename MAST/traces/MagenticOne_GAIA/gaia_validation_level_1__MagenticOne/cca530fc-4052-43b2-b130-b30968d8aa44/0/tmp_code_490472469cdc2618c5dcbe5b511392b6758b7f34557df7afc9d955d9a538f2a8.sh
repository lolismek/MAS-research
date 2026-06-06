# Install tesseract if not already installed
sudo apt-get update
sudo apt-get install -y tesseract-ocr

# Install Python dependencies
pip install -qqq pytesseract opencv-python Pillow
