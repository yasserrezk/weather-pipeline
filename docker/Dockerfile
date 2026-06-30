FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY .env .

# No default CMD — this image is used as a base/utility container.
# Run specific scripts with: docker run <image> python src/...
