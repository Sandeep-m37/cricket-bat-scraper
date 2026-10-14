
import sqlite3
from pathlib import Path

# Database file ka path
folder = Path(__file__).resolve().parent
db_file = folder / "cricket_bats.db"

# Database connect karna
connection = sqlite3.connect(db_file)
cursor = connection.cursor()

# 1. Total products
cursor.execute("SELECT COUNT(*) FROM products")
total = cursor.fetchone()[0]

print("\nTOTAL PRODUCTS:", total)


# 2. Saare products ki list
print("\n--- ALL CRICKET BATS ---")

cursor.execute("""
    SELECT name, type, selling_price, mrp, rating
    FROM products
    ORDER BY selling_price ASC
""")

for row in cursor.fetchall():
    print(
        f"Name: {row[0]}\n"
        f"Type: {row[1]}\n"
        f"Selling Price: {row[2]}\n"
        f"MRP: {row[3]}\n"
        f"Rating: {row[4]}\n"
        + "-" * 35
    )


# 3. Cheapest bat
cursor.execute("""
    SELECT name, selling_price
    FROM products
    WHERE selling_price IS NOT NULL
    ORDER BY selling_price ASC
    LIMIT 1
""")

cheapest = cursor.fetchone()

if cheapest:
    print("\nCHEAPEST BAT:", cheapest[0])
    print("Price:", cheapest[1])
else:
    print("\nCheapest bat ka data nahi mila.")


# 4. Most expensive bat
cursor.execute("""
    SELECT name, selling_price
    FROM products
    WHERE selling_price IS NOT NULL
    ORDER BY selling_price DESC
    LIMIT 1
""")

expensive = cursor.fetchone()

if expensive:
    print("\nMOST EXPENSIVE BAT:", expensive[0])
    print("Price:", expensive[1])
else:
    print("\nMost expensive bat ka data nahi mila.")


# 5. ₹1000 se kam ke bats
cursor.execute("""
    SELECT name, selling_price
    FROM products
    WHERE selling_price < 1000
    ORDER BY selling_price ASC
""")

budget_bats = cursor.fetchall()

print("\n--- BATS UNDER ₹1000 ---")

if budget_bats:
    for name, price in budget_bats:
        print(f"{name} - ₹{price}")
else:
    print("₹1000 se kam ka koi bat nahi mila.")


# 6. Type ke hisaab se product count
cursor.execute("""
    SELECT type, COUNT(*)
    FROM products
    GROUP BY type
    ORDER BY COUNT(*) DESC
""")

print("\n--- PRODUCTS BY TYPE ---")

for product_type, count in cursor.fetchall():
    print(f"{product_type}: {count}")


# Database close karna
connection.close()

print("\nReport complete.")
