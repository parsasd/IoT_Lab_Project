from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(128), nullable=False)
    confirmed  = db.Column(db.Boolean, default=False)
    confirm_code = db.Column(db.String(6))  # 6-digit code

class Alert(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    coin        = db.Column(db.String(50), nullable=False)
    threshold   = db.Column(db.Float, nullable=False)
    direction   = db.Column(db.String(4), nullable=False)  # 'above' or 'below'
    sent        = db.Column(db.Boolean, default=False)