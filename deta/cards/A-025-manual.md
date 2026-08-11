---
material_id: A-025
card_type: manual
title: Raspberry Pi Pico（RP2040）说明书要点
points:
  - 双核 Cortex-M0+ 最高 133MHz + 264KB SRAM + 2MB Flash，跑 MicroPython 或 C/C++
  - 拖放式烧录：按住 BOOTSEL 插 USB，出现 RPI-RP2 盘，把 .uf2 拖进去即可，永不"变砖"
  - 全部 GPIO 为 3.3V 逻辑：ADC 只能测 0~3.3V，5V 信号直连会损坏芯片
source:
  - https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html
  - https://docs.micropython.org/en/latest/rp2/quickref.html
---

## 关键参数（来自树莓派官方 Pico 系列文档）

| 参数 | 值 |
|---|---|
| 主控 | RP2040：双核 Arm Cortex-M0+，最高 133MHz |
| 内存 | 264KB SRAM |
| 存储 | 板载 2MB Flash（程序和数据都存这里） |
| 语言 | MicroPython 或 C/C++（**不跑 Linux**，没有操作系统） |
| 编程方式 | USB 拖放 .uf2 文件（mass storage） |
| 数字 IO | 26 个多功能 GPIO |
| 模拟输入 | 3 个 12 位 ADC（GP26/27/28，量程 0~3.3V，另有 1 路板载温度传感器） |
| PWM | 16 路 PWM 通道 |
| 通信接口 | 2× SPI、2× I2C、2× UART、USB 1.1（Device 和 Host） |
| 特色 | 8 个 PIO 状态机（可软件模拟 SD 卡、VGA 等接口） |
| 逻辑电平 | **3.3V，GPIO 不耐受 5V** |
| 供电 | Micro-USB 5V 输入（VBUS 引脚），或 VSYS 引脚 2~5V |
| 板上 LED | 接 GP25（非无线版） |

## 引脚速览（40 引脚，两侧各 20 个；Micro-USB 口在上方）

| 类型 | 引脚 | 说明 |
|---|---|---|
| 电源 | 36 脚 `3V3(OUT)` | 板载 3.3V 稳压输出，给外设供电 |
| 电源 | 39 脚 `VSYS` | 系统输入 2~5V（绕过 USB 供电时用） |
| 电源 | 40 脚 `VBUS` | USB 的 5V，USB 供电时才有 |
| 控制 | 37 脚 `3V3_EN` | 拉低到 GND 可关机（断电） |
| 控制 | 35 脚 `ADC_VREF` | ADC 参考电压（默认 3.3V） |
| 控制 | 33 脚 `AGND` | 模拟地 |
| 控制 | 30 脚 `RUN` | 复位脚，拉低复位 |
| 板载 LED | 25 号 GPIO | Micro-USB 口左侧那颗灯 |
| I2C0 | GPIO4/5（物理 6/7） | 默认 SDA/SCL |
| UART0 | GPIO0/1（物理 1/2） | 默认 TX/RX |
| 调试 | 底部 3 个 SWD 焊盘 | SWDIO/GND/SWCLK，高级调试用 |

完整引脚图（官方）：https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html 内"Board layouts"章节。

## 常用 MicroPython 接口速查

```python
from machine import Pin, ADC, PWM, I2C, UART

Pin(25, Pin.OUT)      # 数字输出
Pin(2, Pin.IN, Pin.PULL_UP)  # 数字输入（带内部上拉）
ADC(Pin(26)).read_u16()      # 模拟读，0~65535 对应 0~3.3V
PWM(Pin(0), freq=1000, duty_u16=32768)  # 脉宽调制
I2C(0, scl=Pin(5), sda=Pin(4), freq=400_000)  # I2C
UART(0, 9600, tx=Pin(0), rx=Pin(1))  # 串口
```

## 适合 / 不适合

**适合**：MicroPython 快速原型、传感器采集（温度/光照/姿态）、小车/舵机控制、LED 灯带（NeoPixel）、与 Pi 4B 配合做下位机（实时控制交给 Pico）、课程设计中小型嵌入式项目。

**不适合**：跑操作系统/网页服务（它是微控制器不是电脑）、高密度计算、需要 WiFi/蓝牙的联网项目（本板是无 W 版，联网需外接模块或用 Pico W）、大容量存储。

## 官方资源

- 官方 Pico 系列文档（本文参数来源）：https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html
- 官方 MicroPython 安装说明（UF2 下载）：https://www.raspberrypi.com/documentation/microcontrollers/micropython.html
- MicroPython RP2040 快速参考：https://docs.micropython.org/en/latest/rp2/quickref.html
- 官方入门 PDF《Getting started with Raspberry Pi Pico》：https://datasheets.raspberrypi.com/pico/getting-started-with-pico.pdf
- 官方 IDE：Thonny（https://thonny.org），也可用 VS Code + MicroPico 插件
