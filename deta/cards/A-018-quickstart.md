---
material_id: A-018
card_type: quickstart
title: STM32F103C8T6 最小系统板三分钟上手
points:
  - 准备：Keil MDK + ST-Link/V2 烧录器 + ST-Link 驱动；最小系统板没有 USB 口，烧录全靠 ST-Link
  - 接线：ST-Link 四线 SWDIO/SWCLK/GND/3V3 对插；BOOT0 跳线置 0（主闪存启动）；LED 长脚→PB1、短脚→220Ω→GND
  - 跑通：Keil 建好工程点下载，LED 闪烁即成功；看不到先查"ST-Link 能否识别"和"BOOT0 跳线"
source:
  - https://www.st.com/resource/en/datasheet/stm32f103c8.pdf
  - https://github.com/Embedfire/products/wiki/野火STM32F103C8T6核心板
---

## 第零步：装软件与驱动

1. 安装 **Keil MDK-ARM**（正点原子/野火电赛主流环境；免费替代方案 STM32CubeIDE 也可以，本卡片以 Keil 为例）；
2. 去 ST 官网搜 **ST-Link 驱动**（ST-LINK driver）下载安装，否则 Keil 认不到烧录器；
3. 准备一个 **ST-Link/V2**（淘宝几十块的兼容版完全够用）。

## 第一步：接线（断电操作！）

先把 BOOT 跳线摆对：**BOOT0 置 0、BOOT1 置任意**（从主闪存启动，ST-Link 用 SWD 直接烧写，不需要进 bootloader）。

ST-Link 四线接法（板子上 SWDIO/SWCLK 丝印，对应 PA13/PA14）：

| ST-Link 引脚 | 接到最小系统板 |
|---|---|
| SWDIO | SWDIO（PA13） |
| SWCLK | SWCLK（PA14） |
| GND | GND |
| 3.3V | 3V3 |

外接一颗 LED（演示用，板载 LED 引脚各板不同，外接最稳）：

| LED 引脚 | 接到板子 |
|---|---|
| 长脚（阳极） | PB1 |
| 短脚（阴极） | 220Ω 电阻 → GND |

## 第二步：建工程（每个新板一次）

新建 Keil 工程时三处必须配对（野火官方资料原话，配错编译/烧录必挂）：

1. **Options for Target → Device**：芯片选 **STM32F103C8**；
2. **Options for Target → C/C++ → Define**：写 **STM32F10X_MD**（不带引号，MD=中容量）；
3. **启动文件**：加入 **startup_stm32f10x_md.s**（中容量启动文件，别加成 hd 或 ld）。

再把标准外设库的 `Library/src` 全部 .c 文件加进工程。

## 第三步：写第一个程序并烧录

`main.c` 里粘入下面的**完整可运行代码**（标准外设库风格，正点原子/野火资料同款）：

```c
#include "stm32f10x.h"

// 简易软件延时（先跑通再说，工程上请改用定时器）
void Delay(volatile uint32_t n) {
  while (n--) {}
}

int main(void) {
  GPIO_InitTypeDef GPIO_InitStructure;

  // 1. 打开 GPIOB 时钟——STM32 任何外设使用前必须先开时钟，忘了就全不工作
  RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);

  // 2. 配置 PB1 为推挽输出
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_1;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
  GPIO_Init(GPIOB, &GPIO_InitStructure);

  // 3. 主循环：亮 → 延时 → 灭 → 延时
  while (1) {
    GPIO_SetBits(GPIOB, GPIO_Pin_1);    // 输出高电平，LED 亮
    Delay(1000000);
    GPIO_ResetBits(GPIOB, GPIO_Pin_1);  // 输出低电平，LED 灭
    Delay(1000000);
  }
}
```

编译（F7）无错误后，**Options for Target → Debug** 选 **ST-Link Debugger**，点右侧 **Settings**——能看到目标芯片 ID 说明 ST-Link 连接成功；返回后点 **下载（LOAD）**。

## 烧录成功后预期看到

- Keil 输出窗口提示 `Flash Load: Program at 0x08000000... OK` 之类完成信息；
- 外接 **LED 每秒闪一次**（没反应先按一下板上 RESET 键）；
- 反复改 `Delay` 的数值再下载，闪烁快慢会跟着变——这就是"改代码→编译→下载→看现象"的完整闭环。

## 看不到灯闪，第一步查什么？

1. 下载有没有报错？报错先看"常见错误"第 1、2 条（ST-Link 识别、BOOT0 跳线）；
2. 下载成功但灯不亮：**按一下 RESET**；确认 BOOT0 是 0（在 1 上程序不会从 Flash 启动）；
3. 确认 LED 接的引脚就是代码里的 PB1，长短脚没反。

## 下一步学什么（全链路路线图）

1. **GPIO 点灯**（已完成）→ 学按键输入（GPIO_ReadInputDataBit）与外部中断 EXTI；
2. **定时器**：SysTick 精确延时、定时器中断、PWM 输出（调电机/舵机速度）；
3. **USART 串口**：printf 重定向到串口助手，看板子"说话"；
4. **传感器 + 执行器**：ADC 读电位器/光敏、编码器测速、OLED 显示；
5. **完成电赛项目**：把"传感器 → 控制算法 → 电机执行"串成完整作品。
