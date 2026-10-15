
import json
import re
import html
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

JSON_FILE = BASE_DIR / "products.json"
DEBUG_HTML_FILE = BASE_DIR / "product_debug.html"

PRODUCT_URL = (
    "https://www.flipkart.com/"
    "mrf-size-6-genius-grand-virat-kohli-signed-poplar-willow-cricket-bat-15-yrs/"
    "p/itmf942cd2uqs53g"
)

PRODUCT_ID = "BATEWT7HQZVAKQNX"
MAX_REVIEWS = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return None

    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value).strip()

    return value or None


def to_number(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return value

    value = str(value).replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", value)

    if not match:
        return None

    number = float(match.group())

    return int(number) if number.is_integer() else number


# ============================================================
# JSON-LD EXTRACTION
# ============================================================

def walk_json(data):
    if isinstance(data, dict):
        yield data

        for value in data.values():
            yield from walk_json(value)

    elif isinstance(data, list):
        for item in data:
            yield from walk_json(item)


def extract_json_ld(soup):
    objects = []

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        raw = script.string or script.get_text()

        if not raw:
            continue

        try:
            objects.extend(walk_json(json.loads(raw)))
        except (json.JSONDecodeError, TypeError):
            continue

    return objects


def is_type(obj, expected):
    value = obj.get("@type")

    return value == expected or (
        isinstance(value, list) and expected in value
    )


# ============================================================
# FLIPKART PAGE STATE
# ============================================================

def extract_page_state(page_html):
    patterns = [
        r'"ppd"\s*:\s*(\{.*?\})\s*,\s*"sla"',
        r'"ppd"\s*:\s*(\{.*?\})',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, page_html, re.DOTALL):
            try:
                data = json.loads(match.group(1))

                if isinstance(data, dict) and (
                    "mrp" in data or "fsp" in data
                ):
                    return data

            except json.JSONDecodeError:
                continue

    return {}


# ============================================================
# PRODUCT INFORMATION
# ============================================================

def extract_product_name(soup, json_objects):
    for obj in json_objects:
        if is_type(obj, "Product"):
            name = clean_text(obj.get("name"))

            if name:
                return name

    for selector in [
        "span.VU-ZEz",
        "span.B_NuCI",
        "h1",
        "meta[property='og:title']",
    ]:
        element = soup.select_one(selector)

        if element:
            value = (
                element.get("content")
                if element.name == "meta"
                else element.get_text(" ", strip=True)
            )

            value = clean_text(value)

            if value:
                return value

    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True))

    return None


def extract_product_type(name):
    if not name:
        return "Unknown"

    name = name.lower()

    if "poplar willow" in name:
        return "Poplar Willow"

    if "english willow" in name:
        return "English Willow"

    if "kashmir willow" in name:
        return "Kashmir Willow"

    if "plastic" in name:
        return "Plastic Cricket Bat"

    if "tennis" in name and "bat" in name:
        return "Tennis Cricket Bat"

    return "Unknown"


def extract_prices(soup, json_objects, page_html):
    selling_price = None
    mrp = None

    ppd = extract_page_state(page_html)

    if ppd:
        selling_price = to_number(ppd.get("fsp"))
        mrp = to_number(ppd.get("mrp"))

    for obj in json_objects:
        if not is_type(obj, "Product"):
            continue

        offers = obj.get("offers")

        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        if not isinstance(offers, dict):
            continue

        if selling_price is None:
            selling_price = to_number(offers.get("price"))

        specs = offers.get("priceSpecification", [])

        if isinstance(specs, dict):
            specs = [specs]

        for spec in specs:
            if not isinstance(spec, dict):
                continue

            description = (
                str(spec.get("priceType", "")) + " "
                + str(spec.get("name", ""))
            ).lower()

            if "mrp" in description or "list" in description:
                if mrp is None:
                    mrp = to_number(spec.get("price"))

    if selling_price is None:
        for selector in [
            "meta[property='product:price:amount']",
            "meta[property='og:price:amount']",
        ]:
            element = soup.select_one(selector)

            if element:
                selling_price = to_number(element.get("content"))

                if selling_price is not None:
                    break

    if selling_price is None:
        for selector in [
            "div.Nx9bqj.CxhGGd",
            "div._30jeq3._16Jk6d",
            "div._30jeq3",
        ]:
            element = soup.select_one(selector)

            if element:
                selling_price = to_number(
                    element.get_text(" ", strip=True)
                )

                if selling_price is not None:
                    break

    return selling_price, mrp


