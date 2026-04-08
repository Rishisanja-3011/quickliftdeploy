import mysql.connector
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Securely fetch credentials
db = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", 19199),
    user=os.getenv("DB_USER", "avnadmin"),
    password=os.getenv("DB_PASS", "")
)

cursor = db.cursor()
# cursor.execute("CREATE DATABASE IF NOT EXISTS quicklift")
# cursor.execute("USE quicklift")
cursor.execute(f"USE {os.getenv('DB_NAME', 'defaultdb')}")
# 1. User Table
cursor.execute("""CREATE TABLE IF NOT EXISTS userdata (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fullname VARCHAR(100),
    username VARCHAR(50) UNIQUE,
    email VARCHAR(100),
    phnumber VARCHAR(20),
    city VARCHAR(50),
    gender VARCHAR(10),
    files VARCHAR(255),
    id_file VARCHAR(255),
    passwords VARCHAR(255),
    latitude FLOAT,
    longitude FLOAT
)""")

# 2. Add latitude & longitude (SAFE way if table already exists)
try:
    cursor.execute("ALTER TABLE userdata ADD COLUMN latitude FLOAT")
except:
    pass  # Column may already exist

try:
    cursor.execute("ALTER TABLE userdata ADD COLUMN longitude FLOAT")
except:
    pass

# 3. Rides Table
cursor.execute("""CREATE TABLE IF NOT EXISTS rides (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255),
    leaving_from VARCHAR(255),
    going_to VARCHAR(255),
    date DATE,
    time TIME,
    seats INT,
    vehicle VARCHAR(100),
    distance_km DECIMAL(10,2),
    price_per_seat DECIMAL(10,2),
    total_price DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

# 4. Bookings Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ride_id INT,
    passenger_username VARCHAR(255),
    status VARCHAR(50) DEFAULT 'Booked',
    booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ride_id) REFERENCES rides(id) ON DELETE CASCADE
)
""")

# 5. Live Location Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_locations (
    username VARCHAR(100) PRIMARY KEY,
    latitude FLOAT,
    longitude FLOAT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
""")

db.commit()
print("DATABASE UPDATED AND SECURED!")

cursor.close()
db.close()