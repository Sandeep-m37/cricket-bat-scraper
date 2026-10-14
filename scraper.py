import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
from urllib.parse import urljoin

# 1. Flipkart search URL
url = "https://www.flipkart.com/search?q=cricket+bat"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    )
}

# 2. Take html from website
try:
    response = requests.get(
        url,
        headers=headers,
        timeout=20
    )
    response.raise_for_status()

except requests.RequestException as error:
    print("Request failed:", error)
    raise SystemExit(1)

soup = BeautifulSoup(response.text, "html.parser")

# 3. Find the Product links 
product_links = soup.select("a.pIpigb")

print("Product links found:", len(product_links))

products = []
seen_urls = set()

# 4. Process the only 5 products 
for product in product_links:

    name = product.get("title") or product.get_text(
        " ", strip=True
    )

    product_url = urljoin(
        "https://www.flipkart.com",
        product.get("href", "")
    )

    if not name or product_url in seen_urls:
        continue

    seen_urls.add(product_url)

# 5. Product card identify karna:
# link ke ancestors ko chhote se bade order mein check karenge
    card = None
    parent = product

    for level in range(1, 8):
        if parent.parent is None:
            break

        parent = parent.parent
        text = parent.get_text(" ", strip=True)

        # Card mein product name aur price dono hone chahiye
        if (
            name[:25] in text
            and re.search(r"₹\s*[\d,]+", text)
        ):
            card = parent
            break

    if card is None:
        print("Card nahi mila:", name)
        continue

    text = card.get_text(" ", strip=True)

# 6. Selling price aur MRP:
# Is regex se prices milengi, lekin order ko verify karna zaroori hai
    price_matches = re.findall(
        r"₹\s*([\d,]+)",
        text
    )

    selling_price = None
    mrp = None

    if len(price_matches) >= 1:
        selling_price = int(
            price_matches[0].replace(",", "")
        )

    if len(price_matches) >= 2:
        mrp = int(
            price_matches[1].replace(",", "")
        )

    # 7. Rating aur review count
    rating_match = re.search(
        r"(?<![\d.])([0-5]\.\d)\s*\(([\d,]+)\)",
        text
    )

    rating = None
    reviews = None

    if rating_match:
        rating = float(rating_match.group(1))
        reviews = int(
            rating_match.group(2).replace(",", "")
        )

    # 8. Image URL
    image = card.select_one("img")
    photo_url = None

    if image:
        photo_url = (
            image.get("src")
            or image.get("data-src")
            or image.get("data-lazy-src")
        )

    # 9. Product type
    lower_name = name.lower()

    if "kashmir willow" in lower_name:
        product_type = "Kashmir Willow"
    elif "english willow" in lower_name:
        product_type = "English Willow"
    elif "popular willow" in lower_name or "poplar willow" in lower_name:
        product_type = "Popular/Poplar Willow"
    elif "plastic" in lower_name or "pvc" in lower_name:
        product_type = "Plastic"
    else:
        product_type = "Unknown"

    # 10. Dictionary mein data store karna
    product_data = {
        "name": name,
        "type": product_type,
        "selling_price": selling_price,
        "mrp": mrp,
        "rating": rating,
        "reviews": reviews,
        "photo_url": photo_url,
        "product_url": product_url,
        "scraped_at": datetime.now().isoformat(
            timespec="seconds"
        )
    }

    products.append(product_data)

    if len(products) == 5:
        break

# 11. Output print karna
print("\nTotal Products Extracted:", len(products))

for number, item in enumerate(products, start=1):
    print("\n" + "=" * 50)
    print("PRODUCT", number)

    for key, value in item.items():
        print(f"{key}: {value}")

# 12. JSON file mein save karna
with open(
    "products.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        products,
        file,
        ensure_ascii=False,
        indent=4
    )

print("\nData saved in products.json")