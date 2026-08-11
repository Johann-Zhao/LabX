---
material_id: A-023
card_type: manual
title: ESP32-S3 开发板说明书要点
points:
  - 双核 240MHz + WiFi + 蓝牙，3.3V 逻辑电平，Arduino 里引脚号就是 GPIO 编号
  - USB 口下载程序并供电；板载 RGB LED 接 GPIO48；按住 BOOT 再按 RESET 进下载模式
  - 模拟输入用 ADC1（GPIO1-GPIO10，12 位，读数 0-4095），测量范围 0-3.3V
---

## 关键参数

| 参数 | 值 |
|---|---|
| 主控 | ESP32-S3，双核 Xtensa LX7，240MHz |
| 无线 | WiFi 802.11 b/g/n + 蓝牙 5（BLE） |
| 供电 | USB 5V（板载 3.3V 稳压器） |
| 逻辑电平 | 3.3V（大部分 GPIO 5V 容忍，但按 3.3V 设计最稳） |
| 模拟输入 | ADC1：GPIO1-GPIO10，12 位，读数 0-4095，范围 0-3.3V |
| 板载 LED | RGB 灯接 GPIO48（WS2812 型，需 NeoPixel 库驱动） |
| 存储 | 板载 Flash，容量随购买版本而定，程序空间足够用 |

## 接口速览

1. **USB 口（板边 UART 口）** —— 下载程序 + 串口监视器 + 供电。
2. **另一个 USB 口** —— 原生 USB-OTG，一般用不到，别插错。
3. **BOOT 键** —— 按住 BOOT 再按一下 RESET（EN）进入下载模式，上传卡住时靠它。
4. **EN 键** —— 复位。
5. **电源引脚** —— 5V（来自 USB）、3V3（板载稳压输出，给外设供电注意总电流有限）、GND。

## 环境配置

Arduino IDE 首次使用要先加装 esp32 板包：文件 → 首选项 → "附加开发板管理器网址"填入：

`https://espressif.github.io/arduino-esp32/package_esp32_index.json`

然后工具 → 开发板管理器 → 搜索 `esp32` 安装。开发板型号选 **ESP32S3 Dev Module**，串口监视器波特率用 **115200**。

## 启动配置脚（strapping pin）

GPIO0、GPIO3、GPIO45、GPIO46 是启动配置脚，上电瞬间会输出特殊电平，别接 LED 等负载（详见常见错误卡片）。
