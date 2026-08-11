---
material_id: S-009
card_type: quickstart
title: TCRT5000 红外循迹传感器 三分钟上手
points:
  - 接线：VCC→5V、GND→GND、DO→D2、AO→A0；传感器窗口朝下，离地 2~3mm 贴装
  - 跑通：串口 9600 同时打印 AO 和 DO，白纸、黑线各看一眼数值，记录两个方向的读数
  - 调阈值：拧蓝色电位器让 DO 在黑白交界处翻转；没反应先查供电和安装高度
source:
  - https://pcbsync.com/tcrt5000-arduino/
  - https://www.vishay.com/docs/83760/tcrt5000.pdf
---

## 第一步：安装模块

- 模块有**两个小窗口**（红外发射 + 接收）的面朝下
- **离地 2~3mm**：Vishay 数据手册标注最佳检测距离 2.5mm、有效范围 0.2~15mm——贴地安装才有信号
- 小车底盘开孔或扎带固定，**别用胶带糊住窗口**；窗口表面保持干净

## 第二步：接线（断电操作！）

| 模块引脚 | 接到 Arduino Uno |
|---|---|
| VCC | 5V |
| GND | GND |
| DO | D2 |
| AO | A0（可选，但建议先接上看模拟值） |

杜邦线直插，无需面包板。

## 第三步：烧录 + 串口

Arduino IDE 新建 sketch，粘贴下面代码（参考官方教程代码）：

```cpp
const int digitalPin = 2;
const int analogPin = A0;

void setup() {
  Serial.begin(9600);
  pinMode(digitalPin, INPUT);
}

void loop() {
  int analogValue = analogRead(analogPin);
  int digitalValue = digitalRead(digitalPin);
  Serial.print("Analog: ");
  Serial.print(analogValue);
  Serial.print("  Digital: ");
  Serial.println(digitalValue);
  delay(100);
}
```

上传后打开串口监视器，波特率 **9600**。

**预期输出**（每 100ms 一行）：

```
Analog: 120  Digital: 0
Analog: 135  Digital: 0
Analog: 780  Digital: 1
```

**实测流程**：
1. 传感器放在**白纸**上 → 记下 Analog 和 Digital 值（反射强，Analog 偏低）
2. 移到**黑线/黑胶带**上 → 记下两个值（吸光，Analog 明显变高）
3. 确认 DO 在黑白之间能翻转；**如果 DO 不翻，见第四步调电位器**

⚠️ 各模块 DO 电平方向可能相反（有的黑=1、有的黑=0），判断逻辑按你的实测写，别照抄别人的代码。

## 第四步：调电位器（DO 不翻转时）

1. 传感器保持在你计划的工作高度（2~3mm）
2. 下方放黑色表面，用小螺丝刀拧**蓝色电位器**，直到 DO 变成对应电平
3. 换白色表面，确认 DO 能翻回另一电平
4. 来回切换黑白，微调到两种表面都稳定区分

## 没输出？第一查什么

1. **波特率**是不是 9600
2. **离地高度**：传感器离目标超过 15mm 就收不到反射（Vishay 数据手册的有效范围上限）
3. **供电**：5V / GND 是否接对
4. DO / AO 插的引脚和代码里写的是否一致
5. 模块上的电源指示灯亮不亮

## 下一步

- **循迹小车**：装 2 个传感器（左右各一），`digitalRead` 判断：左传感器压线 → 右转，右传感器压线 → 左转，都在白底 → 直行（教程里有完整双传感器示例代码）
- 进阶：用 AO 做 PID 循迹，转弯更平滑；给传感器加黑色遮光罩，提升抗环境光能力
