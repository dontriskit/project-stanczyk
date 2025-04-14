# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
# Optional: Define path for Playwright browsers if needed, though defaults usually work
# ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

# Install system dependencies required by Playwright browsers (Chromium)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # List from Playwright docs / previous working Dockerfile
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libgbm1 libatspi2.0-0 libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxrandr2 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 \
    fonts-liberation \
    wget \
    ca-certificates \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (specifically Chromium in this case)
# --with-deps tries to install system deps, but we did most manually above for clarity/reliability
RUN playwright install --with-deps chromium

# Copy the rest of the application code into the container
COPY . .

# Set environment variables for the script (defaults)
# These can be overridden in docker-compose.yml
ENV TARGET_URL="https://www.pajacyk.pl/"
ENV CLICK_SELECTOR=".pajacyk__clickbox"
ENV SUCCESS_SELECTOR=".pajacyk__thankyou"
ENV COUNT_SPAN_SELECTOR="main > p > span"
ENV WAIT_TIMEOUT="15"
ENV MAX_CYCLES="500"

# Command to run the application
CMD ["python", "pajacyk_clicker_reused_context_local.py"]