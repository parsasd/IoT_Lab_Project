import os
import sys
# ensure project root is on PYTHONPATH for config import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging # Added for better logging
import datetime # Added for context_processor
from flask import Flask, render_template, redirect, url_for, request, flash, current_app
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail # Message class is imported in email_utils
from flask_apscheduler import APScheduler
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
import requests
import time

# Attempt to import from config.py at the project root
try:
    from config import SECRET_KEY, SQLALCHEMY_DATABASE_URI, MAIL_SERVER, \
                       MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, \
                       COIN_LIST, VS_CURRENCY, APSCHEDULER_API_ENABLED
except ImportError:
    # Fallback if config.py is not found (useful for isolated testing, but ensure it exists for real runs)
    print("WARNING: config.py not found or not on PYTHONPATH. Using default/empty values for configuration.")
    SECRET_KEY = 'your_default_secret_key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///default.db'
    MAIL_SERVER = 'smtp.example.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'user@example.com'
    MAIL_PASSWORD = 'password'
    COIN_LIST = ['bitcoin', 'ethereum']
    VS_CURRENCY = 'usd'
    APSCHEDULER_API_ENABLED = True


from models import db, User, Alert # User model is crucial here
from email_utils import send_email

app = Flask(__name__)

# Configuration from config.py (or defaults if import failed)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recommended to disable
app.config['MAIL_SERVER'] = MAIL_SERVER
app.config['MAIL_PORT'] = MAIL_PORT
app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
app.config['APSCHEDULER_API_ENABLED'] = APSCHEDULER_API_ENABLED


# Ensure Flask-Mail has a default sender
app.config['MAIL_DEFAULT_SENDER'] = app.config.get('MAIL_USERNAME') or 'no-reply@example.com'

# Initialize database
db.init_app(app)
with app.app_context():
    db.create_all()

# Initialize Mail
mail = Mail(app)

# Login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info' # Optional: for styling flash messages

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Basic Logging Configuration
logging.basicConfig(level=logging.INFO)
# You can also configure app.logger specifically, e.g.:
# app.logger.setLevel(logging.INFO)
# handler = logging.StreamHandler(sys.stdout)
# handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
# app.logger.addHandler(handler)


@app.context_processor
def inject_now():
    """Injects the current UTC datetime into templates."""
    return {'now': datetime.datetime.utcnow(), 'VS_CURRENCY': VS_CURRENCY}


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template('register.html')

        # Prevent duplicate registration
        if User.query.filter_by(email=email).first():
            flash("That email is already registered. Please log in.", "warning")
            return redirect(url_for('login'))

        pwd_hash  = generate_password_hash(password)
        # Generate a 6-digit confirmation code
        code = ''.join(random.choices(string.digits, k=6))
        new_user = User(email=email, password=pwd_hash, confirm_code=code)
        try:
            db.session.add(new_user)
            db.session.commit()
            send_email(email, "Your confirmation code", f"Your confirmation code is: {code}")
            flash("Confirmation code sent to your email. Please check your inbox (and spam folder).", "success")
            return redirect(url_for('confirm', email=email))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during registration for {email}: {e}")
            flash("An error occurred during registration. Please try again.", "danger")

    return render_template('register.html')

@app.route('/confirm', methods=['GET','POST'])
def confirm():
    email = request.args.get('email')
    if not email:
        flash("No email provided for confirmation.", "danger")
        return redirect(url_for('register'))

    user_to_confirm = User.query.filter_by(email=email).first()

    if not user_to_confirm:
        flash("User not found for this email.", "danger")
        return redirect(url_for('register'))

    if user_to_confirm.confirmed:
        flash("This email has already been confirmed. Please log in.", "info")
        return redirect(url_for('login'))

    if request.method == 'POST':
        code_entered = request.form.get('code')
        if not code_entered:
            flash("Please enter the confirmation code.", "warning")
        elif code_entered == user_to_confirm.confirm_code:
            user_to_confirm.confirmed = True
            db.session.commit()
            flash("Email confirmed successfully. Please log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Invalid confirmation code. Please try again.", "danger")

    return render_template('confirm.html', email=email)


