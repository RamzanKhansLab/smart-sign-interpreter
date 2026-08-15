#include <SoftwareSerial.h>
#include <ArduinoJson.h>

SoftwareSerial esp(2, 3); // RX=D2, TX=D3

const char* SSID    = "sslg_wifi";
const char* PASS    = "12345678";
const char* API_URL = "https://smart-sign-interpreter.onrender.com/api/sensor-data";

bool wifiConnected    = false;
unsigned long lastAttempt = 0;
unsigned long lastPost    = 0;

#define MON(x) Serial.println(x)

void setup() {
  Serial.begin(9600);
  esp.begin(9600);
  MON("==== ATMEGA BOOT ====");
  waitForESP();
  MON("Setup done.");
}

void loop() {
  if (!wifiConnected && millis() - lastAttempt > 5000) {
    lastAttempt = millis();
    MON("\n[LOOP] Sending CONFIG...");
    wifiConnected = sendConfig();
  }

  if (wifiConnected && millis() - lastPost > 2000) {
    lastPost = millis();

    int s1 = analogRead(A0);
    int s2 = analogRead(A1);
    int s3 = analogRead(A2);
    int s4 = analogRead(A3);

    MON("[LOOP] s1=" + String(s1) + " s2=" + String(s2) +
        " s3=" + String(s3) + " s4=" + String(s4));

    sendPost(s1, s2, s3, s4);
  }

  readESP();
}

String readESPLine() {
  String line = esp.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return "";
  if (line.startsWith("DBG:")) {
    MON("[ESP-DBG] " + line.substring(4));
    return "";
  }
  MON("[ESP-RSP] " + line);
  return line;
}

void waitForESP() {
  MON("Waiting for ESP_READY...");
  unsigned long start = millis();
  while (millis() - start < 12000) {
    if (esp.available()) {
      String msg = readESPLine();
      if (msg == "ESP_READY") {
        MON("[WAIT] Got ESP_READY!");
        return;
      }
    }
  }
  MON("[WAIT] Timeout — check wiring.");
}

bool sendConfig() {
  StaticJsonDocument<256> doc;
  doc["cmd"]  = "CONFIG";
  doc["ssid"] = SSID;
  doc["pass"] = PASS;
  doc["url"]  = API_URL;

  String out;
  serializeJson(doc, out);
  MON("[CONFIG] " + out);
  esp.println(out);

  unsigned long start = millis();
  while (millis() - start < 15000) {
    if (esp.available()) {
      String resp = readESPLine();
      if (resp == "") continue;
      if (resp.startsWith("WIFI_OK"))       { MON("[CONFIG] OK: " + resp); return true; }
      if (resp.startsWith("ERR:WIFI_FAIL")) { MON("[CONFIG] WiFi failed.");  return false; }
      if (resp.startsWith("ERR:"))          { MON("[CONFIG] Err: " + resp);  return false; }
    }
  }
  MON("[CONFIG] Timeout.");
  return false;
}

void sendPost(int s1, int s2, int s3, int s4) {
  StaticJsonDocument<512> doc;
  doc["cmd"] = "POST";

  doc["s1"] = s1;
  doc["s2"] = s2;
  doc["s3"] = s3;
  doc["s4"] = s4;
  doc["s5"] = 0;    // fixed at 0 — backend still expects s5 key

  doc["ax"] = 0.0;
  doc["ay"] = 0.0;
  doc["az"] = 0.0;
  doc["gx"] = 0.0;
  doc["gy"] = 0.0;
  doc["gz"] = 0.0;

  doc["timestamp"] = millis();

  String out;
  serializeJson(doc, out);
  MON("[POST] " + out);
  esp.println(out);

  unsigned long start = millis();
  while (millis() - start < 10000) {
    if (esp.available()) {
      String resp = readESPLine();
      if (resp == "") continue;
      if (resp.startsWith("OK:")) {
        MON("[POST] Success: " + resp); return;
      }
      if (resp.startsWith("ERR:NOT_CONFIGURED")) {
        MON("[POST] ESP lost config — reconnecting.");
        wifiConnected = false; return;
      }
      if (resp.startsWith("ERR:")) {
        MON("[POST] Error: " + resp); return;
      }
    }
  }
  MON("[POST] Timeout — WiFi dropped.");
  wifiConnected = false;
}

void readESP() {
  while (esp.available()) readESPLine();
}