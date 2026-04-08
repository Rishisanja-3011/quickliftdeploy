from flask import Flask, request, redirect, render_template, url_for, session, flash, g, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import random
import os
import requests
import mysql.connector
from datetime import datetime, date as dt_date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# Cloudinary imports
import cloudinary
import cloudinary.uploader
import cloudinary.api

try:
    from authlib.integrations.flask_client import OAuth
except Exception:
    OAuth = None

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
# ── Secure Email config ──────────────────────────────────────────────
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_if_env_fails')

# ── Secure DB config ─────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "user":     os.getenv("DB_USER", "root"),
    "port":     int(os.getenv("DB_PORT",    3306)),
    "password": os.getenv("DB_PASS", ""),
    "database": os.getenv("DB_NAME", "defaultdb")
}

# ── Cloudinary config ────────────────────────────────────────────────
cloudinary.config(
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key    = os.getenv('CLOUDINARY_API_KEY'),
    api_secret = os.getenv('CLOUDINARY_API_SECRET'),
    secure     = True
)

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(**DB_CONFIG)
        g.cursor = g.db.cursor(dictionary=True, buffered=True)
    return g.db, g.cursor

@app.teardown_appcontext
def close_db(exception=None):
    cursor = g.pop('cursor', None)
    db     = g.pop('db', None)
    if cursor: cursor.close()
    if db and db.is_connected(): db.close()

# ── Secure Google OAuth ──────────────────────────────────────────────
oauth  = OAuth(app) if OAuth else None
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
) if oauth else None

# ── APScheduler ───────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def get_username():
    user_data = session.get('user')
    if not user_data: return None
    return user_data.get('username') if isinstance(user_data, dict) else user_data[1]

