---
material_id: M-011
card_type: quickstart
title: L298N 三分钟上手
points:
  - 接线：VS→电池正极、GND→电池负极且与 Arduino GND 共地、IN1→D5、IN2→D6，跳线帽保持默认
  - 电机动不了先查两件事：共地接了吗？VS 供电够不够（推荐 7~12V）？
  - 代码只有两行 digitalWrite：一个 HIGH 一个 LOW 就转，两个相同就停
---

## 第一步：接线（断电操作！）

准备：Arduino Uno、7.4V 锂电池组（两节 18650）或 9~12V 电源、直流电机。

| L298N 引脚 | 接到 |
|---|---|
| VS（12V） | 电池/电源正极 |
| GND | 电池/电源负极，**并接到 Arduino 的 GND**（共地，忘了必出问题） |
| IN1 | Arduino D5 |
| IN2 | Arduino D6 |
| OUT1 OUT2 | 电机两根线（接反只是转反，不烧） |
| VSS（5V） | 保持跳线帽短接（VS 是 7~12V 时板载稳压生成 5V，不用另接） |
| ENA | 保持跳线帽短接（先全速跑通，再谈调速） |

## 第二步：烧代码

```cpp
// 电机正反转测试：IN1→D5，IN2→D6
void setup() {
  pinMode(5, OUTPUT);
  pinMode(6, OUTPUT);
}

void loop() {
  digitalWrite(5, HIGH);   // 正转
  digitalWrite(6, LOW);
  delay(2000);

  digitalWrite(5, LOW);    // 反转
  digitalWrite(6, HIGH);
  delay(2000);
}
```

## 第三步：上电看效果

插上 USB 和电池电源，电机应每 2 秒正反交替。**两个引脚输出相同（都 HIGH 或都 LOW）时电机停转。**

## 想调速？

拔掉 ENA 跳线帽，把 ENA 接到 Arduino 的 PWM 引脚（如 D9），代码改用 `analogWrite(9, 150)` 控制速度（0~255）。IN1/IN2 仍定方向，速度和方向互不影响。
