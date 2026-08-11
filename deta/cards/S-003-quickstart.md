---
material_id: S-003
card_type: quickstart
title: DHT22 三分钟上手
points:
  - 接线：VCC→5V、GND→GND、DATA→D2；裸传感器 DATA 与 VCC 之间插 4.7kΩ 上拉电阻（模块版不用）
  - 装库：Arduino IDE 库管理器搜 "DHT sensor library"（Adafruit），连同 Adafruit Unified Sensor 一起装
  - 跑通：DHTtester 示例，串口 9600 每 2 秒一行温湿度；没输出先查上拉电阻和接线
source:
  - https://learn.adafruit.com/dht/using-a-dhtxx-sensor
  - https://learn.adafruit.com/dht
---

## 第一步：接线（断电操作！）

| DHT22 引脚 | 接到 Arduino Uno | 面包板怎么插 |
|---|---|---|
| VCC（左1） | 5V | 跳线从 5V 电源轨接过来 |
| DATA（左2） | D2，同时经 4.7kΩ 电阻接 5V | DATA 所在列 → 电阻 → 5V 电源轨 |
| NC（左3） | 不接 | 空着 |
| GND（左4） | GND | 跳线从 GND 电源轨接过来 |

面包板插法：面包板中间有一条凹槽，把 DHT22 跨凹槽插（每个脚占一列，左右两侧的脚不会短路）；DATA 那一列插一个 4.7kΩ 电阻，另一端插到 5V 电源轨（或经相邻列过渡）。

- 电阻色环：**黄-紫-红-金 = 4.7kΩ**；4.7k~10k 之间都能用
- **模块版（三根线）**：红 VCC→5V、黄/中间 DATA→D2、黑 GND→GND，板载已有上拉电阻，不用再加
- 接完检查两遍再上电：VCC 和 GND 接反会烧传感器

## 第二步：装库

菜单 **Sketch → Include Library → Manage Libraries…**（或左侧栏库管理器图标）→ 搜索框输入 `dht` → 列表里找 **"DHT sensor library" by Adafruit** → 点 **Install**。

会提示需要 **Adafruit Unified Sensor** 库（1.3.0 版起必须），点"全部安装/Install All"一并装上。

## 第三步：跑通示例

1. 菜单 **File → Examples → DHT sensor library → DHTtester**
2. 把代码里 `#define DHTPIN 2` 确认是 `2`；`DHTTYPE` 确认是 `DHT22`（示例默认 DHT22，被注释掉的是 DHT11 那行，别解错注释）
3. 选择板卡型号和串口，点上传
4. 打开串口监视器（**Tools → Serial Monitor**，Ctrl+Shift+M），波特率选 **9600**

**预期输出**（每 2 秒一行）：

```
Humidity: 45.60 %	Temperature: 24.30 *C	Heat index: 24.60 *C
```

**验证方法**（Adafruit 官方推荐）：朝传感器哈一口气（像给眼镜哈气），湿度应明显升高，然后慢慢回落。

不想跑示例？这段完整代码直接粘进新建的 sketch 即可：

```cpp
#include <DHT.h>

#define DHTPIN 2
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  Serial.println("DHT22 test");
  dht.begin();
}

void loop() {
  delay(2000);            // DHT22 最快 0.5Hz，必须等 2 秒
  float h = dht.readHumidity();
  float t = dht.readTemperature();   // 华氏用 dht.readTemperature(true)
  if (isnan(h) || isnan(t)) {
    Serial.println("Failed to read from DHT sensor!");
    return;
  }
  Serial.print("Humidity: ");
  Serial.print(h);
  Serial.print(" %\t");
  Serial.print("Temperature: ");
  Serial.print(t);
  Serial.println(" *C");
}
```

## 没输出？第一查什么

1. **串口监视器波特率**是不是 9600
2. **上拉电阻**在不在（裸传感器九成问题是这个）
3. DATA 实际插的引脚和代码里 `DHTPIN` 是否一致
4. 四根脚是不是从左到右 VCC / DATA / NC / GND（印字朝自己）
5. 5V 和 GND 是否接对、有没有共地

## 下一步

- 读到湿度 → 加阈值判断（如 `< 30%` 视为干）→ 输出高电平给**继电器模块** → 驱动水泵 → **自动浇花**闭环
- 进阶：用 `millis()` 定时读取不阻塞主循环；把数据拼成 JSON 喂给 LabX 后端做知识推送触发
