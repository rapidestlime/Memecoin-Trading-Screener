FROM python:3.11.7

WORKDIR /app

# Copy the Python script into the container
COPY . .

# Install necessary packages including Xvfb
# RUN apt-get update && \
#     apt-get install -y xvfb && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*

# Install required dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run playwright install to ensure all browsers are downloaded
RUN playwright install --with-deps chromium

# Command to run the scraper script
CMD ["python", "solana_meme_screener.py"]