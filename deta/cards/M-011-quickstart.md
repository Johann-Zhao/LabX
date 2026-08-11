---
material_id: M-011
card_type: quickstart
title: L298N 三分钟上手：让电机正转-停-反转
points:
  - 接线：VS→电池正极、GND→电池负极且与 Arduino GND 共地、IN1→D8、IN2→D7、IN3→D5、IN4→D4，两个跳线帽保持默认
  - 代码就一个思路：IN1/IN2 一高一低 = 转，两个相同 = 停；一个 HIGH 一个 LOW 换边就换转向
  - 电机动不了先查三件事：共地接了吗？跳线帽还在吗？VS 供电够不够（7~12V）？
source:
  - https://lastminuteengineers.com/l298n-dc-stepper-driver-arduino-tutorial/
  - https://industrialmonitordirect.com/cs/blogs/knowledgebase/l298n-h-bridge-module-for-alternating-slave-clock-pulse-driver
---

## 第一步：准备（1 分钟）

材料：Arduino Uno、L298N 模块、直流电机 1~2 个、7~12V 电源（6 节 1.5V 电池盒 = 9V，或 12V 电源适配器）、杜邦线若干。

**全程断电操作，接完检查两遍再上电。**

## 第二步：接线（逐根线）

| L298N 引脚 | 接到 | 说明 |
|---|---|---|
| VS（12V 螺丝端子） | 电池盒/电源适配器 **正极** | 电机电源。别用 Arduino 的 5V 带电机 |
| GND（螺丝端子） | 电源负极，**并接一根线到 Arduino GND** | 共地！忘了它电机必出怪问题 |
| IN1 | Arduino D8 | 通道 A 方向 |
| IN2 | Arduino D7 | 通道 A 方向 |
| IN3 | Arduino D5 | 通道 B 方向 |
| IN4 | Arduino D4 | 通道 B 方向 |
| OUT1、OUT2 | 电机 A 两根线 | 接反了只是转向反，不会烧 |
| OUT3、OUT4 | 电机 B 两根线 | 同上 |
| 5V 跳线帽（VSS 旁） | 保持短接 | VS 是 7~12V 时板载稳压器会自己出 5V，VSS 不用接任何线 |
| ENA、ENB 跳线帽 | 保持短接 | 先全速跑通，再谈调速 |

**别动 5V 跳线帽和 ENA/ENB 跳线帽，保持出厂状态。**

## 第三步：烧代码

```cpp
// L298N 双电机测试：正转 2 秒 → 停 2 秒 → 反转 2 秒 → 停 2 秒
// 接线：IN1→D8, IN2→D7, IN3→D5, IN4→D4（ENA/ENB 跳线帽保持短接 = 全速）
const int IN1 = 8, IN2 = 7, IN3 = 5, IN4 = 4;

void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  Serial.begin(9600);
  stopMotors();                 // 上电先确保电机不转
  Serial.println("L298N 测试开始");
}

void loop() {
  // 正转 2 秒：IN1 高、IN2 低 → 电机 A 正转
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
  Serial.println("正转");
  delay(2000);

  // 停 2 秒：两个 IN 都拉低
  stopMotors();
  Serial.println("停");
  delay(2000);

  // 反转 2 秒：把 HIGH/LOW 换边
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
  Serial.println("反转");
  delay(2000);

  // 停 2 秒
  stopMotors();
  Serial.println("停");
  delay(2000);
}

void stopMotors() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}
```

## 第四步：上电看效果

插 USB 上传程序后，**再把电机电源接上**。预期现象：

- 串口监视器（9600）每 2 秒打印：正转 → 停 → 反转 → 停，循环
- 两个电机跟着"转 2 秒、停 2 秒、反转 2 秒、停 2 秒"
- 模块微微发热属正常，烫到不能摸立即断电

## 没反应？第一查这四样（按顺序）

1. **共地**：L298N 的 GND 有没有跟 Arduino GND 连在一起？没有共地，信号全是悬空的。
2. **跳线帽**：ENA/ENB 跳线帽还在吗？拔了又不接 PWM，通道是关的。
3. **电源**：VS 有没有 7~12V？电池没电了没有？
4. **接线**：IN1/IN2 和 D8/D7 对得上吗？OUT 端子拧紧了吗？

## 想调速？

拔掉 ENA 跳线帽，ENA 接 Arduino 的 PWM 引脚（如 D9），代码里 `analogWrite(9, 150)`（0~255）。IN1/IN2 仍管方向，速度和方向互不影响。

## 下一步

给电机装上轮子就是双驱小车 → 加个 HC-SR04 超声波传感器做避障 → 拔跳线帽接 PWM 做慢速转弯。更完整的教程见 [Last Minute Engineers 的 L298N 教程](https://lastminuteengineers.com/l298n-dc-stepper-driver-arduino-tutorial/)。
