echo "Running Docker..."
docker run --rm -v /memecoin_screener/screenshot:/app/screenshots solana_meme_playwright:latest
echo "Finished Docker Execution"