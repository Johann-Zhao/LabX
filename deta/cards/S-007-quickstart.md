---
material_id: S-007
card_type: quickstart
title: 土壤湿度传感器三分钟上手
points:
  - 接线：VCC→5V、GND→GND、AO→A0（DO 可先不接）
  - 上传代码，串口监视器（9600）打印 analogRead(A0) 读数
  - 判断标准：读数越小越湿——空气里数值大，插湿土里数值明显变小
---

## 第一步：接线（断电操作！）

| HL-69 引脚 | 接到 Arduino Uno |
|---|---|
| VCC | 5V |
| GND | GND |
| AO | A0 |
| DO | 先不接 |

## 第二步：上传代码

Arduino IDE 新建文件，粘贴：

```cpp
void setup() {
  Serial.begin(9600);
}

void loop() {
  int value = analogRead(A0);
  Serial.println(value);   // 0-1023，越小越湿
  delay(1000);             // 每秒读一次
}
```

工具 → 开发板选 Arduino Uno，端口选 COM 口，点上传。打开串口监视器，波特率选 **9600**。

## 第三步：看读数变化

1. 探头拿在手里（空气）：读数接近 1023（最大）；
2. 插进干燥花盆土里：读数下降一些；
3. 浇一点水再插：读数明显变小（比如降到 300-600）。

把干、湿两组数值都记下来，之后写"自动浇花"逻辑时用它们定阈值。

## 想做成"自动浇花"

用读数判断：`analogRead(A0)` 大于 700 说明土干了，点亮 LED 或通过继电器模块打开水泵。用 DO 输出接数字脚也可以，但先实测触发方向再写代码。
