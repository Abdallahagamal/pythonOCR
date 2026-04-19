# Stage 1: Base image
FROM python:3.10-slim

# Install OpenCV and Tesseract runtime libraries for Linux containers.
RUN apt-get update && apt-get install -y --no-install-recommends \
	libxcb1 \
	libx11-6 \
	libxext6 \
	libxrender1 \
	libsm6 \
	libgl1 \
	libglib2.0-0 \
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