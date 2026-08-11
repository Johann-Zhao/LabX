---
material_id: A-023
card_type: quickstart
title: ESP32-S3 三分钟上手
points:
  - 先装板包：首选项加 espressif 板包网址，开发板管理器搜 esp32 安装
  - 接线：不用接任何线，USB 连电脑即可，板载 LED 在 GPIO48
  - 跑示例：文件→示例→01.Basics→Blink，选 ESP32S3 Dev Module 上传，灯闪即成功
---

## 第一步：装板包（只需一次）

1. 文件 → 首选项 → "附加开发板管理器网址"填入：`https://espressif.github.io/arduino-esp32/package_esp32_index.json`
2. 工具 → 开发板 → 开发板管理器 → 搜索 `esp32` → 安装 Espressif 官方包（约几百 MB，等几分钟）
3. 工具 → 开发板 → 选 **ESP32S3 Dev Module**

## 第二步：接线

不用接任何线。USB 线连电脑（要能传数据的线），工具 → 端口 → 选中出现的 COM 口。

## 第三步：跑通示例

菜单：文件 → 示例 → 01.Basics → Blink，直接点上传。上传完成后板载 RGB LED 开始闪烁，即成功。

打开串口监视器，波特率选 **115200**（不是 9600）。

## 想自己改一段

```cpp
void setup() {
  pinMode(48, OUTPUT);      // 板载 RGB LED 在 GPIO48
  Serial.begin(115200);
}

void loop() {
  digitalWrite(48, HIGH);
  Serial.println("on");
  delay(500);
  digitalWrite(48, LOW);
  Serial.println("off");
  delay(500);
}
```

## 上传一直失败？

按住板上的 BOOT 键不松，再点上传，看到 "Connecting..." 时松手。详见"常见错误"卡片。
