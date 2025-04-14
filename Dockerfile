FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libgbm1 libatspi2.0-0 libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxrandr2 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 \
    fonts-liberation \
    wget \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY . .

ENV TARGET_URL="https://www.pajacyk.pl/"
ENV CLICK_SELECTOR=".pajacyk__clickbox"
ENV SUCCESS_SELECTOR=".pajacyk__thankyou"
ENV COUNT_SPAN_SELECTOR="main > p > span"
ENV WAIT_TIMEOUT="20"
ENV MAX_CONCURRENCY="10"
ENV STEEL_API_KEY="ste-TW29nXjrU4ECB4gOdcdOhJbrPtHGMsv6ChGr5JXflFb1iTrzaOJm5Ai3jZqTgmD69l85eMB4jxRchTfTyLas4JGVsg8TUeXYD7z"

CMD ["python", "pajacyk_clicker.py"]