---
material_id: S-003
card_type: quickstart
title: DHT22 三分钟上手
points:
  - 接线：VCC→5V、GND→GND、DATA→D2，DATA 和 VCC 之间插一个 4.7kΩ 电阻
  - 装库：Arduino IDE 库管理器搜 DHT sensor library（Adafruit）点安装
  - 跑示例：文件→示例→DHT sensor library→DHTtester，打开串口监视器看读数
---

## 第一步：接线（断电操作！）

| DHT22 引脚 | 接到 Arduino Uno |
|---|---|
| VCC（左1） | 5V |
| DATA（左2） | D2，同时经 4.7kΩ 电阻接到 5V |
| NC（左3） | 不接 |
| GND（左4） | GND |

没有 4.7kΩ 电阻？4.7k-10k 之间的都能用（色环：黄-紫-红 是 4.7k）。

## 第二步：装库

Arduino IDE 左侧栏点"库管理器"图标 → 搜索 `DHT sensor library` → 安装 Adafruit 那个（会提示同时安装 Adafruit Unified Sensor，点"全部安装"）。

## 第三步：跑通示例

菜单：文件 → 示例 → DHT sensor library → DHTtester。把代码里的 `DHTPIN` 改成 `2`，`DHTTYPE` 确认是 `DHT22`，上传。工具 → 串口监视器，波特率选 9600，应看到每 2 秒一行温湿度。

## 读数是 NaN 或全是 0？

先查上拉电阻，再查波特率，最后查 DATA 接的是不是代码里写的那个引脚。详见"常见错误"卡片。
