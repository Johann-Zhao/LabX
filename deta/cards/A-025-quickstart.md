---
material_id: A-025
card_type: quickstart
title: Raspberry Pi Pico 三分钟上手（MicroPython 点亮板载 LED）
points:
  - 先烧固件：按住 BOOTSEL 键插 USB，出现 RPI-RP2 盘，把官方 MicroPython .uf2 拖进去
  - 编程用 Thonny（官方推荐 IDE）：解释器选 MicroPython (Raspberry Pi Pico)，自动连串口
  - 第一个例子：板载 LED 在 GP25，`Pin(25, Pin.OUT)` 点亮，跑通后改外接 LED
source:
  - https://www.raspberrypi.com/documentation/microcontrollers/micropython.html
  - https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html
---

## 需要准备

| 东西 | 说明 |
|---|---|
| Raspberry Pi Pico | 本板（无 W 版） |
| Micro-USB 线 | 要能传数据（不是纯充电线） |
| Thonny IDE | https://thonny.org 下载安装（Windows/Mac/Linux 都有） |
| MicroPython 固件 | 官方 UF2 文件，https://www.raspberrypi.com/documentation/microcontrollers/micropython.html 页面上选 Pico 下载 |

## 第一步：刷 MicroPython 固件（只需一次，约 1 分钟）

1. 下载官方 **MicroPython UF2** 文件（选 "Pico" 那个，不是 Pico W）。
2. **按住板上 BOOTSEL 按钮不松**，同时把 Micro-USB 线插到 Pico（线另一端已连电脑）。保持按住 1~2 秒后松手。
3. 电脑上应出现一个叫 **RPI-RP2** 的 U 盘（正常只有 100 多 KB 容量）。
4. 把下载的 `.uf2` 文件**直接拖进 RPI-RP2 盘**。拷贝完成后 Pico 自动重启，RPI-RP2 盘消失——固件刷好了。
5. **没出现 RPI-RP2 盘** = BOOTSEL 没按好或线不能传数据，拔线重来。

## 第二步：Thonny 连接 Pico

1. 打开 Thonny：菜单 运行 → 配置解释器（或右下角 Python 版本处）。
2. 解释器选 **MicroPython (Raspberry Pi Pico)**，端口自动识别。
3. 左下角 Shell 窗口出现 `MicroPython v1.x.x on 202x-xx-xx; Raspberry Pi Pico with RP2040` 和 `>>>` 提示符 = 连接成功。
4. Shell 里试试直接敲 `print("hello")` 回车，立即输出——这就是 MicroPython 的交互式 REPL。

## 第三步：写第一个程序（板载 LED 闪烁）

在 Thonny 编辑区粘贴：

```python
from machine import Pin
import time

led = Pin(25, Pin.OUT)   # 板载 LED 接 GP25（Micro-USB 口左侧）

while True:
    led.value(1)         # 点亮
    time.sleep(0.5)
    led.value(0)         # 熄灭
    time.sleep(0.5)
```

点绿色**运行**按钮（或 F5）。板载 LED 应开始 0.5 秒间隔闪烁；Thonny 下方 Shell 无报错。点红色停止按钮可中断程序。

## 第四步（进阶）：外接 LED

| LED | 接到 Pico |
|---|---|
| 长脚（阳极） | 面包板连 GPIO15（物理 20 脚） |
| 短脚（阴极） | 串联 330Ω 电阻后接 GND（物理 18 脚等任意地） |

代码把 `Pin(25, ...)` 改成 `Pin(15, ...)`，重新运行，外接灯闪。

## 预期现象

板载 LED 稳定闪烁；把 `time.sleep(0.5)` 改成 `0.1` 再运行，闪烁明显变快——程序在真实硬件上跑通了。

## 失败第一查

Thonny 连不上 / Shell 没反应 → 先检查固件刷没刷（能不能进 RPI-RP2 模式），再检查 Thonny 解释器有没有选 MicroPython (Raspberry Pi Pico)。详见"常见错误"卡片。

## 下一步学什么

- 官方 MicroPython 入门文档（含 REPL、文件上传、GPIO）：https://www.raspberrypi.com/documentation/microcontrollers/micropython.html
- MicroPython RP2040 快速参考（ADC/PWM/I2C/UART 用法）：https://docs.micropython.org/en/latest/rp2/quickref.html
- 接传感器（DHT22 温湿度、超声波、OLED 屏）做小项目
- 官方书《Get started with MicroPython on Raspberry Pi Pico》配套示例
