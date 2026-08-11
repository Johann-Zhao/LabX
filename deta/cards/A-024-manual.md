---
material_id: A-024
card_type: manual
title: Raspberry Pi 4B（4GB）说明书要点
points:
  - 卡片电脑：BCM2711 四核 1.8GHz + 4GB 内存，跑完整 Linux，可当小型服务器/桌面机
  - 供电必须 5V/3A（官方 15W USB-C 电源），手机充电器供电不足会反复重启
  - GPIO 是 3.3V 逻辑，5V 信号直连会烧引脚；40 引脚排针兼容全部老款 Pi
source:
  - https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/
  - https://www.raspberrypi.com/documentation/computers/getting-started.html
---

## 关键参数（来自树莓派官方产品规格页）

| 参数 | 值 |
|---|---|
| 处理器 | Broadcom BCM2711，四核 Cortex-A72（ARM v8）64 位 @ 1.8GHz |
| 内存 | 4GB LPDDR4-3200（本板型号） |
| 无线 | 2.4GHz / 5.0GHz IEEE 802.11ac + 蓝牙 5.0 BLE |
| 有线网络 | 千兆以太网 |
| USB | 2 × USB 3.0（蓝色口）+ 2 × USB 2.0（黑色口） |
| 显示 | 2 × micro-HDMI（最高 4Kp60），2-lane MIPI DSI 屏幕接口 |
| 摄像头 | 2-lane MIPI CSI 相机接口 |
| 存储 | micro-SD 卡槽（系统装卡上），支持 USB 启动 |
| 供电 | 5V DC via USB-C（最低 3A）；也可经 GPIO 5V 引脚供电（最低 3A） |
| 音视频 | 4 极立体声 + 复合视频口；H.265(4Kp60)/H.264 硬解 |
| GPIO | 40 引脚标准排针（与历代树莓派完全兼容） |
| 工作温度 | 0 ~ 50℃ 环境温度 |
| 官方电源 | 15W USB-C 电源（5V / 3A），其他电源需满足 5V ≥3A（外设吃得少时 2.5A 优质电源也可） |

## 40 引脚 GPIO 速查（对着板子缺口朝左、排针朝右看，左下角是物理 1 脚）

| 类型 | 物理引脚 | 说明 |
|---|---|---|
| 3.3V | 1、17 | 低压电源，给 3.3V 外设供电 |
| 5V | 2、4 | 直接来自电源，给 5V 外设供电 |
| GND | 6、9、14、20、25、30、34、39 | 共 8 个地 |
| GPIO2/GPIO3 | 3、5 | I2C 总线 SDA/SCL（板载 1kΩ~1.8kΩ 上拉） |
| GPIO14/GPIO15 | 8、10 | UART TXD/RXD（串口控制台默认占用） |
| GPIO17 | 11 | 最常用的通用 IO（教程例子多用它） |
| GPIO23/GPIO24 | 16、18 | SPI CE0/CE1 片选 |
| 其余 GPIO | 见官方 pinout 图 | 引脚号用 BCM 编号，和物理编号不同，编程时以 BCM 编号为准 |

完整引脚图：https://pinout.xyz/ （交互式 40-pin 参考，含每个 GPIO 的复用功能）

## 适合 / 不适合

**适合**：跑完整 Linux（Raspberry Pi OS / Ubuntu）、Python 程序、OpenCV 视觉、小型 Web 服务器、NAS、桌面办公机、GPIO 控制（LED/按键/传感器）、机器人主控、深度学习推理（CPU 版）、P3 阶段的本地 LLM 实验。

**不适合**：实时性要求高的电机/闭环控制（无实时操作系统，建议配 Pico/STM32 做下位机）、超低功耗电池应用（4B 功耗比单片机高几个数量级）、需要 GPU 大规模训练（它只有视频硬解）。

## 官方资源

- 官方规格页（本文参数来源）：[Raspberry Pi 4 Model B 规格](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/)
- 官方入门文档：https://www.raspberrypi.com/documentation/computers/getting-started.html
- 官方 GPIO 文档（含引脚图）：https://www.raspberrypi.com/documentation/computers/raspberry-pi.html
- 官方系统烧录工具 Raspberry Pi Imager：https://www.raspberrypi.com/software/
