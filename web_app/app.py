import os, sys
# ensure project root is on PYTHONPATH for config import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, redirect, url_for, request, flash, current_app
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_apscheduler import APScheduler
from werkzeug.security import generate_password_hash, check_password_hash
import random, string, requests, time
import datetime

from config import *
from models import db, User, Alert
from email_utils import send_email

@context_processor
def inject_now():
    return {'now': datetime.datetime.utcnow()}
app = Flask(__name__)

app.config.from_object("config")

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        # Prevent duplicate registration
        if User.query.filter_by(email=email).first():
            flash("That email is already registered. Please log in.", "warning")
            return redirect(url_for('login'))

        pwd  = generate_password_hash(request.form['password'])
        code = ''.join(random.choices(string.digits, k=6))
        u = User(email=email, password=pwd, confirm_code=code)
        db.session.add(u)
        db.session.commit()

        send_email(email, "Your confirmation code", f"Code: {code}")
        flash("Confirmation code sent to your email", "success")
        return redirect(url_for('confirm', email=email))

    return render_template('register.html')

@app.route('/confirm', methods=['GET','POST'])
def confirm():
    email = request.args.get('email')
    u = User.query.filter_by(email=email).first_or_404()

    if request.method == 'POST':
        if request.form['code'] == u.confirm_code:
            u.confirmed = True
            db.session.commit()
            flash("Email confirmed. Please log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Wrong code.", "danger")

    return render_template('confirm.html', email=email)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password, request.form['password']) and u.confirmed:
            login_user(u)
            return redirect(url_for('dashboard'))
        flash("Invalid credentials or email not confirmed.", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
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
        a = Alert(
            user_id=current_user.id,
            coin=request.form['coin'],
            threshold=float(request.form['threshold']),
            direction=request.form['direction']
        )
        db.session.add(a)
        db.session.commit()
        flash("Alert created.", "success")
        return redirect(url_for('dashboard'))
    return render_template('alert_form.html', coins=COIN_LIST)

@scheduler.task('interval', id='check_alerts', seconds=60, misfire_grace_time=30)
def check_alerts():
    # Run inside app context so DB/session and mail work
    with app.app_context():
        alerts = Alert.query.filter_by(sent=False).all()
        if not alerts:
            return

        # Fetch current prices
        # It's more efficient to get all coin prices once
        coin_ids_to_fetch = list(set(a.coin for a in alerts if a.coin in COIN_LIST))
        if not coin_ids_to_fetch: # handles case where alerts are for coins not in COIN_LIST
            current_app.logger.warning("No alerts for coins in COIN_LIST to check.")
            return

        try:
            res = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": ",".join(coin_ids_to_fetch), "vs_currencies": VS_CURRENCY}
            )
            res.raise_for_status()  # Raise an exception for HTTP errors
            prices_data = res.json()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Failed to fetch prices from CoinGecko: {e}")
            return # Skip this run if API call fails
        except ValueError as e: # Catches JSON decoding errors
            current_app.logger.error(f"Failed to decode JSON from CoinGecko: {e}")
            return


        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        users_cache = {} # Cache user objects to avoid redundant queries

        for a in alerts:
            # Get the user for this alert
            if a.user_id in users_cache:
                user = users_cache[a.user_id]
            else:
                user = User.query.get(a.user_id)
                if user:
                    users_cache[a.user_id] = user
                else:
                    current_app.logger.warning(f"User with ID {a.user_id} not found for alert ID {a.id}. Skipping.")
                    continue # Skip this alert if user not found

            price = prices_data.get(a.coin, {}).get(VS_CURRENCY)

            if price is None:
                current_app.logger.warning(f"Price not found for coin {a.coin} (vs {VS_CURRENCY}). Alert ID: {a.id}")
                continue

            price = float(price) # Ensure price is a float for comparison

            if (a.direction == "above" and price > a.threshold) or \
               (a.direction == "below" and price < a.threshold):
                try:
                    send_email(
                        user.email, # Now using the explicitly fetched user's email
                        f"Alert: {a.coin} {a.direction} {a.threshold}",
                        f"At {ts}, {a.coin} price is {price} {VS_CURRENCY.upper()}"
                    )
                    a.sent = True
                    current_app.logger.info(f"Sent alert for coin {a.coin} to {user.email}")
                except Exception as e:
                    current_app.logger.error(f"Failed to send email to {user.email} for alert ID {a.id}: {e}")


        db.session.commit()

if __name__ == '__main__':
    # For development only; use a real WSGI server in production
    app.run(host='0.0.0.0', port=5000, debug=False)