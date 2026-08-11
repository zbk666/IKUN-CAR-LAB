IKUN CAR LAB 开发者说明

当前发布结构：

CAR_LAB\          软件本体
IKUN_Launcher.py  小白启动器源码
build_launcher_windows.bat  Windows EXE 打包脚本
logs\             启动/错误日志

Windows 打包：
1. 在 Windows 打开本目录
2. 双击 build_launcher_windows.bat
3. 生成 release\IKUN_Launcher.exe

发布给普通用户时：
只需要发布：
- release\IKUN_Launcher.exe
- CAR_LAB\ 目录
- logs\ 目录（可为空）

下一阶段可以把 CAR_LAB 本体进一步冻结成内部 runtime，实现完全免 Python。