def extract_rating_and_count(soup, json_objects, page_html):
    rating = None
    review_count = None

    for obj in json_objects:
        aggregate = obj.get("aggregateRating")

        if not isinstance(aggregate, dict):
            continue

        if rating is None:
            rating = to_number(aggregate.get("ratingValue"))

        if review_count is None:
            review_count = to_number(
                aggregate.get("reviewCount")
                or aggregate.get("ratingCount")
            )

    if rating is None:
        match = re.search(
            r'"averageRating"\s*:\s*"?(\d+(?:\.\d+)?)"?',
            page_html
        )

        if match:
            rating = to_number(match.group(1))

    if review_count is None:
        for pattern in [
            r'"ratingCount"\s*:\s*"?([\d,]+)"?',
            r'"reviewCount"\s*:\s*"?([\d,]+)"?',
        ]:
            match = re.search(pattern, page_html)

            if match:
                review_count = to_number(match.group(1))
                break

    if rating is None:
        for selector in ["div.XQDdHH", "div._3LWZlK"]:
            element = soup.select_one(selector)

            if element:
                rating = to_number(
                    element.get_text(" ", strip=True)
                )

                if rating is not None:
                    break

    return rating, review_count


def extract_image_url(soup, json_objects):
    for obj in json_objects:
        if not is_type(obj, "Product"):
            continue

        image = obj.get("image")

        if isinstance(image, list):
            image = image[0] if image else None

        if isinstance(image, dict):
            image = image.get("url")

        if isinstance(image, str) and image.startswith("http"):
            return image

    for selector in [
        "meta[property='og:image']",
        "meta[name='twitter:image']",
    ]:
        element = soup.select_one(selector)

        if element:
            image_url = element.get("content")

            if image_url and image_url.startswith("http"):
                return image_url

    return None


# ============================================================
# REVIEW HELPERS
# ============================================================

def normalise_review_date(value):
    value = clean_text(value)

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).strftime("%Y-%m-%d")
    except ValueError:
        pass

    for date_format in [
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%b, %Y",
        "%B, %Y",
    ]:
        try:
            parsed_date = datetime.strptime(value, date_format)

            # Month-only dates ko month ke first day ke roop
            # mein normalize karte hain.
            return parsed_date.strftime("%Y-%m-%d")

        except ValueError:
            continue

    return value


