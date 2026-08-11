---
material_id: A-018
card_type: common_errors
title: STM32F103C8T6 最容易踩的四个坑
points:
  - Keil 报 No ST-LINK detected / Cannot access target：先查驱动和 SWD 四线（SWDIO/SWCLK 别接反），再查供电 3.3V
  - 下载成功但程序不跑：BOOT0 跳线还在 1（从系统存储器启动，不会跑你的程序），置 0 后按 RESET
  - 串口下载失败：TXD/RXD 要交叉接（TXD→PA10、RXD→PA9），共地，BOOT0 必须置 1
source:
  - https://www.st.com/resource/en/datasheet/stm32f103c8.pdf
  - https://cloud.tencent.com/developer/article/2345037
---

## 详细说明（每个坑按 现象 → 原因 → 解决 → 怎么验证 展开）

### 1. 下载报错：No ST-LINK detected / Cannot access target

- **现象**：Keil 点下载立即报 `No ST-LINK detected!` 或 `Cannot access target device`，Settings 里 Device 是空/问号。
- **原因**：四选一——①ST-Link 驱动没装；②SWD 四线没接对（**SWDIO/SWCLK 接反**最常见，GND 没共地也会这样）；③板子没供电或 3.3V 没接；④BOOT0 跳线接错导致芯片不在可烧写状态（SWD 下载要求 BOOT0=0）。
- **解决**：按顺序查——重装 ST-Link 驱动 → 核对四线：SWDIO 对 SWDIO、SWCLK 对 SWCLK、GND 对 GND、3V3 对 3V3 → 确认板子 3.3V 供电正常（万用表量 3V3 排针）→ BOOT0 置 0。
- **怎么验证修好了**：Keil → Options for Target → Debug → Settings 里能读出目标芯片型号（如 Cortex-M3 / STM32F103C8），点下载走到 `Flash Load ... OK`。

### 2. 下载成功但程序不运行 / 板子"没反应"

- **现象**：Keil 提示下载完成（Flash Load OK），但 LED 不亮、程序完全不跑。
- **原因**：最典型是 **BOOT0 跳线还置在 1**——芯片从系统存储器（bootloader）启动，不执行你烧进主闪存（0x08000000）的程序；另一种是下载完没按 RESET，程序还在运行旧内容/没启动。
- **解决**：把 **BOOT0 跳线置 0**，按一下 **RESET 键**，程序才从主闪存启动。
- **怎么验证修好了**：BOOT0=0 + 复位后 LED 按代码节奏闪烁；把 Delay 改大改小重新下载，闪速跟着变，说明跑的确实是新程序。

### 3. 串口下载失败：卡在等待同步 / 一直超时

- **现象**：用 FlyMcu 等工具串口下载，进度一直停在"等待芯片同步/握手"，或报超时；偶尔第一行提示"芯片擦除成功"后就没动静。
- **原因**：四选一——①**TXD/RXD 没交叉**：USB-TTL 的 TXD 要接板子的 **PA10（RX）**，RXD 接 **PA9（TX）**，同向直连（TXD 对 TXD）永远通不了；②USB-TTL 与板子**没共地**；③**BOOT0 没置 1**（芯片没进 bootloader，握手不成功）；④接线或电源不稳定。
- **解决**：核对交叉接线 TXD→PA10、RXD→PA9、GND→GND；BOOT0 置 1、BOOT1 置 0；点"开始编程"后按一下板子 RESET 让芯片进系统存储器。
- **怎么验证修好了**：下载进度走到 100%，提示成功；然后把 BOOT0 跳回 0、按 RESET，程序正常运行。

### 4. 板子没供电 / 上电就烫 / 芯片冒烟

- **现象**：插上电源没反应、电压不稳程序乱跑，或者板子某个元件烫手、芯片冒烟。
- **原因**：**STM32F103 官方供电范围只有 2.0-3.6V**——把 5V 直接怼到 3V3 排针、或插反电源正负极，都会瞬间烧毁芯片；从 5V 引脚供电时，也要先确认板子稳压电路支持（多数最小系统板是 5V 进稳压出 3.3V，但别想当然）。
- **解决**：先看板子丝印：3V3 排针只接 3.3V；用 5V 供电就走标注 5V 的引脚（经板载稳压）；接任何电源前用万用表确认电压值；上下电先断电再操作。
- **怎么验证修好了**：万用表量 3V3 排针稳定在 3.3V（允许 ±5%），芯片常温不烫，程序正常下载运行；更换已烧毁的板子/芯片（注意先排除过压原因再换）。
