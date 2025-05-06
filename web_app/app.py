import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, redirect, url_for, request, flash, current_app
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail
from flask_apscheduler import APScheduler
from werkzeug.security import generate_password_hash, check_password_hash
import random, string, requests, time

from config import *
from models import db, User, Alert
from email_utils import send_email

app = Flask(__name__)
app.config.from_object("config")

# Initialize database and create tables
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
    # Run inside app context for DB & Mail
    with app.app_context():
        alerts = Alert.query.filter_by(sent=False).all()
        if not alerts:
            return

        # Fetch current prices
        res = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ",".join(COIN_LIST), "vs_currencies": VS_CURRENCY}
        ).json()

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        for a in alerts:
            price = res.get(a.coin, {}).get(VS_CURRENCY)
            if price is None:
                continue
            if (a.direction == "above" and price > a.threshold) or \
               (a.direction == "below" and price < a.threshold):
                # Send alert to the user’s email
                send_email(
                    a.user.email,
                    f"Alert: {a.coin} {a.direction} {a.threshold}",
                    f"At {ts}, {a.coin} price is {price}"
                )
                a.sent = True

        db.session.commit()

if __name__ == '__main__':
    # For local development only; in production use a WSGI server
    app.run(host='0.0.0.0', port=5000, debug=True)