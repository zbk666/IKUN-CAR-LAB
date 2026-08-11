# CAR LAB（应用主目录）

这是 **IKUN · CAR LAB** 上位机的核心应用目录（程序入口 `main.py`）。

- 项目总说明、功能特性、快速开始、通信协议见仓库根目录的 [`../README.md`](../README.md)。
- 版本历史见 [`../CHANGELOG.md`](../CHANGELOG.md)。
- 各版本详细说明与 MCU 通信手册见 [`docs/`](docs/)。

## 从源码运行

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows；macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

启动后在顶部「连接方式」选择 **仿真** 即可无硬件体验全部功能。

## 安全提示

上位机不是唯一安全层。真实车辆 MCU 必须独立实现通信超时停车、输出限幅、异常保护和必要的物理急停。
