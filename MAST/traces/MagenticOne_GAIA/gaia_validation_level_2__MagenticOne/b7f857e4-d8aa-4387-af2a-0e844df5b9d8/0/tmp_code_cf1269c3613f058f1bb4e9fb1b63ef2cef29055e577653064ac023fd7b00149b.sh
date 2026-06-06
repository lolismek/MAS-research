# Install Tesseract if it's not installed
if ! command -v tesseract &> /dev/null
then
    echo "Tesseract is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr
fi

# Perform OCR on the image
tesseract /workspace/b7f857e4-d8aa-4387-af2a-0e844df5b9d8.png output.txt

# Display the extracted text
cat output.txt
