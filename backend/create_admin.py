from getpass import getpass

import mysql.connector
from werkzeug.security import generate_password_hash

from config import Config

Config.validate()

name = input("Full name: ").strip()
username = input("Username: ").strip()
role = input("Role (ADMIN or FACULTY): ").strip().upper()

if role not in ("ADMIN", "FACULTY"):
    raise SystemExit("Role must be ADMIN or FACULTY.")
if not name or not username:
    raise SystemExit("Name and username are required.")

department = year = section = None
if role == "FACULTY":
    department = input("Department (must match students.department): ").strip()
    year = int(input("Year (number, e.g. 2): ").strip())
    section = input("Section (e.g. A): ").strip()

password = getpass("Password (min 8 characters): ")
if len(password) < 8:
    raise SystemExit("Password must be at least 8 characters.")
if password != getpass("Confirm password: "):
    raise SystemExit("Passwords do not match.")

conn = mysql.connector.connect(
    host=Config.DB_HOST,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    database=Config.DB_NAME,
    port=Config.DB_PORT,
)
try:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, username, password_hash, role, department, year, section) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (name, username, generate_password_hash(password), role, department, year, section),
    )
    conn.commit()
    print(f"{role} account '{username}' created.")
except mysql.connector.IntegrityError:
    print("That username already exists.")
finally:
    conn.close()