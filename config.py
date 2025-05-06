# config.py
# ============ MQTT (pi_collector & esp32) ============
MQTT_BROKER       = "localhost"      # or your broker IP
MQTT_PORT         = 1883
MQTT_TOPIC_PREFIX = "crypto/price"  # final topic: crypto/price/<coin>

COIN_LIST         = ["bitcoin", "ethereum", "cardano"]
VS_CURRENCY       = "usd"
PUBLISH_INTERVAL  = 10               # seconds between publishes

# ============ Web app ============
SECRET_KEY                = "change-this-to-a-secure-random-string"
SQLALCHEMY_DATABASE_URI   = "sqlite:///app.db"
MAIL_SERVER               = "smtp.gmail.com"
MAIL_PORT                 = 587
MAIL_USERNAME             = "parsasedighi70@gmail.com"
MAIL_PASSWORD             = "Parsa1234"
MAIL_USE_TLS              = True

# ============ Simulation defaults ============
INDICATOR_WINDOWS = {
    "short": {"sma": 10, "ema": 10, "rsi": 7, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "bb_window": 20},
    "long":  {"sma": 50, "ema": 50, "rsi": 14, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "bb_window": 20},
}