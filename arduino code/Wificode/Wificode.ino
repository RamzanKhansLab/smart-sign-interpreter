#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

#define LED LED_BUILTIN

String WIFI_SSID = "";
String WIFI_PASS = "";
String API_URL   = "";
bool configured  = false;

WiFiClientSecure secureClient;
unsigned long lastCheck = 0;

void ledON()  { digitalWrite(LED, LOW);  }
void ledOFF() { digitalWrite(LED, HIGH); }
void dbg(String msg) { Serial.println("DBG:" + msg); }

void setup() {
  Serial.begin(9600);
  pinMode(LED, OUTPUT);
  ledOFF();

  // Skip SSL certificate verification (Render.com uses valid cert but
  // ESP8266 has no CA store — this is fine for sensor data)
  secureClient.setInsecure();

  unsigned long start = millis();
  while (millis() - start < 5000) {
    Serial.println("ESP_READY");
    delay(300);
  }

  dbg("Boot complete. Waiting for CONFIG.");
}

void loop() {
  if (millis() - lastCheck > 2000) {
    lastCheck = millis();
    if (configured) {
      if (WiFi.status() == WL_CONNECTED) {
        ledON();
        dbg("WIFI:CONNECTED IP=" + WiFi.localIP().toString());
      } else {
        ledOFF();
        dbg("WIFI:DROPPED");
      }
    } else {
      ledOFF();
      dbg("STATUS:WAITING_FOR_CONFIG");
    }
  }

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;
    dbg("RAW:" + line);
    if (line.charAt(0) == '{' && line.charAt(line.length() - 1) == '}') {
      handleCommand(line);
    } else {
      dbg("SKIP_NON_JSON");
    }
  }
}

void handleCommand(String raw) {
  StaticJsonDocument<1024> doc;
  DeserializationError err = deserializeJson(doc, raw);

  if (err) {
    Serial.println("ERR:JSON_PARSE:" + String(err.c_str()));
    return;
  }

  String cmd = doc["cmd"].as<String>();
  dbg("CMD:" + cmd);

  // ── CONFIG ──────────────────────────────────────────
  if (cmd == "CONFIG") {
    WIFI_SSID = doc["ssid"].as<String>();
    WIFI_PASS = doc["pass"].as<String>();
    API_URL   = doc["url"].as<String>();

    dbg("SSID=" + WIFI_SSID);
    dbg("URL=" + API_URL);

    WiFi.disconnect();
    delay(100);
    WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      dbg("WIFI_TRY:" + String(attempts));
      delay(500);
      attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      configured = true;
      ledON();
      Serial.println("WIFI_OK:" + WiFi.localIP().toString());
    } else {
      configured = false;
      ledOFF();
      Serial.println("ERR:WIFI_FAIL");
    }
  }

  // ── POST ─────────────────────────────────────────────
  else if (cmd == "POST") {
    if (!configured || WiFi.status() != WL_CONNECTED) {
      Serial.println("ERR:NOT_CONFIGURED");
      return;
    }

    // ── Build payload exactly as backend expects ──
    // {
    //   "channels": {"s1":..,"s2":..,"s3":..,"s4":..,"s5":..},
    //   "imu": {"ax":0,"ay":0,"az":0,"gx":0,"gy":0,"gz":0},
    //   "timestamp": ...
    // }
    StaticJsonDocument<512> payload;

    JsonObject channels = payload.createNestedObject("channels");
    channels["s1"] = doc["s1"] | 0;
    channels["s2"] = doc["s2"] | 0;
    channels["s3"] = doc["s3"] | 0;
    channels["s4"] = doc["s4"] | 0;
    channels["s5"] = doc["s5"] | 0;

    JsonObject imu = payload.createNestedObject("imu");
    imu["ax"] = doc["ax"] | 0.0;
    imu["ay"] = doc["ay"] | 0.0;
    imu["az"] = doc["az"] | 0.0;
    imu["gx"] = doc["gx"] | 0.0;
    imu["gy"] = doc["gy"] | 0.0;
    imu["gz"] = doc["gz"] | 0.0;

    payload["timestamp"] = doc["timestamp"] | (unsigned long)millis();

    String body;
    serializeJson(payload, body);
    dbg("POST body: " + body);

    HTTPClient http;
    http.begin(secureClient, API_URL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(8000);

    int code = http.POST(body);

    if (code > 0) {
      Serial.println("OK:" + String(code));
      dbg("HTTP code=" + String(code) + " body=" + http.getString());
    } else {
      Serial.println("ERR:HTTP_" + String(code));
      dbg("HTTP fail: " + http.errorToString(code));
    }

    http.end();
  }

  else {
    Serial.println("ERR:UNKNOWN_CMD");
  }
}