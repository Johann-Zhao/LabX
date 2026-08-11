---
material_id: E-001
card_type: quickstart
title: 5V 微型水泵三分钟上手：定时浇 5 秒
points:
  - 铁律：先把泵完全浸进水里，再通电——干转几秒就可能烧泵
  - 接线：继电器 IN→D7；负载回路：5V 电源正→COM、NO→泵红线、泵黑线→5V 电源负极
  - 代码就一句话：LOW 吸合开泵 5 秒、HIGH 断开停 55 秒（低电平触发模块）
source:
  - https://shillehtek.com/blogs/shillehtek-product-manuals/mini-submersible-water-pump-5v-120lph-arduino-esp32-manual
  - https://www.gravityelectronic.com/shop/mini-water-pump-5v-dc-12445
---

## 第一步：准备（1 分钟）

材料：5V 微型水泵、单路 5V 继电器模块、Arduino Uno、5V 电源（USB 充电头，电流 ≥500mA）、软管一段、水杯（水位要能没过泵体）。

**先把泵放进水杯里泡着——通电之前就必须就位，这是铁律。**

## 第二步：接线（1 分钟，断电操作）

| 继电器模块 | 接到 | 说明 |
|---|---|---|
| VCC | Arduino 5V | 模块供电 |
| GND | Arduino GND | 共地 |
| IN | Arduino D7 | 控制信号 |
| COM | 5V 电源正极 | 负载回路公共端 |
| NO | 水泵红线（+） | 吸合时给泵供电 |
| — | 水泵黑线（-）接 5V 电源负极 | 电源负极再与 Arduino GND 共地 |

完整回路：**5V 电源正 → COM →（继电器触点）→ NO → 泵红线 → 泵 → 泵黑线 → 5V 电源负**。水泵的电流完全不走 Arduino。

## 第三步：烧代码

```cpp
// 自动浇花雏形：定时浇 5 秒，停 55 秒（继电器 IN→D7，低电平触发）
const int RELAY_PIN = 7;

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // 上电默认断开
  Serial.begin(9600);
}

void loop() {
  digitalWrite(RELAY_PIN, LOW);  // 吸合 → 水泵转
  Serial.println("浇水 5 秒");
  delay(5000);

  digitalWrite(RELAY_PIN, HIGH); // 断开 → 水泵停
  Serial.println("停 55 秒");
  delay(55000);
}
```

> 如果你的继电器是**高电平触发**，把 LOW/HIGH 对调。

## 第四步：上电看效果

先确认泵还泡在水里，然后上电。预期现象：

- 串口监视器（9600）打印"浇水 5 秒"→"停 55 秒"循环
- 继电器每 55 秒咔哒一声，出水管喷水 5 秒后停止

## 没反应？第一查这四样（按顺序）

1. **泵浸水了吗**：泵体完全没入水中？水杯里水够吗？
2. **继电器咔哒了吗**：没有咔哒 → 查信号侧（VCC/共地/IN 接对 D7 没）；有咔哒但不出水 → 查负载侧（COM/NO 回路、泵线接牢没）。
3. **回路对了吗**：是不是"电源正→COM、NO→泵红线、泵黑线→电源负"？接成 NC 会变成"一直转、触发才停"。
4. **电源够力吗**：USB 口功率不足（老电脑 USB 口）会让泵转不动，换 5V/1A 充电头。

## 下一步

加一个**土壤湿度传感器**（LM393 湿度模块：AO→A0 测干湿，DO→D7 直接触发继电器）→ 土干了才浇、土湿自动停，就是真·自动浇花机。再给水箱加**浮球开关/低水位检测**防止抽干空转——干转是水泵的头号死因，见"常见错误"卡片。
