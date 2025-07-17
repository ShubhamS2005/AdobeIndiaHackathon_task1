# Use official Python slim image — lightweight and AMD64 compatible
FROM python:3.11

# Set working directory inside container
WORKDIR /app

# Copy local code to container
COPY Extractor.py ./
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Make sure input/output dirs exist
RUN mkdir -p /app/input /app/output

# The container ENTRYPOINT — this runs when container starts
CMD ["python", "Extractor.py"]
