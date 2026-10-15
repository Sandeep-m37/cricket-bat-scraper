
import sqlite3
from pathlib import Path


# --------------------------------------------------
# 1. DATABASE CONNECTION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = BASE_DIR / "cricket_bats.db"

if not DB_NAME.exists():
    print("ERROR: cricket_bats.db file nahi mili.")
    raise SystemExit(1)

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()


def show_value(label, value):
    print(f"{label}: {value if value not in (None, '') else 'Not available'}")


try:
    # --------------------------------------------------
    # 2. CHECK TABLES
    # --------------------------------------------------

    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """)

    tables = [row[0] for row in cur.fetchall()]

    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)
    print("Database:", DB_NAME)
    print("Tables:", ", ".join(tables))

    if "products" not in tables:
        print("Products table nahi mili.")
        raise SystemExit(1)

    cur.execute("PRAGMA table_info(products)")
    product_columns = [row[1] for row in cur.fetchall()]

    print("Products columns:", product_columns)

    if "reviews" in tables:
        cur.execute("PRAGMA table_info(reviews)")
        review_columns = [row[1] for row in cur.fetchall()]
        print("Reviews columns:", review_columns)
    else:
        review_columns = []
        print("Reviews table nahi mili.")

    # --------------------------------------------------
    # 3. TOTAL PRODUCT COUNT
    # --------------------------------------------------

    cur.execute("SELECT COUNT(*) FROM products")
    print("\nTOTAL PRODUCTS:", cur.fetchone()[0])

    # --------------------------------------------------
    # 4. SHOW PRODUCT INVENTORY
    # --------------------------------------------------

    preferred_fields = [
        "id",
        "name",
        "type",
        "selling_price",
        "mrp",
        "photo_url",
        "product_url",
        "rating",
        "scraped_at",
    ]

    fields = [
        field for field in preferred_fields
        if field in product_columns
    ]

    if "name" not in fields:
        print("Product name column nahi mili.")
        raise SystemExit(1)

    sql_fields = ", ".join(f'"{field}"' for field in fields)

    order_by = "id" if "id" in product_columns else "rowid"

    cur.execute(f"""
        SELECT {sql_fields}
        FROM products
        ORDER BY "{order_by}" DESC
    """)

    products = cur.fetchall()

    print("\n" + "=" * 60)
    print("PRODUCT INVENTORY")
    print("=" * 60)

    for product in products:
        details = dict(zip(fields, product))

        print("\n" + "-" * 60)

        show_value("Inventory ID", details.get("id"))
        show_value("Inventory Name", details.get("name"))
        show_value("Type", details.get("type"))
        show_value("Price", details.get("selling_price"))
        show_value("MRP", details.get("mrp"))
        show_value("Photo URL", details.get("photo_url"))
        show_value("Product URL", details.get("product_url"))
        show_value("Rating", details.get("rating"))
        show_value("Scraped At", details.get("scraped_at"))

    # --------------------------------------------------
    # 5. REVIEWS FOR EACH PRODUCT
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("PRODUCT REVIEWS (MAXIMUM 10 PER PRODUCT)")
    print("=" * 60)

    if "reviews" not in tables:
        print("Reviews table nahi hai.")

    elif "product_id" not in review_columns:
        print("Reviews table mein product_id column nahi hai.")

    else:
        review_fields = [
            field for field in [
                "reviewer_name",
                "review_title",
                "rating",
                "review_date",
                "comment",
                "review_text",
            ]
            if field in review_columns
        ]

        if not review_fields:
            print("Review details ke columns nahi mile.")

        else:
            review_sql_fields = ", ".join(
                f'"{field}"' for field in review_fields
            )

            review_order = (
                "id" if "id" in review_columns else "rowid"
            )

            for product in products:
                details = dict(zip(fields, product))
                product_id = details.get("id")
                product_name = details.get("name")

                if product_id is None:
                    continue

                cur.execute(f"""
                    SELECT {review_sql_fields}
                    FROM reviews
                    WHERE product_id = ?
                    ORDER BY "{review_order}" ASC
                    LIMIT 10
                """, (product_id,))

                reviews = cur.fetchall()

                print("\n" + "-" * 60)
                print("PRODUCT:", product_name)
                print("PRODUCT ID:", product_id)
                print("REVIEWS FOUND:", len(reviews))

                if not reviews:
                    print("Is product ke reviews nahi mile.")
                    continue

                for number, review in enumerate(reviews, start=1):
                    review_details = dict(
                        zip(review_fields, review)
                    )

                    print(f"\nReview {number}")

                    for field, value in review_details.items():
                        show_value(field, value)

    # --------------------------------------------------
    # 6. FINAL COUNTS
    # --------------------------------------------------

    cur.execute("SELECT COUNT(*) FROM products")
    total_products = cur.fetchone()[0]

    print("\n" + "=" * 60)
    print("FINAL DATABASE SUMMARY")
    print("=" * 60)
    print("Total products:", total_products)

    if "reviews" in tables:
        cur.execute("SELECT COUNT(*) FROM reviews")
        print("Total review records:", cur.fetchone()[0])

    print("\nReport complete.")

finally:
    conn.close()
