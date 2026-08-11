---
material_id: M-011
card_type: manual
title: L298N 双H桥电机驱动模块 说明书要点
points:
  - 双 H 桥：一块模块可驱动 2 路直流电机（或 1 路两相步进电机），方向由 IN1~IN4 控制、速度由 ENA/ENB 的 PWM 控制
  - 两套电源各管各的：VS 接电机电源（ST 手册上限 46V，模块建议 7~12V），VSS 是 5V 逻辑电源，且必须与 Arduino 共地
  - 芯片导通压降约 2V：12V 供电时电机实际只拿到约 10V，想让电机满速，VS 要比电机额定电压高约 2V
source:
  - https://lastminuteengineers.com/l298n-dc-stepper-driver-arduino-tutorial/
  - https://industrialmonitordirect.com/cs/blogs/knowledgebase/l298n-h-bridge-module-for-alternating-slave-clock-pulse-driver
---

## 关键参数

| 参数 | 值 |
|---|---|
| 电机电源 VS | 最高 46V（ST 手册上限）；模块受板载稳压器散热限制，常用范围 7~12V |
| 逻辑电源 VSS | 4.5~7V，典型 5V（TTL 兼容，输入高电平 ≥ 2.3V） |
| 输出电流 | 每通道连续 2A（手册标短时峰值，t<100µs 可达 4A）；模块散热片小，长时间运行建议 ≤1A |
| 导通压降 | 约 2V（1A 时手册典型 2.0V、最大 3.2V） |
| 板载 5V 稳压器 | 78M05：由 VS 降压给逻辑电路供电，可额外输出约 0.5A；VS 高于 12V 时不宜使用它 |
| 静态电流 | 约 13~22mA（空载） |

## 模块引脚

| 引脚 | 作用 |
|---|---|
| VS（丝印常写 +12V） | 电机电源正极，接 7~12V 电池或电源适配器 |
| GND | 电机电源负极；**必须同时连到 Arduino 的 GND（共地）** |
| 5V / VSS | 逻辑电源。跳线帽在位：板载稳压器供电，此脚是 5V 输出（**别把它再接到 Arduino 5V，会打架**）；跳线帽拔掉：必须自己外接 5V |
| IN1 / IN2 | 通道 A 方向控制，接 Arduino 数字引脚 |
| IN3 / IN4 | 通道 B 方向控制 |
| ENA / ENB | 通道 A/B 使能端，跳线帽短接 = 始终使能（全速） |
| OUT1 / OUT2 | 通道 A 电机两根线（无正反之分，接反只是转向反） |
| OUT3 / OUT4 | 通道 B 电机两根线 |

## 控制逻辑表（以通道 A 为例，ENA=1 时）

| IN1 | IN2 | 电机状态 |
|---|---|---|
| 0 | 0 | 停（下管导通制动） |
| 1 | 0 | 正转 |
| 0 | 1 | 反转 |
| 1 | 1 | 停（上管导通制动） |

ENA=0 时输出高阻，电机自由滑行。想让电机转，**IN 一高一低**；想让电机停，**两个相同**。

## 两个跳线帽，别搞混

- **ENA/ENB 跳线帽**：默认短接 = 通道全速。想调速就拔掉，把 ENA 接到 Arduino 的 PWM 引脚（如 D9），用 `analogWrite(9, 0~255)` 调速；IN1/IN2 仍负责方向。拔了又不接 PWM，电机就完全不动。
- **5V 稳压跳线帽**（位于 VSS 和 12V 之间）：VS 在 7~12V 时保持短接（板载稳压器给逻辑供电）；**VS 超过 12V 必须拔掉**并给 VSS 外接 5V，否则稳压器过热烧毁；跳线帽在位时 VSS 是输出，千万别再给它接 5V。

## 适合 / 不适合

- 适合：双电机小车、1 路两相步进电机、需要正反转和调速的直流电机、教学演示。
- 不适合：低压小电机（压降约 2V 太伤，5V 电机要配约 7V 电源）、长时间大电流运行（模块散热差，建议 ≤1A）、电池供电的功耗敏感项目（双极型管效率低）、需要无声或高频切换的场合。

## 官方资源

- ST L298 数据手册 PDF（ST 官方手册，DFRobot 托管镜像）：`https://www.dfrobot.com.cn/image/data/DRI0002/CN/L298 datasheet.pdf`
- 模块接线与代码教程（Last Minute Engineers）：`https://lastminuteengineers.com/l298n-dc-stepper-driver-arduino-tutorial/`
