---
material_id: E-001
card_type: quickstart
title: 5V 微型水泵 三分钟上手
points:
  - 必须先浸水再通电：泵体完全没入水中，严禁干转
  - 接线：继电器模块 IN→D7，水泵红线接模块 COM、黑线接电源负极
  - 烧录程序后开泵 2 秒停 1 秒，看到出水即跑通
---

## 第一步：准备（1 分钟）

材料：水泵、5V 继电器模块（高电平触发）、Arduino、杜邦线、一杯水（水位要能没过泵体）。

**先把泵放进水里泡着，通电前就位。**

## 第二步：接线（1 分钟，断电操作）

| 继电器模块 | 接到 |
|---|---|
| VCC | Arduino 5V |
| GND | Arduino GND |
| IN | Arduino D7 |
| COM | 水泵红线（+） |
| NO | 5V 电源正极 |
| — | 水泵黑线（-）接电源负极，电源负极与 Arduino GND 共地 |

## 第三步：烧录程序（1 分钟）

```cpp
const int PUMP_PIN = 7;

void setup() {
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW); // 默认关泵
}

void loop() {
  digitalWrite(PUMP_PIN, HIGH); // 开泵
  delay(2000);
  digitalWrite(PUMP_PIN, LOW);  // 关泵
  delay(1000);
}
```

## 验证

上电后水泵应转 2 秒、停 1 秒，杯子里能看到水流。没动静依次查：水位够不够、继电器 IN 是不是 D7、电源共地了没有。

## 做完收尾

先断电，再取出水泵，倒掉余水晾干。不要让泵在无水状态下通电超过几秒。