def unique_reviews(reviews):
    unique = []
    seen = set()

    for review in reviews:
        if not isinstance(review, dict):
            continue

        cleaned = {
            "reviewer_name": clean_text(
                review.get("reviewer_name")
                or review.get("reviewer")
            ),
            "review_title": clean_text(
                review.get("review_title")
                or review.get("title")
            ),
            "comment": clean_text(
                review.get("comment")
            ),
            "rating": to_number(review.get("rating")),
            "review_date": normalise_review_date(
                review.get("review_date")
                or review.get("date")
            ),
        }

        if not cleaned["comment"] and not cleaned["review_title"]:
            continue

        key = (
            cleaned["reviewer_name"] or "",
            cleaned["review_title"] or "",
            cleaned["comment"] or "",
            cleaned["review_date"] or "",
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(cleaned)

    return unique


def extract_reviews_from_json(json_objects):
    reviews = []

    for obj in json_objects:
        if not is_type(obj, "Review"):
            continue

        author = obj.get("author")

        if isinstance(author, dict):
            author = author.get("name")

        title = (
            obj.get("name")
            or obj.get("headline")
            or obj.get("reviewTitle")
        )

        comment = (
            obj.get("reviewBody")
            or obj.get("description")
        )

        rating = obj.get("reviewRating")

        if isinstance(rating, dict):
            rating = rating.get("ratingValue")

        date = (
            obj.get("datePublished")
            or obj.get("dateCreated")
        )

        reviews.append({
            "reviewer_name": author,
            "review_title": title,
            "comment": comment,
            "rating": to_number(rating),
            "review_date": normalise_review_date(date),
        })

    return reviews


def extract_reviews_from_embedded_html(page_html):
    reviews = []

    for match in re.finditer(
        r'<script[^>]*>(.*?)</script>',
        page_html,
        re.IGNORECASE | re.DOTALL
    ):
        script_text = match.group(1)

        if not any(
            key in script_text
            for key in ["reviewText", "reviewBody", "reviewerName"]
        ):
            continue

        try:
            parsed = json.loads(script_text)
            objects = list(walk_json(parsed))
        except (json.JSONDecodeError, TypeError):
            continue

        reviews.extend(extract_reviews_from_json(objects))

        for obj in objects:
            comment = (
                obj.get("reviewText")
                or obj.get("reviewBody")
            )

            if not comment:
                continue

            author = obj.get("reviewerName") or obj.get("author")

            if isinstance(author, dict):
                author = author.get("name")

            title = (
                obj.get("reviewTitle")
                or obj.get("title")
                or obj.get("name")
            )

            rating = obj.get("rating")

            if isinstance(rating, dict):
                rating = rating.get("ratingValue")

            date = (
                obj.get("reviewDate")
                or obj.get("datePublished")
            )

            reviews.append({
                "reviewer_name": author,
                "review_title": title,
                "comment": comment,
                "rating": to_number(rating),
                "review_date": normalise_review_date(date),
            })

    return unique_reviews(reviews)


# ============================================================
# FLIPKART REVIEW API
# ============================================================

def fetch_reviews_from_api(product_id):
    """Flipkart API se actual product reviews fetch karta hai."""

    api_url = "https://www.flipkart.com/api/3/product/reviews"

    params = {
        "productId": product_id,
        "count": MAX_REVIEWS,
        "ratings": "ALL",
        "reviewerType": "ALL",
        "sortOrder": "MOST_HELPFUL",
    }

    api_headers = {
        **HEADERS,
        "x-user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36 "
            "FKUA/website/41/website/Desktop"
        ),
    }

    try:
        response = requests.get(
            api_url,
            params=params,
            headers=api_headers,
            timeout=30,
        )

        print("Reviews API status:", response.status_code)
        response.raise_for_status()

        result = response.json()
        entries = result.get("RESPONSE", {}).get("data", [])

        reviews = []

        for entry in entries:
            item = entry.get("value", {})

            review = {
                "reviewer_name": item.get("author"),
                "review_title": item.get("title"),
                "comment": item.get("text"),
                "rating": item.get("rating"),
                "review_date": normalise_review_date(
                    item.get("created")
                ),
            }

            reviews.append(review)

        reviews = unique_reviews(reviews)

        print("Actual API reviews extracted:", len(reviews))

        return reviews[:MAX_REVIEWS]

    except (requests.RequestException, ValueError) as error:
        print("Reviews API error:", error)
        return []


# ============================================================
# REVIEW URL DISCOVERY
# ============================================================

def find_review_urls(soup, product_url):
    found = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        link_text = clean_text(
            anchor.get_text(" ", strip=True)
        ) or ""

        if (
            "ratings-reviews-details-page" not in href.lower()
            and "review" not in link_text.lower()
        ):
            continue

        full_url = urljoin(product_url, href)
        parsed = urlparse(full_url)
        query = parsed.query

        query = re.sub(
            r"(^|&)lid([^=&]+)(?=&|$)",
            r"\1lid=\2",
            query
        )

        params = parse_qs(query)
        fixed_query = urlencode(params, doseq=True)

        fixed_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            fixed_query,
            parsed.fragment,
        ))

        if fixed_url not in found:
            found.append(fixed_url)

    return found


def fetch_reviews_from_url(review_url):
    print("Fetching review page:", review_url)

    try:
        response = requests.get(
            review_url,
            headers=HEADERS,
            timeout=30
        )

        print("Review page status:", response.status_code)

        if response.status_code != 200:
            print("Review page access nahi hua.")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        json_objects = extract_json_ld(soup)

        reviews = extract_reviews_from_json(json_objects)
        reviews.extend(
            extract_reviews_from_embedded_html(response.text)
        )

        return unique_reviews(reviews)[:MAX_REVIEWS]

    except requests.RequestException as error:
        print("Review page request failed:", error)
        return []


# ============================================================
# JSON STORAGE
# ============================================================

