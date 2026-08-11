---
material_id: M-013
card_type: manual
title: 单路继电器模块（5V 光耦隔离）说明书要点
points:
  - 小信号控大电流：Arduino 的 5V 信号只负责触发，真正通断负载电源的是 COM/NO/NC 触点回路
  - 光耦隔离：信号经光耦（LED+光敏管）传给线圈侧，线圈通断产生的反电动势打不到单片机引脚
  - 默认多为低电平触发：IN 拉低 = 吸合（咔哒一声）；触发方式看板上丝印/说明，先确认再写代码
source:
  - https://envistiamall.com/blogs/learn/2-channel-5v-spdt-relay-module-with-optocoupler-user-guide
  - https://www.pishop.co.za/store/5v-1-channel-level-trigger-optocoupler-relay-module
---

## 关键参数

| 参数 | 值 |
|---|---|
| 工作电压 | 5V DC（VCC 对 GND） |
| 触发电流 | 约 5mA（光耦输入侧） |
| 触点容量 | 常见 AC 250V/10A、DC 30V/10A（以模块丝印为准；连续负载建议降额到 7~8A 使用） |
| 触点类型 | SPDT 单刀双掷：COM（公共端）/ NO（常开）/ NC（常闭） |
| 隔离方式 | 光耦隔离（常见 PC817） |
| 触发方式 | 多数默认低电平触发（IN 为低时吸合）；部分板子带跳线可切高电平触发 |
| 指示灯 | 电源指示灯 + 继电器状态灯（吸合时亮） |

## 模块引脚

- **VCC / DC+** —— 接 5V
- **GND / DC-** —— 接 Arduino GND（必须共地，IN 信号才有参考电平）
- **IN** —— 信号脚，接 Arduino 数字引脚（如 D7）
- **COM** —— 公共端，负载回路必过这一端
- **NO（常开）** —— 不吸合时断开、吸合时与 COM 导通。**控制水泵、灯带"通电才工作"的设备用 NO**
- **NC（常闭）** —— 不吸合时与 COM 导通、吸合时断开。想让设备"平时通电、触发才停"才用 NC
- **高/低电平触发跳线**（部分板子有）—— 跳线插 LOW 侧 = 低电平触发，插 HIGH 侧 = 高电平触发

## 工作原理

继电器里是一个电磁线圈 + 一组机械触点。不吸合时，内部弹簧把触点压在 **NC** 上（COM-NC 通）；IN 触发后线圈通电，电磁铁把触点拉到 **NO** 上（COM-NO 通），伴随一声"咔哒"。

```
未触发：COM ── NC 通，COM ── NO 断（灯灭）
触发后：COM ── NC 断，COM ── NO 通（灯亮）
```

## 关于"光耦隔离"，说句实话

光耦的作用是**信号隔离**：IN 脚和线圈之间没有直连，线圈通断时的电压尖峰到不了单片机引脚。但很多单路模块的 VCC 和线圈供电共用同一路 5V——这种情况下 Arduino 和线圈仍共享地，不是完全电气隔离。追求彻底隔离要用带 **JD-VCC 跳线**的板子：拔掉跳线，给 JD-VCC 单独供一路 5V，VCC 只给光耦输入侧供电（还兼容 3.3V 单片机）。

## 适合 / 不适合

- 适合：水泵、灯带、风扇、电磁阀等"开/关"控制；用低压信号控制 220V 家电（须老师在场监督并做好绝缘）；自动浇花、天黑自动开灯这类开关场景。
- 不适合：PWM 调速（机械触点开关寿命约 10 万次，高频切换会短命，调速请用 MOS 管）；要求静音的场合（咔哒声不可避免）；长时间大电流运行（触点发热）；高速开关（改用固态继电器 SSR）。

## 官方资源

- 继电器模块使用指南（Envistia Mall，含接线/代码/排障）：`https://envistiamall.com/blogs/learn/2-channel-5v-spdt-relay-module-with-optocoupler-user-guide`
- 单路光耦继电器模块规格页（PiShop）：`https://www.pishop.co.za/store/5v-1-channel-level-trigger-optocoupler-relay-module`
