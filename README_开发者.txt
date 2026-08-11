IKUN CAR LAB · 开发者速查卡
（完整开发/贡献说明见 README.md 与 CONTRIBUTING.md）

发布结构：
  CAR_LAB\                    软件本体（入口 CAR_LAB\main.py）
  IKUN_Launcher.py            小白启动器源码
  build_launcher_windows.bat  Windows EXE 打包脚本
  logs\                       启动/错误日志

从源码运行（开发）：
  cd CAR_LAB
  python -m venv .venv
  .venv\Scripts\activate          （macOS/Linux: source .venv/bin/activate）
  pip install -r requirements.txt
  python main.py

Windows 打包 EXE：
  双击 build_launcher_windows.bat  →  生成 release\IKUN_Launcher.exe

发布给普通用户时只需：
  release\IKUN_Launcher.exe + CAR_LAB\ 目录 + logs\（可为空）

新增车型 / 提交贡献：
  见 CONTRIBUTING.md（vehicles\<name>\config.yaml，加一个文件夹即一个车型）。

下一阶段：把 CAR_LAB 本体冻结成内部 runtime，实现完全免 Python。
