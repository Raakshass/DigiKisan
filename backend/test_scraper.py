# test_scraper.py
from interactivechat import scrape_agmarknet, format_date_for_agmarknet
from datetime import datetime

# Test with current date
test_date = datetime.now().strftime("%Y-%m-%d")
formatted_date = format_date_for_agmarknet(test_date)

print(f"Testing scraper for Wheat in Agra on {formatted_date}")
result = scrape_agmarknet(test_date, "UP", "7", "23")

if result is not None:
    print("✅ Scraping successful!")
    print(result.head())
else:
    print("❌ Scraping failed")
