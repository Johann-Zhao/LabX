---
material_id: A-017
card_type: manual
title: Arduino Uno 说明书要点
points:
  - 5V 逻辑电平，14 个数字引脚（D0-D13）+ 6 路模拟输入（A0-A5，10 位 ADC）
  - USB 口下载程序并供电（5V）；DC 电源座可接 7-12V 外部电源
  - 单个 I/O 引脚输出电流别超过 20mA，LED 必须串 220Ω 左右限流电阻
---

## 关键参数

| 参数 | 值 |
|---|---|
| 主控 | ATmega328P，16MHz |
| 供电 | USB 5V，或 DC 座 / Vin 接 7-12V |
| 逻辑电平 | 5V |
| 数字引脚 | D0-D13 共 14 个，其中 D3/D5/D6/D9/D10/D11 支持 PWM |
| 模拟输入 | A0-A5 共 6 路，10 位 ADC，读数 0-1023 |
| 板载 LED | 接 D13，代码里叫 LED_BUILTIN |
| 存储 | Flash 32KB（程序）、SRAM 2KB、EEPROM 1KB |
| I/O 电流 | 每脚建议 ≤ 20mA，极限 40mA |

## 引脚与接口

1. **USB 口** —— 下载程序 + 串口监视器 + 供电。R3 板载 ATmega16U2 转串口芯片，正版免驱；克隆板多为 CH340，需装 CH340 驱动。
2. **DC 电源座 / Vin** —— 接 7-12V 外部电源。带电机、舵机等大电流设备时走这里，别全指望 USB。
3. **电源引脚** —— 5V（给 5V 外设供电）、3.3V（给低功耗 3.3V 设备）、GND、Vin。
4. **D0/D1** —— 串口 RX/TX，下载程序和 Serial 打印要用，别接其他设备。
5. **A0-A5** —— 模拟输入，只能接 0-5V 电压信号。

## 常用库

Arduino IDE 库管理器搜索名字直接安装：`Servo.h`（舵机）、`DHT sensor library`（温湿度）、`LiquidCrystal`（1602 液晶）等。开发板型号选 **Arduino Uno**。
