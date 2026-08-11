---
material_id: A-024
card_type: quickstart
title: Raspberry Pi 4B 三分钟上手（无头模式 + GPIO 点亮 LED）
points:
  - 系统用官方 Raspberry Pi Imager 烧进 microSD 卡，烧录时可顺手预配置 Wi-Fi、SSH 和用户名密码
  - 不用显示器键盘：插卡上电后用 SSH 远程登录，Windows 自带的 ssh 命令就能连
  - 点亮 LED 用系统自带的 gpiozero 库：LED 长脚接 GPIO17（物理 11），经 330Ω 电阻接 GND
source:
  - https://www.raspberrypi.com/documentation/computers/getting-started.html
  - https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/
---

## 需要准备

| 东西 | 说明 |
|---|---|
| microSD 卡 | 至少 8GB（官方建议 Raspberry Pi OS Lite 8GB、桌面版 32GB 起步） |
| 读卡器 | 把卡插到电脑上烧系统 |
| Raspberry Pi Imager | 官方烧录工具，https://www.raspberrypi.com/software/ 下载（Windows/Mac/Linux 都有） |
| 电源 | 5V/3A USB-C（官方 15W 电源最佳） |
| 电脑 + 网络 | 与 Pi 连同一个 Wi-Fi 或插网线；Windows 10/11 自带 ssh 客户端 |

## 第一步：用 Imager 烧系统（预配置 SSH / Wi-Fi / 账号）

1. 电脑上装好并打开 Raspberry Pi Imager。
2. 依次选择：**设备** → Raspberry Pi 4 → **操作系统** → Raspberry Pi OS（新手选带桌面的版本，或选 Lite 更省资源）→ **存储卡** → 选你的 microSD。
3. 点右下角"齿轮"（或下一步里的设置按钮），打开高级选项并填好：
   - 勾选"启用 SSH"（无头模式必选！）
   - 设置用户名和密码
   - 勾选"配置无线局域网"，填实验室 Wi-Fi 的 SSID 和密码（没 Wi-Fi 就用网线，无需此项）
4. 点"写入"，等进度条走完，**拔出读卡器**。

## 第二步：插卡上电，等它开机

microSD 卡**标签面朝外**插入 Pi 板底的卡槽，接好网线（可选），最后插 USB-C 电源。Pi 通电即开机：红灯（电源）常亮，绿灯开始闪烁。首次启动 1~3 分钟，耐心等。

## 第三步：SSH 登录（Windows 打开 PowerShell 或 CMD）

```bash
ssh 用户名@树莓派IP
```

不知道 IP 就去路由器管理页面找主机名对应的 IP（Imager 设置里可自定义主机名），或手机开热点看连接设备列表。第一次连接提示确认指纹输 `yes`，然后输密码，看到 `$` 提示符就成功了：

```bash
$ uname -a     # 应显示 Linux ... aarch64
```

## 第四步：接线（断电操作！）

| LED 引脚 | 接到 Pi 的 |
|---|---|
| 长脚（阳极） | 物理引脚 11（GPIO17） |
| 短脚（阴极） | 串联 330Ω 电阻后接物理引脚 6（GND） |

面包板或杜邦线都行，正负极别接反，电阻不能省（GPIO 直接驱动 LED 会过流）。

## 第五步：写第一个程序点亮 LED

`gpiozero` 是树莓派官方维护的 GPIO 库，Raspberry Pi OS 自带，无需安装。SSH 里执行：

```bash
mkdir -p ~/labx && cd ~/labx && nano blink.py
```

粘贴代码，Ctrl+O 回车保存，Ctrl+X 退出：

```python
from gpiozero import LED
from time import sleep

led = LED(17)      # GPIO17 = 物理引脚 11
while True:
    led.on()
    sleep(1)
    led.off()
    sleep(1)
```

运行：

```bash
python3 blink.py
```

## 预期现象

LED 以 1 秒间隔稳定闪烁。Ctrl+C 退出程序。把 `sleep` 数字改小再跑，闪烁变快——GPIO 控制成功。

## 失败第一查

绿灯完全不亮 / 反复重启 → **供电问题**，换官方 5V 3A 电源；SSH 连不上 → 确认 Imager 设置里勾了"启用 SSH"、Wi-Fi 密码对、电脑和 Pi 在同一网络。详见"常见错误"卡片。

## 下一步学什么

- 官方 GPIO 文档（gpiozero 更多玩法：按键、舵机、传感器）：https://www.raspberrypi.com/documentation/computers/raspberry-pi.html
- 接摄像头跑 OpenCV 视觉项目（本空间视觉/AI 项目的基础）
- 装 Docker 跑服务、把 Pi 当小服务器
- 官方入门教程站：https://www.raspberrypi.com/tutorials/