def get_road_distance(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        response = requests.get(url, timeout=5).json()
        return round(response['routes'][0]['distance'] / 1000, 2)
    except Exception as e:
        print(f"Distance calculation error: {e}")
        return 0

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(email, otp):
    msg = Message("QuickLift OTP Verification",
                  sender=app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = f"<-----------QuickLift---------->\n Your OTP for QuickLift verification is: {otp}"
    mail.send(msg)

# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' in session: return redirect('/dashboard')
    return render_template('index.html')

# ── Google OAuth ──────────────────────────────────────────────
@app.route('/login/google')
def google_login():
    if not google: return redirect('/login')
    return google.authorize_redirect(url_for('google_callback', _external=True))

@app.route('/auth/google/callback')
def google_callback():
    if not google: return redirect('/login')
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        db, cursor = get_db()
        cursor.execute("SELECT * FROM userdata WHERE email=%s", (user_info['email'],))
        db_user = cursor.fetchone()
        session['user'] = db_user if db_user else {
            'username': user_info.get('email').split('@')[0],
            'fullname': user_info.get('name'),
            'email':    user_info.get('email'),
            'is_google': True
        }
        return redirect('/dashboard')
    return redirect('/login')

# ── Login ─────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return render_template('login.html', error="All fields required")
        try:
            db, cursor = get_db()
            cursor.execute("SELECT * FROM userdata WHERE username=%s", (username,))
            result = cursor.fetchone()
            
            if result and check_password_hash(result['passwords'], password):
                session['user'] = result
                return redirect('/dashboard')
            return render_template('login.html', error="Invalid username or password")
        except Exception as e:
            print(f"Login Error: {e}")
            return render_template('login.html', error="Database error. Please try again.")
    return render_template('login.html')

# ── Register ──────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname         = request.form.get('fullname')
        username         = request.form.get('username')
        email            = request.form.get('email')
        contact          = request.form.get('contact')
        city             = request.form.get('city')
        password         = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        gender           = request.form.get('gender')
        file             = request.files.get('file')        # profile photo
        id_file_obj      = request.files.get('id_file')     # ID proof

        if not all([fullname, username, email, contact, city,
                    password, confirm_password, gender, file, id_file_obj]):
            return render_template('register.html', error="Please fill in all fields including photo and ID proof")
        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match")

        db, cursor = get_db()
        cursor.execute("SELECT * FROM userdata WHERE username=%s OR email=%s", (username, email))
        if cursor.fetchone():
            return render_template("register.html", error="Username or email already exists")

        try:
            # Upload to Cloudinary instead of local folder
            profile_upload = cloudinary.uploader.upload(file, folder="quicklift/profiles")
            profile_url = profile_upload.get('secure_url')

            id_upload = cloudinary.uploader.upload(id_file_obj, folder="quicklift/ids")
            id_url = id_upload.get('secure_url')
        except Exception as e:
            print(f"Cloudinary Upload Error: {e}")
            return render_template('register.html', error="Failed to upload files to cloud. Try again.")

        hashed_password = generate_password_hash(password)

        session['register_data'] = {
            "fullname":     fullname,
            "username":     username,
            "email":        email,
            "contact":      contact,
            "city":         city,
            "gender":       gender,
            "file_path":    profile_url, # Now saving Cloudinary URL
            "id_file_path": id_url,      # Now saving Cloudinary URL
            "password":     hashed_password
        }
        otp = generate_otp()
        session['otp']      = otp
        session['otp_type'] = "register"
        send_otp_email(email, otp)
        return render_template("otp.html")
    return render_template('register.html')

# ── Verify OTP ────────────────────────────────────────────────
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    user_otp = request.form.get('otp')
    if user_otp == session.get('otp'):
        if session.get('otp_type') == "register":
            data = session.get('register_data')
            db, cursor = get_db()
            cursor.execute(
                """INSERT INTO userdata
                   (fullname, username, email, phnumber, city, gender, files, id_file, passwords)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (data['fullname'], data['username'], data['email'], data['contact'],
                 data['city'], data['gender'], data['file_path'],
                 data['id_file_path'], data['password'])
            )
            db.commit()
            session.pop('otp', None)
            session.pop('otp_type', None)
            session.pop('register_data', None)
            flash("Registration successful. Please login.")
            return redirect('/login')
        elif session.get('otp_type') == "reset":
            return redirect('/reset-password')
    else:
        return render_template("otp.html", error="Invalid OTP")

# ── Forgot / Reset Password ───────────────────────────────────
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        db, cursor = get_db()
        cursor.execute("SELECT * FROM userdata WHERE email=%s", (email,))
        if not cursor.fetchone():
            return render_template("forgot-password.html", error="Email not found")
        otp = generate_otp()
        session['otp'] = otp; session['otp_type'] = "reset"; session['reset_email'] = email
        send_otp_email(email, otp)
        return render_template("otp.html")
    return render_template("forgot-password.html")

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_password = request.form.get('password')
        email = session.get('reset_email')
        hashed_password = generate_password_hash(new_password)
        
        db, cursor = get_db()
        cursor.execute("UPDATE userdata SET passwords=%s WHERE email=%s", (hashed_password, email))
        db.commit()
        flash("Password updated successfully")
        return redirect('/login')
    return render_template("reset-password.html")

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# ── Dashboard ─────────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/login')
    user_name  = get_username()
    db, cursor = get_db()
    try:
        cursor.execute("DELETE FROM rides WHERE date < CURDATE() OR (date = CURDATE() AND time < CURTIME())")
        db.commit()
    except Exception as e:
        print("Cleanup error:", e); db.rollback()

    cursor.execute("SELECT * FROM rides WHERE username != %s AND seats > 0 ORDER BY date ASC LIMIT 3", (user_name,))
    recent_rides = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE passenger_username = %s", (user_name,))
    booking_count = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM rides WHERE username = %s", (user_name,))
    published_count = cursor.fetchone()['total']
    stats = {
        'co2_saved':      round((booking_count + published_count) * 2.15, 1),
        'network_status': "Active" if recent_rides else "Searching",
        'total_rides':    booking_count + published_count
    }
    return render_template('dashboard.html', user=session['user'], recent_rides=recent_rides, stats=stats)

# ── Publish Ride ──────────────────────────────────────────────
@app.route('/publish', methods=['GET', 'POST'])
def publish():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        start_lat = float(request.form.get('start_lat'))
        start_lon = float(request.form.get('start_lon'))
        dest_lat  = float(request.form.get('dest_lat'))
        dest_lon  = float(request.form.get('dest_lon'))
        leaving_from = request.form.get('leaving_from')
        going_to     = request.form.get('going_to')
        date         = request.form.get('date')
        time         = request.form.get('time')
        seats        = int(request.form.get('seats', '1'))
        vehicle      = request.form.get('vehicle')
        try:
            parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
            today = dt_date.today()
            if parsed_date < today:
                flash("Cannot publish rides in the past.", "error"); return redirect('/publish')
            if parsed_date > today + timedelta(days=15):
                flash("Cannot publish rides more than 15 days in advance.", "error"); return redirect('/publish')
        except Exception: pass
        km = get_road_distance(start_lat, start_lon, dest_lat, dest_lon)
        total_price    = 40 + (km * 12)
        price_per_seat = round(total_price / max(seats, 1), 2)
        user_name  = get_username()
        db, cursor = get_db()
        try:
            cursor.execute(
                """INSERT INTO rides (username, leaving_from, going_to, date, time, seats,
                   vehicle, distance_km, price_per_seat, total_price) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (user_name, leaving_from, going_to, date, time, seats, vehicle, km, price_per_seat, round(total_price, 2))
            )
            db.commit()
            flash("Ride published successfully!", "success")
        except Exception as e:
            print("INSERT FAILED:", e)
        return render_template('publish.html', user=session['user'],
                               calculated_km=km, total_price=round(total_price, 2), price_per_seat=price_per_seat)
    return render_template('publish.html', user=session['user'])

# ── Find Ride ─────────────────────────────────────────────────
@app.route('/find-ride', methods=['GET', 'POST'])
def find_ride():
    if 'user' not in session: return redirect('/login')
    db, cursor = get_db()
    try:
        cursor.execute("DELETE FROM rides WHERE date < CURDATE() OR (date = CURDATE() AND time < CURTIME())")
        db.commit()
    except Exception as e:
        print("Cleanup error:", e); db.rollback()
    if request.method == 'POST':
        leaving_from = request.form.get('from')
        going_to     = request.form.get('to')
        ride_date    = request.form.get('date')
        if ride_date:
            cursor.execute(
                "SELECT * FROM rides WHERE leaving_from LIKE %s AND going_to LIKE %s AND date=%s AND seats>0 ORDER BY date ASC",
                (f"%{leaving_from}%", f"%{going_to}%", ride_date))
        else:
            cursor.execute(
                "SELECT * FROM rides WHERE leaving_from LIKE %s AND going_to LIKE %s AND seats>0 ORDER BY date ASC",
                (f"%{leaving_from}%", f"%{going_to}%"))
    else:
        cursor.execute("SELECT * FROM rides WHERE seats > 0 ORDER BY date ASC")
    rides = cursor.fetchall()
    return render_template('findride.html', user=session['user'], rides=rides)

# ── Reserve & Book ────────────────────────────────────────────
@app.route('/reserve/<int:ride_id>')
def reserve_page(ride_id):
    if 'user' not in session: return redirect('/login')
    db, cursor = get_db()
    cursor.execute("SELECT * FROM rides WHERE id = %s", (ride_id,))
    ride = cursor.fetchone()
    if not ride:
        flash("Ride not found!"); return redirect('/find-ride')
    return render_template('reserve.html', user=session['user'], ride=ride)

@app.route('/book-ride/<int:ride_id>')
def book_ride(ride_id):
    if 'user' not in session: return redirect('/login')
    user_name  = get_username()
    db, cursor = get_db()
    cursor.execute("SELECT username, seats FROM rides WHERE id = %s", (ride_id,))
    ride = cursor.fetchone()
    if not ride or ride['seats'] <= 0:
        flash("Sorry, no seats left for this ride."); return redirect('/find-ride')
    if ride['username'] == user_name:
        flash("You cannot book your own ride."); return redirect('/find-ride')
    try:
        cursor.execute("UPDATE rides SET seats = seats - 1 WHERE id = %s", (ride_id,))
        cursor.execute("INSERT INTO bookings (ride_id, passenger_username) VALUES (%s, %s)", (ride_id, user_name))
        db.commit()
        flash("Booking Successful! Track your driver below.", "success")
        return redirect(f'/track/{ride_id}')
    except Exception as e:
        db.rollback(); print(f"Sync Error: {e}"); return "Database Sync Error", 500

# ── Live Location ─────────────────────────────────────────────
@app.route('/update-location', methods=['POST'])
def update_location():
    if 'user' not in session: return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    lat = data.get('lat'); lon = data.get('lon')
    username = get_username()
    db, cursor = get_db()
    try:
        cursor.execute(
            """INSERT INTO user_locations (username, latitude, longitude) VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE latitude=%s, longitude=%s, updated_at=NOW()""",
            (username, lat, lon, lat, lon))
        db.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"Location update error: {e}"); return jsonify({'error': str(e)}), 500

@app.route('/get-location/<int:ride_id>')
def get_location(ride_id):
    if 'user' not in session: return jsonify({'error': 'unauthorized'}), 401
    db, cursor = get_db()
    cursor.execute("SELECT username FROM rides WHERE id = %s", (ride_id,))
    ride = cursor.fetchone()
    if not ride: return jsonify({'error': 'ride not found'}), 404
    cursor.execute("SELECT latitude, longitude, updated_at FROM user_locations WHERE username = %s", (ride['username'],))
    loc = cursor.fetchone()
    if loc and loc['latitude']:
        return jsonify({'lat': loc['latitude'], 'lon': loc['longitude'], 'updated_at': str(loc['updated_at'])})
    return jsonify({'error': 'location not available yet'})

@app.route('/track/<int:ride_id>')
def track_ride(ride_id):
    if 'user' not in session: return redirect('/login')
    db, cursor = get_db()
    cursor.execute("SELECT * FROM rides WHERE id = %s", (ride_id,))
    ride = cursor.fetchone()
    if not ride:
        flash("Ride not found."); return redirect('/insights')
    cursor.execute("SELECT phnumber, fullname FROM userdata WHERE username = %s", (ride['username'],))
    driver = cursor.fetchone()
    return render_template('tracking.html', user=session['user'], ride=ride, driver=driver, ride_id=ride_id)

@app.route('/check-ride/<int:ride_id>')
def check_ride(ride_id):
    if 'user' not in session: return jsonify({'error': 'unauthorized'}), 401
    db, cursor = get_db()
    cursor.execute("SELECT id FROM rides WHERE id = %s", (ride_id,))
    return jsonify({'exists': cursor.fetchone() is not None})

# ── Insights ──────────────────────────────────────────────────
@app.route('/insights')
def insights():
    if 'user' not in session: return redirect('/login')
    user_name  = get_username()
    db, cursor = get_db()
    cursor.execute("""
        SELECT r.id as ride_id, r.leaving_from, r.going_to, r.date, r.time,
               r.price_per_seat, r.vehicle, r.username as driver_username,
               b.id as booking_id, b.status, b.booking_date
        FROM bookings b JOIN rides r ON b.ride_id = r.id
        WHERE b.passenger_username = %s ORDER BY b.booking_date DESC
    """, (user_name,))
    bookings = cursor.fetchall()
    cursor.execute("""
        SELECT r.*, COUNT(b.id) as passenger_count
        FROM rides r LEFT JOIN bookings b ON b.ride_id = r.id
        WHERE r.username = %s GROUP BY r.id ORDER BY r.date ASC
    """, (user_name,))
    published = cursor.fetchall()
    stats = {
        'carbon_saved': round(len(bookings) * 2.15, 2),
        'total_rides':  len(bookings) + len(published)
    }
    return render_template('insights.html', user=session['user'],
                           bookings=bookings, published=published, stats=stats)

# ── Unbook ────────────────────────────────────────────────────
@app.route('/unbook/<int:booking_id>', methods=['POST'])
def unbook_ride(booking_id):
    if 'user' not in session: return redirect('/login')
    user_name  = get_username()
    db, cursor = get_db()
    cursor.execute("SELECT b.id, b.ride_id FROM bookings b WHERE b.id = %s AND b.passenger_username = %s",
                   (booking_id, user_name))
    booking = cursor.fetchone()
    if not booking:
        flash("Booking not found or unauthorized.", "error"); return redirect('/insights')
    try:
        cursor.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
        cursor.execute("UPDATE rides SET seats = seats + 1 WHERE id = %s", (booking['ride_id'],))
        db.commit()
        flash("Booking cancelled. Seat has been released.", "success")
    except Exception as e:
        db.rollback(); print(f"Unbook error: {e}"); flash("Something went wrong.", "error")
    return redirect('/insights')

# ── Cancel Ride ───────────────────────────────────────────────
@app.route('/cancel-ride/<int:ride_id>', methods=['POST'])
def cancel_ride(ride_id):
    if 'user' not in session: return redirect('/login')
    user_name  = get_username()
    db, cursor = get_db()
    cursor.execute("SELECT * FROM rides WHERE id = %s AND username = %s", (ride_id, user_name))
    ride = cursor.fetchone()
    if not ride:
        flash("Ride not found or unauthorized.", "error"); return redirect('/insights')
    cursor.execute("""
        SELECT u.email, u.fullname FROM bookings b
        JOIN userdata u ON b.passenger_username = u.username WHERE b.ride_id = %s
    """, (ride_id,))
    passengers = cursor.fetchall()
    try:
        cursor.execute("DELETE FROM bookings WHERE ride_id = %s", (ride_id,))
        cursor.execute("DELETE FROM rides WHERE id = %s", (ride_id,))
        db.commit()
        for passenger in passengers:
            try:
                msg = Message(subject="⚠️ QuickLift — Your ride has been cancelled",
                              sender=app.config['MAIL_USERNAME'], recipients=[passenger['email']])
                msg.body = f"<----------- QuickLift ----------->\n\nHi {passenger['fullname']},\n\nYour upcoming ride has been cancelled by the driver.\n\nCANCELLED RIDE:\n  From  : {ride['leaving_from']}\n  To    : {ride['going_to']}\n  Date  : {ride['date']} at {ride['time']}\n  Driver: @{ride['username']}\n\nPlease find another ride:\n  http://127.0.0.1:5000/find-ride\n\n— QuickLift Team"
                mail.send(msg)
            except Exception as e:
                print(f"Email error for {passenger['email']}: {e}")
        flash(f"Ride cancelled. {len(passengers)} passenger(s) notified by email.", "success")
    except Exception as e:
        db.rollback(); print(f"Cancel ride error: {e}"); flash("Something went wrong.", "error")
    return redirect('/insights')

# ── Ride Passengers ───────────────────────────────────────────
@app.route('/ride-passengers/<int:ride_id>')
def ride_passengers(ride_id):
    if 'user' not in session: return redirect('/login')
    user_name  = get_username()
    db, cursor = get_db()
    cursor.execute("SELECT * FROM rides WHERE id = %s AND username = %s", (ride_id, user_name))
    ride = cursor.fetchone()
    if not ride:
        flash("Ride not found or unauthorized."); return redirect('/insights')
    cursor.execute("""
        SELECT u.fullname, u.username, u.phnumber, u.city, u.gender, u.files,
               b.id as booking_id, b.booking_date
        FROM bookings b JOIN userdata u ON b.passenger_username = u.username
        WHERE b.ride_id = %s ORDER BY b.booking_date ASC
    """, (ride_id,))
    passengers = cursor.fetchall()
    return render_template('ride_passengers.html', user=session['user'], ride=ride, passengers=passengers)

# ── Profile — view ────────────────────────────────────────────
@app.route('/profile/<username>')
def profile(username):
    if 'user' not in session: return redirect('/login')
    db, cursor = get_db()
    cursor.execute("SELECT * FROM userdata WHERE username = %s", (username,))
    profile_user = cursor.fetchone()
    if not profile_user:
        flash("User not found."); return redirect('/dashboard')
    cursor.execute("SELECT COUNT(*) as total FROM rides WHERE username = %s", (username,))
    rides_published = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE passenger_username = %s", (username,))
    rides_taken = cursor.fetchone()['total']
    stats = {
        'rides_published': rides_published,
        'rides_taken':     rides_taken,
        'co2_saved':       round((rides_published + rides_taken) * 2.15, 1)
    }
    return render_template('profile.html', user=session['user'], profile=profile_user,
                           stats=stats, current_user=get_username())

# ── Profile — edit ────────────────────────────────────────────
@app.route('/edit-profile', methods=['POST'])
def edit_profile():
    if 'user' not in session: return redirect('/login')
    user_name    = get_username()
    db, cursor   = get_db()
    fullname     = request.form.get('fullname')
    new_username = request.form.get('username')
    city         = request.form.get('city')
    phnumber     = request.form.get('phnumber')
    photo        = request.files.get('photo')

    if new_username != user_name:
        cursor.execute("SELECT id FROM userdata WHERE username = %s", (new_username,))
        if cursor.fetchone():
            flash("Username already taken.", "error")
            return redirect(f'/profile/{user_name}')
    try:
        if photo and photo.filename:
            # Upload new photo to Cloudinary
            profile_upload = cloudinary.uploader.upload(photo, folder="quicklift/profiles")
            file_path = profile_upload.get('secure_url')
            
            cursor.execute(
                "UPDATE userdata SET fullname=%s, username=%s, city=%s, phnumber=%s, files=%s WHERE username=%s",
                (fullname, new_username, city, phnumber, file_path, user_name)
            )
        else:
            cursor.execute(
                "UPDATE userdata SET fullname=%s, username=%s, city=%s, phnumber=%s WHERE username=%s",
                (fullname, new_username, city, phnumber, user_name)
            )
        db.commit()
        cursor.execute("SELECT * FROM userdata WHERE username = %s", (new_username,))
        session['user'] = cursor.fetchone()
        flash("Profile updated successfully!", "success")
        return redirect(f'/profile/{new_username}')
    except Exception as e:
        db.rollback(); print(f"Edit profile error: {e}")
        flash("Something went wrong. Please try again.", "error")
        return redirect(f'/profile/{user_name}')

# ── Scheduler ─────────────────────────────────────────────────
def send_ride_notifications():
    try:
        notif_db     = mysql.connector.connect(**DB_CONFIG)
        notif_cursor = notif_db.cursor(dictionary=True)
        notif_cursor.execute("""
            SELECT r.id, r.username, r.leaving_from, r.going_to, r.date, r.time,
                   u.phnumber, u.fullname, ul.latitude, ul.longitude
            FROM rides r JOIN userdata u ON r.username = u.username
            LEFT JOIN user_locations ul ON r.username = ul.username
            WHERE r.date = CURDATE()
              AND r.time BETWEEN ADDTIME(CURTIME(), '00:04:00') AND ADDTIME(CURTIME(), '00:06:00')
        """)
        upcoming_rides = notif_cursor.fetchall()
        for ride in upcoming_rides:
            notif_cursor.execute("""
                SELECT b.passenger_username, u.email, u.fullname FROM bookings b
                JOIN userdata u ON b.passenger_username = u.username
                WHERE b.ride_id = %s AND b.status = 'Booked'
            """, (ride['id'],))
            passengers = notif_cursor.fetchall()
            location_text = (
                f"Driver's current location: https://www.google.com/maps?q={ride['latitude']},{ride['longitude']}"
                if ride['latitude'] and ride['longitude']
                else "Driver location not available yet. Please contact them directly."
            )
            for passenger in passengers:
                try:
                    msg = Message(subject="🚗 QuickLift — Your ride departs in 5 minutes!",
                                  sender=app.config['MAIL_USERNAME'], recipients=[passenger['email']])
                    msg.body = f"<----------- QuickLift ----------->\n\nHi {passenger['fullname']},\n\nYour ride departs in ~5 minutes!\n\nFrom: {ride['leaving_from']}\nTo  : {ride['going_to']}\nDriver: {ride['fullname']} (@{ride['username']})\nPhone : {ride['phnumber']}\n\n{location_text}\n\nTrack live: http://127.0.0.1:5000/track/{ride['id']}\n\nSafe travels!\n— QuickLift Team"
                    with app.app_context(): mail.send(msg)
                except Exception as e:
                    print(f"Email error for {passenger['email']}: {e}")
        notif_cursor.close(); notif_db.close()
    except Exception as e:
        print(f"Scheduler error: {e}")

scheduler.add_job(func=send_ride_notifications, trigger='interval', seconds=60,
                  id='ride_notification_job', replace_existing=True)

if __name__ == "__main__":
    app.run(debug=True)


from werkzeug.exceptions import RequestEntityTooLarge

@app.errorhandler(RequestEntityTooLarge)
def handle_file_size_error(e):
    flash("One of your files is too large! Please ensure photos are under 10MB.", "error")
    return redirect(request.url)