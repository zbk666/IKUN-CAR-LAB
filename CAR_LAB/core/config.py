from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
VEHICLES = ROOT / "vehicles"


def _vehicle_order(path):
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return (int(cfg.get("vehicle", {}).get("order", 999)), str(cfg.get("vehicle", {}).get("display_name", path.stem)))
    except Exception:
        return (999, Path(path).stem)


def list_vehicle_files():
    """列出所有车型配置。

    同时支持两种布局，方便车型插件化：
    - 旧：``vehicles/<name>.yaml``（扁平文件，保持向后兼容）
    - 新：``vehicles/<name>/config.yaml``（每个车型一个文件夹，别人只需加一个目录）
    """
    flat = list(VEHICLES.glob("*.yaml"))
    plugins = list(VEHICLES.glob("*/config.yaml"))
    return sorted(flat + plugins, key=_vehicle_order)


def load_vehicle_config(path=None):
    if path is None:
        files = list_vehicle_files()
        if not files:
            raise FileNotFoundError("vehicles 目录中没有 YAML 车型配置")
        path = files[0]
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["_path"] = str(path)
    return cfg


def validate_vehicle_config(cfg):
    issues = []
    params = cfg.get("parameters", []) or []
    defined = {}
    for i, item in enumerate(params):
        key = str(item.get("key", "")).strip()
        if not key:
            issues.append({"severity":"error","message":f"parameters[{i}] 缺少 key"})
            continue
        if key in defined:
            issues.append({"severity":"error","message":f"参数 key 重复：{key}"})
        defined[key] = item

    refs = []
    speed = cfg.get("speed_lab", {}) or {}
    refs.extend(("Speed Lab", str(v)) for v in (speed.get("params", {}) or {}).values())
    heading = cfg.get("heading_lab", {}) or {}
    for group in ("outer_params","inner_params"):
        refs.extend((f"Heading Lab/{group}", str(v)) for v in (heading.get(group,{}) or {}).values())
    custom = cfg.get("custom_loop", {}) or {}
    for k in ("kp_key","ki_key","kd_key"):
        if custom.get(k):
            refs.append(("Custom Loop", str(custom[k])))
    motion = cfg.get("chassis_motion", {}) or {}
    for axis in (motion.get("axes", []) or []):
        name = str(axis.get("label", axis.get("key", "轴")))
        refs.extend((f"底盘运动/{name}", str(v)) for v in (axis.get("params", {}) or {}).values())

    for where, key in refs:
        if key not in defined:
            issues.append({"severity":"warning","message":f"{where} 引用了未定义参数：{key}"})

    telemetry = {str(x.get("key","")).strip() for x in (cfg.get("telemetry",[]) or []) if x.get("key")}
    for key in sorted(set(defined) & telemetry):
        issues.append({"severity":"error","message":f"参数 key 与遥测 key 冲突：{key}"})

    controls = {str(x.get("key","")).strip() for x in (cfg.get("controls",[]) or []) if x.get("key")}
    for key in sorted(set(defined) & controls):
        issues.append({"severity":"warning","message":f"参数 key 与控制 key 重名：{key}"})

    command_keys = {
        str(speed.get("target_command_key","")).strip(),
        str(heading.get("target_command_key","")).strip(),
    }
    command_keys.discard("")
    for key in sorted(set(defined) & command_keys):
        issues.append({"severity":"warning","message":f"参数 key 与环目标 CMD key 重名：{key}"})

    for motor in (cfg.get("chassis_debug",{}) or {}).get("motors",[]) or []:
        prefix=str(motor.get("pid_prefix","")).strip()
        if prefix:
            for suffix in ("kp","ki","kd"):
                key=f"{prefix}_{suffix}"
                if key not in defined:
                    issues.append({"severity":"info","message":f"电机 PID 参数未定义：{key}"})
    return issues
