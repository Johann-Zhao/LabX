---
material_id: M-013
card_type: quickstart
title: 单路继电器三分钟上手
points:
  - 接线：VCC→5V、GND→GND（共地）、IN→D7；负载回路：电源正极→负载→NO→COM→电源负极
  - 代码就一个 digitalWrite：LOW 吸合 / HIGH 释放（低电平触发模块）
  - 先接 12V 低压负载跑通，再碰 220V
---

## 第一步：接线（断电操作！）

准备：Arduino Uno、12V 灯带/风扇、12V 电源。

| 继电器模块 | 接到 |
|---|---|
| VCC | Arduino 5V |
| GND | Arduino GND（必须共地） |
| IN | Arduino D7 |
| COM | 12V 电源负极 |
| NO | 12V 灯带的一端 |
| 灯带另一端 | 12V 电源正极 |

这样接：模块一吸合，灯带回路就通了。先用 12V 低压练手，别直接上 220V。

## 第二步：烧代码

```cpp
// 继电器闪烁测试：IN→D7（低电平触发模块）
const int relayPin = 7;

void setup() {
  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, HIGH); // 先释放
}

void loop() {
  digitalWrite(relayPin, LOW);  // 吸合：灯亮
  delay(3000);
  digitalWrite(relayPin, HIGH); // 释放：灯灭
  delay(3000);
}
```

## 第三步：上电看效果

灯应每 3 秒亮灭交替，模块上的指示灯同步变化。**如果你的模块是高电平触发，把代码里的 LOW 和 HIGH 对调即可**（先看丝印或实测确认）。

## 遇到问题？

灯不亮先查：共地了吗？负载回路串对了吗（灯带一端接 NO，别接 NC）？IN 极性对吗？详见"常见错误"卡片。
