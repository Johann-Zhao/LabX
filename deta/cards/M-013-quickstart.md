---
material_id: M-013
card_type: quickstart
title: 单路继电器三分钟上手：每秒通断一次
points:
  - 接线：VCC→5V、GND→GND（共地）、IN→D7；负载回路：电源正极→COM、NO→灯带正极、灯带负极→电源负极
  - 代码就一句话：低电平触发模块 digitalWrite(LOW) 吸合（咔哒）、HIGH 释放
  - 没反应先听声音：没咔哒声查信号侧（VCC/共地/IN），有咔哒声查负载侧（COM/NO 回路）
source:
  - https://envistiamall.com/blogs/learn/2-channel-5v-spdt-relay-module-with-optocoupler-user-guide
  - https://www.pishop.co.za/store/5v-1-channel-level-trigger-optocoupler-relay-module
---

## 第一步：准备（1 分钟）

材料：Arduino Uno、单路 5V 继电器模块、5V LED 灯带或小灯泡（练手用低压负载，**先别碰 220V**）、5V 电源（USB 充电头 + 杜邦线即可）。

**全程断电操作，接完检查两遍再上电。**

## 第二步：接线（逐根线）

| 继电器模块 | 接到 | 说明 |
|---|---|---|
| VCC | Arduino 5V | 模块供电 |
| GND | Arduino GND | 共地，IN 信号才有参考电平 |
| IN | Arduino D7 | 控制信号 |
| COM | 5V 电源正极 | 负载回路的"公共端" |
| NO | 灯带正极 | 常开触点：吸合才通电 |
| 灯带负极 | 5V 电源负极 | 同时和 Arduino GND 共地 |

负载回路是一条完整的链：**5V 电源正 → COM →（触点）→ NO → 灯带 → 5V 电源负**。Arduino 只发信号，电流不走 Arduino。

## 第三步：烧代码

```cpp
// 继电器每秒通断一次：IN→D7（低电平触发模块：LOW=吸合，HIGH=释放）
const int RELAY_PIN = 7;

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // 上电先释放，防止乱动作
}

void loop() {
  digitalWrite(RELAY_PIN, LOW);  // 吸合：咔哒一声，灯亮
  delay(1000);
  digitalWrite(RELAY_PIN, HIGH); // 释放：咔哒一声，灯灭
  delay(1000);
}
```

> 如果你的模块是**高电平触发**（看丝印或说明），把代码里的 LOW 和 HIGH 对调即可。

## 第四步：上电看效果

预期现象：

- 每秒听到一声"咔哒"，模块上的红色状态灯同步亮灭
- 灯带跟着亮 1 秒、灭 1 秒

## 没反应？先听声音分叉排查

1. **没有咔哒声** → 问题在信号侧：VCC 有 5V 吗？GND 共地了吗？IN 真的接到 D7 了吗？代码里的触发方式和模块一致吗？
2. **有咔哒声但灯不亮** → 问题在负载侧：灯带是接在 **NO** 上吗（接成 NC 会"平时亮、触发反而不亮"）？COM/NO 螺丝端子拧紧了吗？5V 电源有电吗？

## 下一步

把 IN 换成土壤湿度模块的输出（LM393 湿度比较器，AO 接 A0、DO 接 D7）→ **自动浇花**：土干了继电器吸合水泵转，土湿了自动停。或者把灯带换成光敏电阻判断的"天黑自动开灯"。