@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_to_login = User.query.filter_by(email=email).first()

        if user_to_login and check_password_hash(user_to_login.password, password):
            if user_to_login.confirmed:
                login_user(user_to_login)
                flash('Logged in successfully!', 'success')
                # Redirect to next page if it exists, otherwise dashboard
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash("Your email is not confirmed. Please check your email for the confirmation code.", "warning")
                return redirect(url_for('confirm', email=email))
        else:
            flash("Invalid email or password. Please try again.", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    alerts = Alert.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', alerts=alerts)

@app.route('/alert/new', methods=['GET','POST'])
@login_required
def new_alert():
    if request.method == 'POST':
        coin = request.form.get('coin')
        try:
            threshold = float(request.form.get('threshold'))
        except (ValueError, TypeError):
            flash("Invalid threshold value. Please enter a number.", "danger")
            return render_template('alert_form.html', coins=COIN_LIST, VS_CURRENCY=VS_CURRENCY) # Pass VS_CURRENCY

        direction = request.form.get('direction')

        if not all([coin, threshold is not None, direction]):
            flash("All fields are required.", "danger")
        elif coin not in COIN_LIST:
            flash("Invalid coin selected.", "danger")
        elif direction not in ['above', 'below']:
            flash("Invalid direction selected.", "danger")
        else:
            new_alert_obj = Alert(
                user_id=current_user.id,
                coin=coin,
                threshold=threshold,
                direction=direction
            )
            try:
                db.session.add(new_alert_obj)
                db.session.commit()
                flash("Alert created successfully.", "success")
                return redirect(url_for('dashboard'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating alert for user {current_user.id}: {e}")
                flash("An error occurred while creating the alert. Please try again.", "danger")

    return render_template('alert_form.html', coins=COIN_LIST, VS_CURRENCY=VS_CURRENCY) # Pass VS_CURRENCY

@scheduler.task('interval', id='check_alerts', seconds=60, misfire_grace_time=90) # Increased misfire_grace_time
def check_alerts():
    current_app.logger.info("Scheduler: Running check_alerts job.")
    with app.app_context(): # Ensure app context for DB and mail operations
        alerts_to_check = Alert.query.filter_by(sent=False).all()
        if not alerts_to_check:
            current_app.logger.info("Scheduler: No pending alerts to check.")
            return

        # Efficiently gather unique coin IDs from pending alerts
        coin_ids_to_fetch = list(set(a.coin for a in alerts_to_check if a.coin in COIN_LIST))

        if not coin_ids_to_fetch:
            current_app.logger.info("Scheduler: No alerts for coins in COIN_LIST to check prices for.")
            return

        current_app.logger.info(f"Scheduler: Fetching prices for coins: {', '.join(coin_ids_to_fetch)}")
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": ",".join(coin_ids_to_fetch), "vs_currencies": VS_CURRENCY},
                timeout=10 # Added timeout
            )
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            prices_data = response.json()
        except requests.exceptions.Timeout:
            current_app.logger.error("Scheduler: CoinGecko API request timed out.")
            return
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Scheduler: Failed to fetch prices from CoinGecko: {e}")
            return
        except ValueError as e: # Catches JSON decoding errors
            current_app.logger.error(f"Scheduler: Failed to decode JSON from CoinGecko: {e}. Response: {response.text if 'response' in locals() else 'N/A'}")
            return

        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC")
        users_cache = {} # Cache user objects to avoid redundant DB queries

        for alert_item in alerts_to_check:
            # Get the user for this alert
            if alert_item.user_id in users_cache:
                user = users_cache[alert_item.user_id]
            else:
                user = User.query.get(alert_item.user_id)
                if user:
                    users_cache[alert_item.user_id] = user
                else:
                    current_app.logger.warning(f"Scheduler: User with ID {alert_item.user_id} not found for alert ID {alert_item.id}. Skipping.")
                    continue # Skip this alert if user not found

            # Get price for the specific coin of the alert
            coin_price_data = prices_data.get(alert_item.coin)
            if not coin_price_data or VS_CURRENCY not in coin_price_data:
                current_app.logger.warning(f"Scheduler: Price not found for coin {alert_item.coin} (vs {VS_CURRENCY}). Alert ID: {alert_item.id}")
                continue

            try:
                current_price = float(coin_price_data[VS_CURRENCY])
            except (ValueError, TypeError):
                current_app.logger.warning(f"Scheduler: Invalid price format for {alert_item.coin}: {coin_price_data[VS_CURRENCY]}. Alert ID: {alert_item.id}")
                continue


            alert_triggered = False
            if alert_item.direction == "above" and current_price > alert_item.threshold:
                alert_triggered = True
            elif alert_item.direction == "below" and current_price < alert_item.threshold:
                alert_triggered = True

            if alert_triggered:
                current_app.logger.info(f"Scheduler: Alert triggered for user {user.email}, coin {alert_item.coin}, price {current_price}, threshold {alert_item.threshold}")
                try:
                    send_email(
                        user.email,
                        f"Crypto Alert: {alert_item.coin} {alert_item.direction} {alert_item.threshold} {VS_CURRENCY.upper()}",
                        f"Hello {user.email.split('@')[0]},\n\n"
                        f"This is an alert from Crypto IoT.\n"
                        f"As of {ts}, the price of {alert_item.coin.capitalize()} is {current_price:.2f} {VS_CURRENCY.upper()}.\n"
                        f"This has triggered your alert set for when the price goes {alert_item.direction} {alert_item.threshold:.2f} {VS_CURRENCY.upper()}.\n\n"
                        f"Regards,\nThe Crypto IoT Team"
                    )
                    alert_item.sent = True # Mark as sent
                    current_app.logger.info(f"Scheduler: Successfully sent alert email to {user.email} for alert ID {alert_item.id}")
                except Exception as e:
                    current_app.logger.error(f"Scheduler: Failed to send email to {user.email} for alert ID {alert_item.id}: {e}")
        try:
            db.session.commit() # Commit all changes (e.g., alert_item.sent = True)
            current_app.logger.info("Scheduler: Committed session changes after checking alerts.")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Scheduler: Error committing session after checking alerts: {e}")


if __name__ == '__main__':
    # For development only; use a real WSGI server (e.g., Gunicorn, uWSGI) in production
    # Ensure the host is accessible if running in a container or VM
    # Debug mode should be False in production
    app.run(host='0.0.0.0', port=5000, debug=False)
