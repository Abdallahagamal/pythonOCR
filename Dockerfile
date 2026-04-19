# Stage 1: Base image
FROM python:3.10-slim

# Install Tesseract OCR for pytesseract on Linux containers.
RUN apt-get update && apt-get install -y --no-install-recommends \
	tesseract-ocr \
	tesseract-ocr-ara \
	tesseract-ocr-eng \
	&& rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Hugging Face / public access
EXPOSE 7860

# Run the Flask app
CMD ["python", "app.py"]