---
material_id: A-018
card_type: manual
title: STM32F103C8T6 最小系统板说明书要点
points:
  - 72MHz Cortex-M3 内核，64KB Flash + 20KB SRAM，供电 2.0-3.6V（典型 3.3V），LQFP48 封装共 37 个 I/O（几乎全部 5V 容忍）
  - 最小系统板不带 USB 下载口：烧程序要么用 ST-Link 走 SWD 四线（BOOT0=0 直接下载），要么 USB-TTL 串口下载（BOOT0=1、BOOT1=0）
  - 外设阵容（电赛主力）：2×12 位 ADC、3×16 位定时器 + 1 路 PWM 定时器、3×USART、2×I2C、2×SPI、USB、CAN
source:
  - https://www.st.com/resource/en/datasheet/stm32f103c8.pdf
  - https://cloud.tencent.com/developer/article/2345037
---

## 关键参数（来自 ST 官方数据手册 DS5319）

| 参数 | 值 |
|---|---|
| 内核 | Arm Cortex-M3 32 位，最高 72MHz，1.25 DMIPS/MHz |
| Flash | 64KB（C8T6 为 64KB 型号；同系列 xB 为 128KB） |
| SRAM | 20KB |
| 供电 | 2.0-3.6V（典型 3.3V）；I/O 几乎全部 5V 容忍 |
| 封装 | LQFP48，37 个 I/O（26/37/51/80 对应 36/48/64/100 脚封装） |
| ADC | 2 个 12 位 ADC（最多 16 通道，1μs 转换，量程 0-3.6V） |
| 定时器 | 3 个 16 位通用定时器（带 PWM/编码器接口）+ 1 个 16 位电机控制 PWM 定时器（带死区与急停）+ 2 个看门狗 + SysTick |
| 通信 | 2×I2C、3×USART（支持 LIN/红外）、2×SPI（18Mbit/s）、USB 2.0 全速、CAN 2.0B |
| 调试 | SWD + JTAG 双接口 |
| 时钟 | 4-16MHz 外部晶振（最小系统板一般配 8MHz）+ 内部 8MHz RC + 32.768kHz RTC 晶振 |
| 工作温度 | -40~85℃（C8T6 尾缀 6） |

## 最小系统板的板载资源

"最小系统板"= 芯片 + 晶振 + 稳压 + 复位 + 排针，**没有 USB 下载口、没有仿真器**，全靠外部工具烧程序：

| 接口/元件 | 说明 |
|---|---|
| BOOT0 / BOOT1 跳线（或拨码） | 决定启动来源，见下表，这是本板最常出错的部位 |
| SWD 排针（SWDIO/SWCLK/GND/3V3） | 接 ST-Link 烧录与调试 |
| USART1 引脚 PA9(TX) / PA10(RX) | 串口通信，也是串口下载程序的入口 |
| 3V3 / GND / 5V 排针 | 芯片供电 3.3V；多数最小系统板带 5V→3.3V 稳压（具体看板子丝印，供电别超过官方 3.6V 上限） |
| NRST 复位键 | 低电平复位；**每次切换 BOOT 跳线后按一下它才生效** |
| 板载 LED | 接的引脚各板不同，先看板子丝印，别照抄别人的代码 |

## BOOT 启动模式（官方数据手册 Boot modes 章节）

| BOOT0 | BOOT1 | 启动来源 | 什么时候用 |
|---|---|---|---|
| 0 | 任意(X) | 主闪存（你的程序） | **正常运行**、SWD/ST-Link 下载 |
| 1 | 0 | 系统存储器（出厂 bootloader） | **串口下载**（FlyMcu 等工具） |
| 1 | 1 | SRAM | 调试用，一般不用 |

## 这块板适合 / 不适合做什么

- **适合**：电赛主力——电机/舵机控制（高级定时器 PWM）、编码器测速、传感器采集（ADC）、CAN 总线、串口通信、低成本工业控制。资料极多（正点原子/野火/ST 官方），是学嵌入式最主流的选择。
- **不适合**：WiFi/蓝牙联网（芯片无无线功能，需外挂模块）；需要大内存/大存储的应用（64KB Flash / 20KB SRAM 有限）；追求快速原型验证（Arduino 上手更快）；图形界面。

## 官方与教程资源

- ST 官方产品页：https://www.st.com/en/microcontrollers-microprocessors/stm32f103c8.html
- 官方数据手册（DS5319 PDF）：https://www.st.com/resource/en/datasheet/stm32f103c8.pdf
- 野火 STM32F103C8T6 核心板资料页（含 Keil 工程配置要点）：https://github.com/Embedfire/products/wiki/野火STM32F103C8T6核心板
- 烧录方法图文教程（SWD/串口两种）：https://cloud.tencent.com/developer/article/2345037
