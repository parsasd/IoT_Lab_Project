import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time, json
import requests
import paho.mqtt.client as mqtt
from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_PREFIX,
    COIN_LIST, VS_CURRENCY, PUBLISH_INTERVAL
)

def fetch_prices(coins, vs_currency):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(coins),
        "vs_currencies": vs_currency
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    return res.json()  # e.g. {"bitcoin":{"usd":12345}, ...}

def main():
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()

    while True:
        try:
            data = fetch_prices(COIN_LIST, VS_CURRENCY)
            ts = int(time.time())
            for coin, vals in data.items():
                price = vals[VS_CURRENCY]
                topic = f"{MQTT_TOPIC_PREFIX}/{coin}"
                payload = json.dumps({"price": price, "timestamp": ts})
                client.publish(topic, payload, qos=1)
                print(f"Published {coin}@{price} to {topic}")
        except Exception as e:
            print("Error fetching/publishing:", e)
        time.sleep(PUBLISH_INTERVAL)

if __name__ == "__main__":
    main()