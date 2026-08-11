---
material_id: A-023
card_type: manual
title: ESP32-S3 DevKitC-1 说明书要点
points:
  - 双核 Xtensa LX7 240MHz + WiFi 802.11b/g/n + 蓝牙 5(LE)，3.3V 逻辑电平，共 45 个 GPIO
  - 用板边 USB-to-UART 口（Micro-USB）供电+下载+串口；按住 BOOT 再按 RESET 进下载模式
  - 板载 RGB 灯是 WS2812 可寻址灯，v1.1 版接 GPIO38（初版 v1.0 是 GPIO48），要用 NeoPixel 库驱动
source:
  - https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html
  - https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf
---

## 关键参数（来自乐鑫官方用户指南与数据手册）

| 参数 | 值 |
|---|---|
| 主控 | ESP32-S3，双核 Xtensa LX7，最高 240MHz，带单精度 FPU |
| 无线 | WiFi 802.11 b/g/n（2.4GHz，20/40MHz 带宽，最高 150Mbps）+ 蓝牙 5 LE |
| 逻辑电平 | 3.3V（大部分引脚不可直接接 5V 信号） |
| GPIO | 45 个（芯片级），其中 4 个为启动配置脚（strapping） |
| 模拟输入 | 2 个 12 位 SAR ADC，最多 20 通道，量程 0-3.3V |
| 触摸 | 14 个触摸感应 IO |
| 内存 | SRAM 512KB、ROM 384KB、RTC SRAM 16KB；程序存板载 Flash（按版本 N8=8MB 等） |
| 串口 | 3 个 UART、2 个 I2C、2 个 I2S、2 个通用 SPI + 2 个 Flash/PSRAM SPI |
| USB | USB 2.0 全速 OTG + USB Serial/JTAG 控制器 |
| 低功耗 | Deep-sleep 最低约 7μA |
| 板载稳压 | 5V → 3.3V LDO |
| 板载灯 | RGB 可寻址 LED（WS2812 型）：v1.1 接 GPIO38，初版 v1.0 接 GPIO48；另有 3.3V 电源指示灯 |

## 板载接口速览

| 接口 | 功能说明 |
|---|---|
| USB-to-UART 口（板边，Micro-USB） | **默认使用**：供电 + 下载程序 + 串口监视器，经板载 USB-to-UART 桥（最高 3Mbps） |
| USB 口（ESP32-S3 USB OTG） | USB 1.1 全速 OTG / USB Serial-JTAG，一般项目用不到，别插错 |
| BOOT 键 | 按住 BOOT 再按一下 RESET → 进入固件下载模式（上传卡住时靠它） |
| RESET 键 | 复位 |
| 5V 引脚 | 来自 USB 的 5V（可从这里给外设供电，注意总电流） |
| 3V3 引脚 | 板载 LDO 输出的 3.3V，给 3.3V 外设供电 |
| G（GND） | 地。官方供电方式三选一：USB 口（推荐）、5V+G、3V3+G |

## 引脚使用注意事项（官方数据手册/用户指南）

1. **启动配置脚（strapping pins）**：GPIO0、GPIO3、GPIO45、GPIO46 决定芯片启动方式，上电瞬间会输出特殊电平。**别把 LED、继电器、三极管等负载接在这 4 个脚上**。
2. **GPIO35/36/37**：使用 Octal SPI Flash/PSRAM 模块（如 N8R8、WROOM-2 版）时被内部占用，不可外接使用。
3. **GPIO19/20**：USB 引脚，上电瞬间有约 60μs 的电平毛刺，且默认用作 USB；当普通 IO 用时要先在配置里关掉 USB。
4. **ADC 量程 0-3.3V**：接 5V 会烧 ADC；5V 传感器信号需分压或电平转换。

## 这块板适合 / 不适合做什么

- **适合**：WiFi 联网项目（环境监测上云、网页控制、MQTT）、蓝牙 BLE 应用、需要触摸按键、音频/摄像头采集（LCD/DVP 接口）、边缘 AI 推理。
- **不适合**：纯简单教学点灯（用 Uno 更省事）；需要 5V 逻辑电平直接驱动的设备（需转换）；极低功耗电池项目要做深度配置（需吃透 Deep-sleep + RTC 外设）。

## 官方资源

- DevKitC-1 用户指南（含原理图、尺寸图链接）：https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html
- ESP32-S3 数据手册：https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf
- Arduino 环境板包索引：https://espressif.github.io/arduino-esp32/package_esp32_index.json
