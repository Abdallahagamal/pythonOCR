# Stage 1: Base image
FROM python:3.10-slim

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