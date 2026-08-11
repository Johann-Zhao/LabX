---
material_id: A-017
card_type: quickstart
title: Arduino Uno R3 三分钟上手
points:
  - 软件：官网下载 Arduino IDE 2.x 装好即可（官方板免驱动；克隆板需另装 CH340 驱动）
  - 接线：LED 长脚→D13、短脚→220Ω 电阻→GND，一根电阻一根 LED 就能点亮
  - 流程：选板 Arduino Uno → 选端口 COM 口 → 打开 Blink 示例点上传，板载 L 灯每秒闪一次即成功
source:
  - https://docs.arduino.cc/hardware/uno-rev3/
  - https://store.arduino.cc/products/arduino-uno-rev3
---

## 第零步：装软件（只需一次）

1. 打开官网 https://www.arduino.cc/en/software ，下载 **Arduino IDE 2.x** 的 Windows 版，一路下一步安装；
2. 用 USB 线（**要能传数据的线**）把 Uno 连到电脑，Windows 会弹出"安装驱动"提示，等它装完；
3. 正版板（ATmega16U2 转串口）免驱动；**克隆板（板上有 CH340 小芯片）需要另外装 CH340 驱动**，搜"CH340 驱动"下载安装，否则端口列表里啥都没有。

## 第一步：接线（断电操作！）

点亮一颗 LED 只需要两个元件，这是完整接线：

| LED 引脚 | 接到 Arduino Uno |
|---|---|
| 长脚（阳极） | D13 |
| 短脚（阴极） | 220Ω 电阻的一端 |
| 电阻另一端 | GND |

220Ω 电阻色环：红-红-棕-金。没有 220Ω？100Ω-1kΩ 都能用，**但必须串电阻**，否则烧引脚。

> 不接线也能验证：板载 L 灯本来就接在 D13 上。但**外接 LED 才是真正学会接线**，推荐照做。

## 第二步：选板选口

1. 工具 → 开发板 → 选 **Arduino Uno**；
2. 工具 → 端口 → 选刚出现的 **COM 口**（如 COM3）。端口里啥都没有 → 查第零步的驱动和 USB 线。

## 第三步：跑通第一个程序

打开 Arduino IDE，把下面代码整个复制进去（这就是官方 Blink 示例的完整内容）：

```cpp
// 板载 L 灯和外接 LED 都接在 D13，HIGH 点亮，LOW 熄灭
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);   // LED_BUILTIN 就是 D13
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH); // 亮
  delay(1000);                     // 等 1 秒
  digitalWrite(LED_BUILTIN, LOW);  // 灭
  delay(1000);                     // 再等 1 秒
}
```

点左上角 **→（上传）** 按钮。底部提示"上传成功（Done uploading）"后：

- 板载 **L 灯** 和外接 LED **同时每秒闪一次**；
- 想确认代码确实生效：把 `delay(1000)` 改成 `delay(200)`，再上传，灯会闪得快 5 倍。

## 看不到灯闪，第一步查什么？

1. 先看上传有没有成功——失败的话按"常见错误"卡片第 1 条查（板型/端口/驱动/USB 线）；
2. 上传成功但灯不亮：LED 长短脚是否插反（长脚接 D13）？电阻是否串在回路里？
3. 按一下板上的 RESET 键再观察。

## 打开串口监视器看看

工具 → 串口监视器（或右上角放大镜图标），波特率选 **9600**。把上面的代码在 `setup()` 里加一行 `Serial.begin(9600);`，loop 里加一行 `Serial.println("hello");`，上传后监视器里每 1 秒打印一行 hello——这是以后调试的必备技能。

## 下一步学什么（全链路路线图）

1. **点亮 LED**（已完成）→ 控制亮灭、PWM 调亮度（analogWrite）；
2. **读传感器**：接 DHT22 温湿度（用 DHT sensor library，见 S-003 卡片）或电位器（接 A0，analogRead 读数）；
3. **驱动执行器**：舵机（Servo 库）、电机（L298N 模块，注意共地+单独供电）；
4. **完成项目**：把"传感器读数 → 逻辑判断 → 执行器动作"串起来，就是一个完整的作品。
