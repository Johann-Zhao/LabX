---
material_id: A-023
card_type: quickstart
title: ESP32-S3 DevKitC-1 三分钟上手
points:
  - 装软件：Arduino IDE 首选项里加 espressif 板包网址，开发板管理器搜 esp32 安装（首次较大，需联网）
  - 接线：不用接任何线，USB 数据线插板边 Micro-USB 口即可；板载 RGB 灯在 GPIO38（v1.1）
  - 跑通：选 ESP32S3 Dev Module 上传 NeoPixel 点灯代码，RGB 灯红闪即成功；失败就按住 BOOT 再传
source:
  - https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html
  - https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf
---

## 第零步：装 Arduino 板包（只需一次）

1. 安装 **Arduino IDE 2.x**（官网 https://www.arduino.cc/en/software 下载 Windows 版）；
2. 文件 → 首选项 → "附加开发板管理器网址"填入：

   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`

3. 工具 → 开发板 → 开发板管理器 → 搜索 `esp32` → 安装 **esp32 by Espressif Systems**（几百 MB，耐心等几分钟，**中途别断网**）；
4. 工具 → 开发板 → 搜索选择 **ESP32S3 Dev Module**。

## 第一步：接线（其实没有线）

官方要求的硬件只有三样：DevKitC-1 板 + **USB 2.0 数据线** + 电脑。**USB 线必须能传数据**——官方文档明确警告：很多线只充电不传数据，无法下载程序。

插**板边的 USB-to-UART 口**（Micro-USB 那个，**不是**另一个 USB 口）。工具 → 端口 → 选中新出现的 COM 口。

## 第二步：装库 + 跑通第一个程序

板载 RGB 灯是 WS2812 可寻址灯，普通 Blink 示例驱动不了它。先装库：左侧栏库管理器 → 搜索 **Adafruit NeoPixel** → 安装。然后把下面代码整个复制进 IDE：

```cpp
#include <Adafruit_NeoPixel.h>

#define PIN 38        // v1.1 版板载 RGB 灯；如果你的板是早期 v1.0 版，改成 48
#define NUMPIXELS 1   // 板载只有 1 颗灯

Adafruit_NeoPixel pixels(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

void setup() {
  pixels.begin();
  Serial.begin(115200);
  Serial.println("ESP32-S3 启动成功");
}

void loop() {
  pixels.setPixelColor(0, pixels.Color(255, 0, 0));  // 红色（R,G,B 取值 0-255）
  pixels.show();                                     // 真正点亮
  delay(500);
  pixels.setPixelColor(0, pixels.Color(0, 0, 0));    // 熄灭
  pixels.show();
  delay(500);
}
```

点 **→（上传）**。看到 "Connecting..." 时板子会自动进下载模式；若一直卡在 Connecting，**按住板上的 BOOT 键不松，点上传，看到 Connecting... 时松手**。

## 上传成功后预期看到

- 板载 **RGB 灯红色闪烁**（每秒一次）；
- 打开串口监视器（右上角放大镜），波特率选 **115200**（不是 9600），看到一行 `ESP32-S3 启动成功`；
- 想改颜色：把 `pixels.Color(255, 0, 0)` 改成 `pixels.Color(0, 255, 0)` 就是绿色——改代码→上传→看效果，流程闭环。

## 看不到灯闪，第一步查什么？

1. 上传是否成功？失败 → 按"常见错误"卡片第 1 条：先试 BOOT 键强制下载、换数据线、确认板型；
2. 上传成功但灯不闪 → **确认你的板是 v1.1 还是 v1.0**：RGB 灯引脚 v1.1=38、v1.0=48，把代码里的 `#define PIN` 改成另一个试试；
3. 灯没反应但串口有输出 → 灯是好的，问题只在那一行 PIN。

## 下一步学什么（全链路路线图）

1. **点亮板载 LED**（已完成）→ 换成点亮外接 WS2812 灯带（同一段代码，改引脚即可）；
2. **连 WiFi**：官方示例 文件→示例→WiFi→WiFiScan，扫描周围热点；
3. **读传感器 + 上云**：DHT22 温湿度（见 S-003 卡片）→ MQTT 推到物联网平台；
4. **完成项目**：手机网页控制传感器数据+LED 状态，一个完整的 IoT 作品就闭环了。
