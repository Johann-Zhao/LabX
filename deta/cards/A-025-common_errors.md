---
material_id: A-025
card_type: common_errors
title: Raspberry Pi Pico 最容易踩的四个坑
points:
  - 插上电脑没有 RPI-RP2 盘 = 没按住 BOOTSEL 就插线 / 线只能充电，拔线按住重插
  - Pico 是 3.3V 逻辑：ADC 只能测 0~3.3V，5V 信号直连会永久损坏芯片
  - Thonny 连不上先查三件事：解释器选没选 MicroPython (Raspberry Pi Pico)、端口是否被占用、固件刷没刷
  - BOOTSEL 模式烧在芯片 ROM 里，怎么折腾都"变不了砖"，放心重刷
source:
  - https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html
  - https://docs.micropython.org/en/latest/rp2/quickref.html
---

## 详细说明

### 1. 插上电脑没有反应 / 没有 RPI-RP2 盘
**现象**：用 USB 线连上 Pico，电脑什么都不弹，资源管理器里没有 RPI-RP2 盘，设备管理器也没有新设备。
**原因**：最常见三个——(a) **没按 BOOTSEL**：普通模式下 Pico 上电直接跑 Flash 里的程序，不会挂载成 U 盘（除非固件里主动开了 USB 串口）；(b) 线只能充电不能传数据；(c) 刷好固件后 BOOTSEL 才是唯一入口，而进入 BOOTSEL 必须**先按住按键再插线**。
**解决**：拔掉 USB 线 → **按住 BOOTSEL 不松** → 插线（线先插电脑再插 Pico）→ 保持 1~2 秒松手。换一根能传数据的线再试，换 USB 口再试。Windows 下可以打开设备管理器观察插线瞬间是否出现新设备（USB 大容量存储设备）。
**怎么验证修好了**：资源管理器出现 **RPI-RP2** 盘（容量 128KB 左右），能正常打开。

### 2. 3.3V 逻辑：接 5V 外设烧芯片 / ADC 读数满量程
**现象**：接了 5V 供电的传感器/舵机信号线后，GPIO 引脚失灵或读数永远 65535；用 ADC 测超过 3.3V 的电压；接 5V 继电器模块后板子异常。
**原因**：RP2040 所有 GPIO 都是 **3.3V 逻辑，官方明确不耐受 5V**。ADC 量程 0~3.3V，超压会把模拟输入损坏。5V 设备大多兼容 3.3V 输入但输出 5V 高电平，那个 5V 高电平直接怼 GPIO 就烧了。
**解决**：传感器/模块优先选 3.3V 版本；5V 输出的模块必须加**电平转换器**（双向电平转换模块很便宜）或电阻分压；ADC 输入串电阻限流并按分压降到 3.3V 以内；给 5V 外设供电走 VSYS/VBUS 或独立电源，信号线别接 5V。拿不准先查模块手册的输出电平。
**怎么验证修好了**：用万用表量信号线高电平为 3.3V 而非 5V；ADC 读数和实际电压对得上（如 1.65V 输入读到约 32767）；原本损坏的引脚不会恢复，换一个 GPIO 再测。

### 3. Thonny 连不上：一直 Connecting / Shell 没有 >>> 
**现象**：Thonny 打开后提示连接失败，或 Shell 一直卡在 "Connecting..."；点运行报"设备未找到"。
**原因**：按频率排序——(a) Thonny 解释器没选对（默认是"本地 Python 3"，连接的是电脑自己的 Python 而不是 Pico）；(b) 板子固件没刷（出厂没有 MicroPython，连上也没 REPL）；(c) 串口被别的程序占用（比如终端里开着 minicom/另一个 Thonny 窗口）；(d) 线只充电。
**解决**：(a) 运行 → 配置解释器 → 选 **MicroPython (Raspberry Pi Pico)**；(b) 按 BOOTSEL 重刷一遍官方 UF2 固件；(c) 关掉所有占用端口的程序，拔线重插；(d) 换数据线。确认固件：Shell 里应显示 `MicroPython v... on ... Raspberry Pi Pico with RP2040`。
**怎么验证修好了**：Thonny 左下角 Shell 出现 `>>>` 提示符，直接敲 `import sys` + 回车有输出；点运行按钮能往 Pico 上跑程序。

### 4. 拖入 UF2 后 RPI-RP2 盘消失，但程序没跑 / 固件没生效
**现象**：把 .uf2 拖进 RPI-RP2 盘，盘自己弹出（正常），但之后插电板子没有反应，或 Thonny 连不上。
**原因**：UF2 拖放是"拷贝完自动重启"：拷贝过程中盘提前弹出/文件不完整（复制被中断）、或下错了固件（比如下了 Pico W 的版本，或下成 C SDK 的示例而不是 MicroPython）。
**解决**：按住 BOOTSEL 重新进 RPI-RP2 模式，确认拖的是**官网对应本板**的 MicroPython UF2（Pico 版，不要 Pico W 版），等拷贝进度完全走完、盘自动消失再拔线。若固件被刷坏成无法启动的状态，BOOTSEL 在芯片 ROM 里，**永远能进**——按住 BOOTSEL 重刷即可恢复，官方文档明确 Pico 不会因软件"变砖"。
**怎么验证修好了**：重刷后插电，Thonny 能连上并出现 `>>>`；板载 LED 能跑闪烁程序。

### 5. 代码里写了 Pin(25) 却报错 / LED 不亮（进阶坑）
**现象**：用 `Pin(25, Pin.OUT)` 控制板载 LED，运行报错或灯不亮。
**原因**：(a) 手里其实是 **Pico W**（无线版），它的板上 LED 不在 GP25，而是挂在无线芯片的 WL_GPIO0 上；(b) 固件版本太老或非官方。
**解决**：看板子背面丝印确认型号（本空间物料 A-025 是普通 Pico，LED 在 GP25；若是 Pico W，用 `from machine import Pin; led = Pin("LED", Pin.OUT)` 这类网络版专属写法）；升级到官方最新 MicroPython 固件。
**怎么验证修好了**：用对应型号的代码点亮板上 LED；`import sys; sys.implementation._machine` 输出确认固件对应的板子型号。
