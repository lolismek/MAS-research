import cv2
import numpy as np
from matplotlib import pyplot as plt

# Load image
image_path = '8f80e01c-1296-4371-9486-bb3d68651a60.png'
img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

# Preprocessing
blur = cv2.GaussianBlur(img, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Detect lines in sheet music
horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
detect_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)

# Detect contours for lines
contours, _ = cv2.findContours(detect_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Count total lines
line_count = len(contours)
print(f'Total number of lines detected: {line_count}')

# Detect notes using Hough Circles
notes = cv2.HoughCircles(thresh, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=50, param2=30, minRadius=5, maxRadius=15)

# Count total notes
note_count = notes.shape[1] if notes is not None else 0
print(f'Total number of notes detected: {note_count}')

# Count notes on lines
notes_on_lines = 0
if notes is not None:
    for note in notes[0, :]:
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if y < note[1] < y + h:
                notes_on_lines += 1
                break

print(f'Number of notes on lines: {notes_on_lines}')

# Display the image for visual confirmation
output_img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
if notes is not None:
    for note in notes[0, :]:
        center = (note[0], note[1])  # Center of the circle
        cv2.circle(output_img, center, 1, (0, 255, 0), 3)  # Circle center
        cv2.circle(output_img, center, note[2], (255, 0, 0), 3)  # Circle outline

plt.imshow(output_img)
plt.title('Detected Notes and Lines')
plt.show()