def load_existing_products():
    if not JSON_FILE.exists():
        return []

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

    except (json.JSONDecodeError, OSError) as error:
        print("Existing JSON read nahi hua:", error)
        return []

    if isinstance(data, dict):
        products = data.get("products", [])
        return products if isinstance(products, list) else []

    if isinstance(data, list):
        return data

    return []


def save_product_to_json(product):
    products = load_existing_products()

    product_url = product.get("product_url")
    existing_index = None

    for index, old_product in enumerate(products):
        if old_product.get("product_url") == product_url:
            existing_index = index
            break

    if existing_index is not None:
        old_product = products[existing_index]

        merged_reviews = unique_reviews(
            old_product.get("review_details", [])
            + product.get("review_details", [])
        )

        updated_product = {
            **old_product,
            **product,
            "review_details": merged_reviews[:MAX_REVIEWS],
        }

        products[existing_index] = updated_product

    else:
        products.append({
            **product,
            "review_details": unique_reviews(
                product.get("review_details", [])
            )[:MAX_REVIEWS],
        })

    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {"products": products},
            file,
            indent=2,
            ensure_ascii=False
        )

    print("JSON saved:", JSON_FILE)
    print("Products in JSON:", len(products))


# ============================================================
# MAIN SCRAPER
# ============================================================

def scrape_product(product_url):
    print("=" * 60)
    print("FLIPKART PRODUCT SCRAPER")
    print("=" * 60)
    print("Requested URL:", product_url)

    try:
        response = requests.get(
            product_url,
            headers=HEADERS,
            timeout=30
        )
    except requests.RequestException as error:
        print("Product request failed:", error)
        return

    print("Final URL:", response.url)
    print("Status code:", response.status_code)

    if response.status_code != 200:
        print("Product page access nahi hua.")
        return

    page_html = response.text

    DEBUG_HTML_FILE.write_text(
        page_html,
        encoding="utf-8"
    )

    print("Debug HTML saved:", DEBUG_HTML_FILE)

    soup = BeautifulSoup(page_html, "html.parser")
    json_objects = extract_json_ld(soup)

    name = extract_product_name(soup, json_objects)
    product_type = extract_product_type(name)

    selling_price, mrp = extract_prices(
        soup, json_objects, page_html
    )

    rating, review_count = extract_rating_and_count(
        soup, json_objects, page_html
    )

    photo_url = extract_image_url(soup, json_objects)

    # Product HTML se reviews.
    review_details = extract_reviews_from_json(json_objects)
    review_details.extend(
        extract_reviews_from_embedded_html(page_html)
    )
    review_details = unique_reviews(review_details)

    print()
    print("Product name:", name)
    print("Product type:", product_type)
    print("Selling price:", selling_price)
    print("MRP:", mrp)
    print("Rating:", rating)
    print("Aggregate review count:", review_count)
    print("Embedded unique reviews:", len(review_details))

    # Working API se additional actual reviews.
    api_reviews = fetch_reviews_from_api(PRODUCT_ID)

    review_details = unique_reviews(
        review_details + api_reviews
    )

    # Old review page fallback, only if fewer than 10 reviews.
    if len(review_details) < MAX_REVIEWS:
        review_urls = find_review_urls(soup, product_url)

        print("Review links found:", len(review_urls))

        for review_url in review_urls:
            if len(review_details) >= MAX_REVIEWS:
                break

            additional_reviews = fetch_reviews_from_url(review_url)

            review_details = unique_reviews(
                review_details + additional_reviews
            )

    review_details = review_details[:MAX_REVIEWS]

    print("Unique reviews collected:", len(review_details))

    if len(review_details) < MAX_REVIEWS:
        print(
            "Note: 10 unique actual reviews nahi mile. "
            "Fake reviews add nahi kiye gaye."
        )

    if mrp is None:
        print("Note: MRP nahi mila; guess nahi kiya jayega.")

    product = {
        "name": name,
        "type": product_type,
        "selling_price": selling_price,
        "mrp": mrp,
        "rating": rating,
        "review_count": review_count,
        "photo_url": photo_url,
        "product_url": product_url,
        "scraped_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "review_details": review_details,
    }

    save_product_to_json(product)

    print()
    print("=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    scrape_product(PRODUCT_URL)
