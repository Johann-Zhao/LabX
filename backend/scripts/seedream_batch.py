# -*- coding: utf-8 -*-
"""批量生成 LabX 演示素材（15 张物料图 + 4 张开屏视觉图），串行 + 间隔防限流。

用法（工作目录 backend/）：
    ./venv/Scripts/python scripts/seedream_batch.py            # 全量
    ./venv/Scripts/python scripts/seedream_batch.py --only B   # 只跑任务B
    ./venv/Scripts/python scripts/seedream_batch.py --only A --force  # 覆盖已存在

产物：deta/images/{materials,intro}/*.png，并复制到 frontend/public/...
"""
import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seedream_gen import generate

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND_DIR)

MAT_STYLE = "电商产品摄影，纯白背景，柔和顶光"
MAT_TAIL = "主体居中完整展示，高清细节，无文字，无水印，无logo"

# 任务 A：15 张物料图（外观描述按实物长相）
MATERIALS = [
    ("A-017", "一块Arduino Uno开发板，蓝色长方形电路板，板边白色排针，银色USB-B方口，黑色圆形DC电源座，中央黑色主芯片"),
    ("A-018", "一块STM32最小系统板，深蓝色窄长条电路板，两侧金色排针，一端micro-USB接口，板上银色晶振与黑色小芯片"),
    ("A-019", "一块51单片机学习板，蓝色大电路板，板载多位数码管、矩阵按键、液晶显示屏与USB接口，教学实验板布局"),
    ("A-023", "一块ESP32-S3开发板，黑色长方形电路板，中央带金属屏蔽罩的无线模块，两侧排针，一端USB-C接口"),
    ("A-024", "一块树莓派4B卡片电脑，绿色电路板，黑色主芯片，四个USB接口与网线接口，侧面40针GPIO排针，micro-HDMI与USB-C电源口"),
    ("A-025", "一块树莓派Pico开发板，绿色窄长条电路板，中央黑色方形主芯片，一端micro-USB接口，两侧锯齿状排针焊盘"),
    ("S-003", "一个DHT22温湿度传感器，白色镂空塑料小方壳，正面栅格开孔，底部四根金属针脚"),
    ("S-007", "一个土壤湿度传感器，红色小电路板通过黑色导线连接叉形金属探头，探头两片叉齿插入式"),
    ("S-009", "一个红外循迹传感器模块，蓝色小电路板，前端一黑一透明两个红外对管探头，板载蓝色电位器与排针"),
    ("M-011", "一块L298N电机驱动模块，红色电路板，中央竖立黑色大散热片，边缘蓝色接线端子排与黄色跳线帽"),
    ("M-013", "一个单路继电器模块，蓝色电路板，中央黑色方块继电器，一侧蓝色接线端子，板载光耦与指示灯"),
    ("T-005", "一套电烙铁工具，黑色隔热手柄电烙铁斜靠在金属烙铁架上，银色金属发热头，旁边黄色清洁海绵"),
    ("H-001", "一块白色长条免焊面包板，板面红蓝电源标识槽线布满插孔，旁边整齐放一束彩色杜邦线"),
    ("E-001", "一个微型潜水泵，白色圆柱形小泵体，顶部出水嘴，底部引出红黑两根电线"),
    ("E-002", "一台热风枪焊台，黑色主机箱带数码管显示屏与调温旋钮，手持热风枪插在侧面支架上"),
]

INTRO_STYLE = "深蓝色科技背景（近黑的藏蓝），荧光青绿色光效，粒子与精密电路线条，高端科技产品发布会视觉风格"
INTRO_TAIL = "无文字，无水印，无logo"

# 任务 B：4 张开屏视觉图
INTROS = [
    ("hero", "多块开发板与传感器如星座般悬浮在深色空间，荧光青光线彼此连接，中央留白"),
    ("scene1", "一只手把一块Arduino开发板交给另一只手，深色背景中荧光青色轮廓勾勒手与电路板，光点随交接流动"),
    ("scene2", "一块开发板上方悬浮着发光的知识卡片与全息面板，半透明荧光界面层层展开，数据流光效"),
    ("scene3", "环形循环构图，电路板、发光灯泡、人群剪影依次排列围成荧光闭环，箭头光流首尾相连回到电路板"),
]

SIZE_MAT = "1024x1024"
SIZE_INTRO = "2048x1152,1152x864,1024x1024"


def dest_for(group, name):
    if group == "A":
        deta = os.path.join(ROOT, "deta", "images", "materials", f"{name}.png")
        pub = os.path.join(ROOT, "frontend", "public", "images", "materials", f"{name}.png")
    else:
        deta = os.path.join(ROOT, "deta", "images", "intro", f"{name}.png")
        pub = os.path.join(ROOT, "frontend", "public", "intro", f"{name}.png")
    return deta, pub


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["A", "B"], default=None)
    ap.add_argument("--force", action="store_true", help="已存在也重新生成")
    ap.add_argument("--ids", default="", help="只跑指定 id，逗号分隔，如 A-017,hero")
    args = ap.parse_args()

    jobs = []
    if args.only in (None, "A"):
        for mid, look in MATERIALS:
            jobs.append(("A", mid, f"{MAT_STYLE}，{look}，{MAT_TAIL}", SIZE_MAT))
    if args.only in (None, "B"):
        for name, scene in INTROS:
            jobs.append(("B", name, f"{INTRO_STYLE}，{scene}，{INTRO_TAIL}", SIZE_INTRO))
    if args.ids:
        wanted = {s.strip() for s in args.ids.split(",") if s.strip()}
        jobs = [j for j in jobs if j[1] in wanted]

    os.makedirs(os.path.join(ROOT, "deta", "images", "materials"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "deta", "images", "intro"), exist_ok=True)

    results = []
    for i, (group, name, prompt, sizes) in enumerate(jobs):
        deta, pub = dest_for(group, name)
        if os.path.exists(deta) and not args.force:
            print(f"[skip] {name} 已存在")
            results.append((name, True, os.path.getsize(deta), "skip"))
        else:
            print(f"[{i + 1}/{len(jobs)}] {group} {name} ...")
            ok, _, nbytes, used_size, note = generate(prompt, deta, sizes)
            tag = f"size={used_size}" if ok else f"FAIL {note[:150]}"
            print(f"  -> {'OK' if ok else 'FAIL'} {name} {nbytes // 1024}KB {tag}")
            results.append((name, ok, nbytes, tag))
            time.sleep(1.5)  # 防限流
        # 同步到 frontend/public（存在即复制，保证两边一致）
        if os.path.exists(deta):
            os.makedirs(os.path.dirname(pub), exist_ok=True)
            shutil.copyfile(deta, pub)

    print("\n==== 汇总 ====")
    fails = [r for r in results if not r[1]]
    for name, ok, nbytes, tag in results:
        print(f"{'OK ' if ok else 'FAIL'} {name:8s} {nbytes // 1024:5d}KB  {tag}")
    print(f"成功 {len(results) - len(fails)}/{len(results)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
