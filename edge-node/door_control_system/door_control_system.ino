#include <WiFiNINA.h>
#include "config.h"
#include "pins.h"

// กำหนดพิน (ใช้ขา 2 หรือขา 13 ที่เป็นไฟบนบอร์ดก็ได้ครับ)
const int ledPin = 2;
const int ledPin3 = 3;

WiFiServer server(80);

void setup() {
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
  pinMode(ledPin3, OUTPUT);
  digitalWrite(ledPin, LOW); // เริ่มต้นให้ไฟดับ
  digitalWrite(ledPin3, HIGH);

  Serial.print("กำลังเชื่อมต่อ WiFi: ");
  Serial.println(ssid);
  
  while (WiFi.begin(ssid, password) != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n✅ WiFi เชื่อมต่อแล้ว!");
  Serial.print("📍 IP Address: ");
  Serial.println(WiFi.localIP());

  server.begin();
}

void loop() {
  WiFiClient client = server.available();
  if (client) {
    String request = client.readStringUntil('\r');
    client.flush();

    // --- ตรวจสอบคำสั่งเพื่อเปิดไฟ ---
    if (request.indexOf("/unlock") != -1) {
      Serial.println("💡 สั่งเปิดไฟ (LED ON)");
      digitalWrite(ledPin, HIGH); // ไฟติด
      sendResponse(client, "ON");
    } 
    
    // --- ตรวจสอบคำสั่งเพื่อปิดไฟ ---
    else if (request.indexOf("/lock") != -1) {
      Serial.println("🌑 สั่งปิดไฟ (LED OFF)");
      digitalWrite(ledPin, LOW);  // ไฟดับ
      sendResponse(client, "OFF");
    }
    
    else if (request.indexOf("/ping") != -1) {
      sendResponse(client, "PONG");
    }
    
    delay(10);
    client.stop();
  }
}

void sendResponse(WiFiClient& client, String msg) {
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: application/json");
  client.println("Connection: close");
  client.println();
  client.print("{\"led_status\":\"");
  client.print(msg);
  client.println("\"}");
}