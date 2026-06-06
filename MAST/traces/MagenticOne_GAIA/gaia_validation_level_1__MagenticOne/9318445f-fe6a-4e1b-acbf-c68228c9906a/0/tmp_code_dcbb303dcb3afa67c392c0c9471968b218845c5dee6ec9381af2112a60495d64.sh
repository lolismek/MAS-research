# Install Tesseract
sudo apt-get update
sudo apt-get install -y tesseract-ocr

# Extract text from the image
# Ensure the image path is correct
ocr_output=$(tesseract /workspace/9318445f-fe6a-4e1b-acbf-c68228c9906a.png stdout)
echo "$ocr_output"
