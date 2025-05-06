#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"  // create this with your Wi-Fi creds

// OLED setup
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// MQTT
WiFiClient   espClient;
PubSubClient mqttClient(espClient);

// stores last prices
std::map<String, float> prices;
std::vector<String>    coinList = { "bitcoin", "ethereum", "cardano" };
int idx = 0;

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<200> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) return;
  float price = doc["price"];
  String t = String(topic);
  String coin = t.substring(t.lastIndexOf('/') + 1);
  prices[coin] = price;
}

void connectMQTT() {
  while (!mqttClient.connected()) {
    if (mqttClient.connect("ESP32Client")) {
      mqttClient.subscribe("crypto/price/#");
    } else {
      delay(2000);
    }
  }
}

void setup() {
  connectWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.clearDisplay();
}

void loop() {
  if (!mqttClient.connected()) connectMQTT();
  mqttClient.loop();

  // cycle through coins
  if (!coinList.empty()) {
    String coin = coinList[idx++ % coinList.size()];
    float price = prices[coin];

    display.clearDisplay();
    display.setTextSize(2);
    display.setCursor(0, 10);
    display.print(coin);
    display.setCursor(0, 35);
    display.print(price);
    display.print(" USD");
    display.display();
  }
  delay(3000);
}