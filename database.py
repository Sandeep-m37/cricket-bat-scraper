
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
JSON_FILE = BASE_DIR / "products.json"
DB_FILE = BASE_DIR / "cricket_bats.db"


def get_reviews(product):
    """JSON se actual review details nikalo."""
    reviews = product.get("review_details", [])
    return reviews if isinstance(reviews, list) else []


def add_missing_columns(cursor, table, columns):
    """Existing table mein missing columns add karo."""
    cursor.execute(f'PRAGMA table_info("{table}")')
    existing = {row[1] for row in cursor.fetchall()}

    for column, definition in columns.items():
        if column not in existing:
            cursor.execute(
                f'ALTER TABLE "{table}" '
                f'ADD COLUMN "{column}" {definition}'
            )
            print(f"Added column: {table}.{column}")


def main():
    if not JSON_FILE.exists():
        print("ERROR: products.json nahi mili.")
        print("Pehle scraper.py run karein.")
        return

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        print("ERROR: products.json valid JSON nahi hai.")
        print(error)
        return

    # JSON list ya {"products": [...]} dono support karega.
    if isinstance(data, dict):
        products = data.get("products", [])
    elif isinstance(data, list):
        products = data
    else:
        print("ERROR: products.json ka format sahi nahi hai.")
        return

    if not isinstance(products, list):
        print("ERROR: JSON mein products list nahi mili.")
        return

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    try:
        # Existing database aur data ko preserve karo.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                type TEXT,
                selling_price REAL,
                mrp REAL,
                rating REAL,
                reviews INTEGER,
                photo_url TEXT,
                product_url TEXT UNIQUE,
                scraped_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                reviewer_name TEXT,
                review_title TEXT,
                rating REAL,
                review_date TEXT,
                comment TEXT,
                product_url TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        # Purane tables mein missing columns add karo.
        add_missing_columns(cursor, "products", {
            "name": "TEXT",
            "type": "TEXT",
            "selling_price": "REAL",
            "mrp": "REAL",
            "rating": "REAL",
            "reviews": "INTEGER",
            "photo_url": "TEXT",
            "product_url": "TEXT",
            "scraped_at": "TEXT",
        })

        add_missing_columns(cursor, "reviews", {
            "product_id": "INTEGER",
            "reviewer_name": "TEXT",
            "review_title": "TEXT",
            "rating": "REAL",
            "review_date": "TEXT",
            "comment": "TEXT",
            "product_url": "TEXT",
        })

        connection.commit()

        processed_products = 0
        inserted_reviews = 0
        existing_reviews = 0

        for product in products:
            if not isinstance(product, dict):
                continue

            product_url = product.get("product_url")
            if not product_url:
                print("Skipped product: product_url nahi hai.")
                continue

            # Aggregate review count.
            review_count = product.get("review_count")
            if review_count is None:
                review_count = product.get("reviews")

            # Product ko URL se identify karo.
            cursor.execute(
                "SELECT id FROM products WHERE product_url = ?",
                (product_url,)
            )
            row = cursor.fetchone()

            product_values = (
                product.get("name"),
                product.get("type"),
                product.get("selling_price"),
                product.get("mrp"),
                product.get("rating"),
                review_count,
                product.get("photo_url"),
                product_url,
                product.get("scraped_at"),
            )

            if row:
                product_id = row[0]

                cursor.execute("""
                    UPDATE products
                    SET name = ?,
                        type = ?,
                        selling_price = ?,
                        mrp = ?,
                        rating = ?,
                        reviews = ?,
                        photo_url = ?,
                        scraped_at = ?
                    WHERE id = ?
                """, (
                    *product_values[:7],
                    product_values[8],
                    product_id,
                ))

            else:
                cursor.execute("""
                    INSERT INTO products (
                        name, type, selling_price, mrp,
                        rating, reviews, photo_url,
                        product_url, scraped_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, product_values)

                product_id = cursor.lastrowid

            processed_products += 1

            # Sirf actual review details import karo.
            for review in get_reviews(product):
                if not isinstance(review, dict):
                    continue

                reviewer = review.get("reviewer_name")
                title = review.get("review_title")
                rating = review.get("rating")
                review_date = review.get("review_date")
                comment = (
                    review.get("comment")
                    or review.get("review_text")
                )

                # Khali review insert mat karo.
                if not any((reviewer, title, comment, review_date)):
                    continue

                # Duplicate review check.
                cursor.execute("""
                    SELECT id
                    FROM reviews
                    WHERE product_id = ?
                      AND COALESCE(reviewer_name, '') = COALESCE(?, '')
                      AND COALESCE(review_title, '') = COALESCE(?, '')
                      AND COALESCE(review_date, '') = COALESCE(?, '')
                      AND COALESCE(comment, '') = COALESCE(?, '')
                    LIMIT 1
                """, (
                    product_id,
                    reviewer,
                    title,
                    review_date,
                    comment,
                ))

                if cursor.fetchone():
                    existing_reviews += 1
                    continue

                # Same review ki unique constraint bhi handle karo.
                cursor.execute("""
                    INSERT OR IGNORE INTO reviews (
                        product_id,
                        reviewer_name,
                        review_title,
                        rating,
                        review_date,
                        comment,
                        product_url
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_id,
                    reviewer,
                    title,
                    rating,
                    review_date,
                    comment,
                    product_url,
                ))

                if cursor.rowcount > 0:
                    inserted_reviews += 1
                else:
                    existing_reviews += 1

        connection.commit()

        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reviews")
        total_reviews = cursor.fetchone()[0]

        print("\n" + "=" * 60)
        print("DATABASE IMPORT COMPLETE")
        print("=" * 60)
        print("Products processed:", processed_products)
        print("New reviews inserted:", inserted_reviews)
        print("Duplicate reviews skipped:", existing_reviews)
        print("Total products in database:", total_products)
        print("Total review records in database:", total_reviews)
        print("Database path:", DB_FILE)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()
