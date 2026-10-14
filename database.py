import json
import sqlite3
from pathlib import Path

# Project folder ka path
folder = Path(__file__).resolve().parent

# JSON aur database files
json_file = folder / "products.json"
db_file = folder / "cricket_bats.db"

# JSON file check karna
if not json_file.exists():
    print("products.json nahi mili. Pehle scraper.py run karo.")
    raise SystemExit(1)

# JSON file se data read karna
with open(json_file, "r", encoding="utf-8") as file:
    products = json.load(file)

# SQLite database connect/create karna
connection = sqlite3.connect(db_file)
cursor = connection.cursor()

# Products table create karna
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT,
    selling_price INTEGER,
    mrp INTEGER,
    rating REAL,
    reviews INTEGER,
    photo_url TEXT,
    product_url TEXT UNIQUE,
    scraped_at TEXT
)
""")

# Har product ko database mein save karna
for product in products:
    cursor.execute("""
        INSERT INTO products (
            name, type, selling_price, mrp,
            rating, reviews, photo_url,
            product_url, scraped_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_url) DO UPDATE SET
            name = excluded.name,
            type = excluded.type,
            selling_price = excluded.selling_price,
            mrp = excluded.mrp,
            rating = excluded.rating,
            reviews = excluded.reviews,
            photo_url = excluded.photo_url,
            scraped_at = excluded.scraped_at
    """, (
        product.get("name"),
        product.get("type"),
        product.get("selling_price"),
        product.get("mrp"),
        product.get("rating"),
        product.get("reviews"),
        product.get("photo_url"),
        product.get("product_url"),
        product.get("scraped_at")
    ))

# Changes save karna
connection.commit()

# Total products count karna
cursor.execute("SELECT COUNT(*) FROM products")
total = cursor.fetchone()[0]

print("Products processed:", len(products))
print("Total unique products in database:", total)
print("Database saved at:", db_file)

connection.close()
