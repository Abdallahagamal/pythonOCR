import pytesseract
import cv2
import numpy as np
import re


def ocr_image(image_path):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    img = cv2.imread(image_path)

    # Upscale 2x with cubic interpolation
    img = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    # Sharpen
    kernel_sharpen = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    gray = cv2.filter2D(gray, -1, kernel_sharpen)

    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    custom_config = r'--oem 3 --psm 6 -l ara+eng'
    text = pytesseract.image_to_string(gray, config=custom_config)
    return text


def clean_text(text):
    text = re.sub(r'[©@‏®%\(\)\[\]\{\}~\'\"،]', '', text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_phone(text):
    """Normalize Arabic-Indic digits and extract Egyptian mobile number."""
    arabic_indic = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    text = text.translate(arabic_indic)

    # Remove spaces/dashes inside number sequences (run twice)
    text = re.sub(r'(\d)[\s\-](\d)', r'\1\2', text)
    text = re.sub(r'(\d)[\s\-](\d)', r'\1\2', text)

    match = re.search(r'01[0-9]{9}', text)
    return match.group() if match else None


def extract_header_name(text):
    """
    In FB Messenger screenshots, the contact name (client) is in the chat header.
    The header name appears at the TOP of the OCR text.
    Agent names appear mid-text as message labels (e.g. 'Omar Ramzy' before a bubble).

    Strategy:
    1. Collect all candidate names from the FULL text (to know which are agents).
    2. Agent names appear multiple times OR appear after message content lines.
    3. The client name appears ONCE and near the top.
    """
    system_keywords = [
        'intake', 'auto-label', 'lead', 'chat', 'reply', 'ad', 'learn',
        'suggested', 'tap', 'fill', 'stage', 'added', 'label', 'am', 'pm'
    ]

    lines = text.splitlines()

    # Find all name-like lines in the whole text
    def is_name_line(line):
        line = line.strip()
        if not line:
            return False
        if any(kw in line.lower() for kw in system_keywords):
            return False
        words = line.split()
        if 2 <= len(words) <= 4:
            if all(re.match(r'^[A-Za-z\u0600-\u06FF]+$', w) for w in words):
                return True
        return False

    # Count how many times each name appears (agents appear >1 times as message labels)
    from collections import Counter
    all_names = [line.strip() for line in lines if is_name_line(line)]
    name_counts = Counter(all_names)

    # The client name is typically the FIRST name-like line that appears only once
    # (agent names appear as message sender labels repeatedly)
    for line in lines[:15]:  # client name is always near the top
        line = line.strip()
        if is_name_line(line):
            # Prefer names that appear only once (not repeated as sender labels)
            if name_counts[line] == 1:
                return line

    # Fallback: just return the first name-like line in top 15
    for line in lines[:15]:
        line = line.strip()
        if is_name_line(line):
            return line

    return None

