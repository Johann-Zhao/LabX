---
material_id: A-017
card_type: manual
title: Arduino Uno R3 说明书要点
points:
  - ATmega328P 主控 16MHz，5V 逻辑电平：14 个数字脚（其中 3/5/6/9/10/11 共 6 路 PWM）+ 6 路模拟输入（A0-A5，10 位 ADC，默认量程 0-5V）
  - 供电三选一：USB 5V、DC 电源座 / Vin 引脚接 7-12V（官方推荐，极限 6-20V，超 12V 稳压器会过热）
  - 单个 I/O 引脚官方推荐电流 20mA（极限 40mA），3.3V 引脚最大 50mA；LED 必须串限流电阻
source:
  - https://docs.arduino.cc/hardware/uno-rev3/
  - https://store.arduino.cc/products/arduino-uno-rev3
---

## 关键参数（来自 Arduino 官方文档）

| 参数 | 值 |
|---|---|
| 主控 | ATmega328P（DIP 封装，可更换芯片），16MHz 陶瓷谐振器 |
| 逻辑电平 | 5V |
| 输入电压（推荐） | 7-12V（DC 电源座或 Vin 引脚） |
| 输入电压（极限） | 6-20V；低于 7V 时 5V 引脚可能不足 5V，高于 12V 稳压器可能过热损坏 |
| 数字引脚 | D0-D13 共 14 个，均可作输入/输出 |
| PWM 引脚 | D3、D5、D6、D9、D10、D11（analogWrite 输出 8 位 PWM） |
| 模拟输入 | A0-A5 共 6 路，10 位分辨率（0-1023），默认量程 0-5V，可用 AREF 改上限 |
| 板载 LED | 接 D13（代码里叫 LED_BUILTIN） |
| 存储 | Flash 32KB（其中 0.5KB 被 bootloader 占用）、SRAM 2KB、EEPROM 1KB |
| I/O 电流 | 每脚推荐 ≤ 20mA，任何引脚不可超过 40mA（超过会永久损坏） |
| 内部上拉 | 20-50kΩ，默认断开，pinMode 里可启用 |
| 3.3V 引脚 | 最大输出电流 50mA |
| USB 保护 | 板载自恢复保险丝，USB 口超过 500mA 自动断开 |
| 串口芯片 | ATmega16U2 转串口，官方板免装驱动（Windows 的 .inf 已含在 IDE 内） |

## 引脚与接口

| 引脚/接口 | 功能说明 |
|---|---|
| D0 / D1 | 串口 RX / TX，接 ATmega16U2 转串口芯片。下载程序和 Serial 打印要用，别接其他设备 |
| D2 / D3 | 外部中断脚（attachInterrupt），低电平/上升沿/下降沿/电平变化均可触发 |
| D10(SS) / D11(MOSI) / D12(MISO) / D13(SCK) | SPI 通信 |
| A4 / A5 | TWI(I2C) 的 SDA / SCL，用 Wire 库 |
| A0-A5 | 模拟输入，只接 0-5V 电压信号；超过会烧 ADC |
| AREF | 模拟输入参考电压，配合 analogReference() 用 |
| Vin / 5V / 3V3 / GND | Vin：外部电源输入（7-12V）；5V：稳压输出；3V3：最大 50mA；GND：地 |
| IOREF | 输出主控工作电压，让 shield 自动适配 5V/3.3V |
| DC 电源座 | 2.1mm 内正外负，接 7-12V AC-DC 适配器或 9V 电池 |
| USB 口 | 下载程序 + 串口监视器 + 供电 |
| ICSP 排针 | 绕过 bootloader 直接烧写芯片（Arduino ISP 方式） |
| RESET | 低电平复位；软件可通过 DTR 线自动复位（上传时自动触发） |

## 这块板适合 / 不适合做什么

- **适合**：入门第一块板；传感器数据采集、LED/数码管/1602 液晶、舵机、继电器控制；课堂实验与课程设计。
- **勉强能行**：小型电机驱动（必须加 L298N/ULN2003 驱动模块并单独供电）、简单小车。
- **不适合**：WiFi/蓝牙联网（Uno 没有无线，需外挂模块）；大量数据处理（2KB SRAM 很小）；多任务实时系统；视频/图像处理。

## 官方资源

- 官方文档页：https://docs.arduino.cc/hardware/uno-rev3/
- 官方规格页：https://store.arduino.cc/products/arduino-uno-rev3
- IDE 下载：https://www.arduino.cc/en/software （下载 Arduino IDE 2.x 的 Windows 版）
