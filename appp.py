# from flask import Flask, request, redirect, render_template, url_for, session
# from authlib.integrations.flask_client import OAuth
# import mysql.connector
# import os

# app = Flask(__name__)
# # Change this to a random string for security
# app.secret_key = "any_hello_world_patelbhaihere" 

# # --- GOOGLE OAUTH SETUP ---
# oauth = OAuth(app)
# google = oauth.register(
#     name='google',
#     client_id='853368867067-agsdp0bjm4c4q56j29pjrppqlh0fff63.apps.googleusercontent.com', # From Google Cloud Console
#     client_secret='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', # From Google Cloud Console
#     server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
#     client_kwargs={'scope': 'openid email profile'}
# )

# # Database connection
# db = mysql.connector.connect(
#     host="localhost",
#     user="root",
#     password="Patel_2101",
#     database="quicklift"
# )
# cursor = db.cursor(dictionary=True) # dictionary=True helps access data like user['fullname']

# # Configuration for file uploads
# UPLOAD_FOLDER = "uploads"
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# # --- GOOGLE AUTH ROUTES ---

# @app.route('/login/google')
# def google_login():
#     # This sends the user to Google's login page
#     redirect_uri = url_for('google_callback', _external=True)
#     return google.authorize_redirect(redirect_uri)

# @app.route('/auth/google/callback')
# def google_callback():
#     token = google.authorize_access_token()
#     user_info = token.get('userinfo')
    
#     if user_info:
#         # We store the Google info in the session
#         session['user'] = {
#             'fullname': user_info.get('name'),
#             'email': user_info.get('email'),
#             'picture': user_info.get('picture')
#         }
#         return redirect(url_for('dashboard'))
    
#     return redirect(url_for('login'))

# # --- LOGIN ROUTE ---

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         username = request.form.get('username')
#         password = request.form.get('password')
        
#         if not username or not password:
#             return render_template('login.html', error="All Fields required to be filled")
        
#         query = "SELECT * FROM userdata WHERE username=%s AND passwords=%s"
#         cursor.execute(query, (username, password))
#         result = cursor.fetchone()
        
#         if result:
#             session['user'] = result
#             return redirect(url_for('dashboard'))
#         else:
#             return render_template('login.html', error="Invalid credentials")
            
#     return render_template('login.html')

# # --- DASHBOARD ---

# @app.route('/dashboard')
# def dashboard():
#     if 'user' not in session:
#         return redirect(url_for('login'))
#     # You can now use user.fullname or user.email in your dashboard.html
#     return render_template('dashboard.html', user=session['user'])

# # --- LOGOUT ---

# @app.route('/logout')
# def logout():
#     session.pop('user', None)
#     return redirect(url_for('login'))

# if __name__ == "__main__":
#     app.run(debug=True)