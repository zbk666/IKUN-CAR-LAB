from __future__ import annotations
import math


def response_metrics(samples, target_key="target", actual_key="actual", time_key="t"):
    """Return conservative step-response metrics from a list of dict samples."""
    if len(samples) < 5:
        return {}
    ts = [float(s.get(time_key, i)) for i, s in enumerate(samples)]
    ys = [float(s.get(actual_key, 0.0)) for s in samples]
    rs = [float(s.get(target_key, 0.0)) for s in samples]
    target = rs[-1]
    if abs(target) < 1e-9:
        return {"rmse": math.sqrt(sum((r-y)**2 for r, y in zip(rs, ys))/len(ys))}
    initial = ys[0]
    amp = target - initial
    direction = 1.0 if amp >= 0 else -1.0
    transformed = [(y-initial)*direction for y in ys]
    mag = abs(amp)
    peak = max(transformed)
    overshoot = max(0.0, (peak-mag)/max(mag, 1e-9)*100.0)
    rmse = math.sqrt(sum((r-y)**2 for r, y in zip(rs, ys))/len(ys))
    steady_n = max(3, len(ys)//5)
    steady_error = sum(abs(r-y) for r, y in zip(rs[-steady_n:], ys[-steady_n:]))/steady_n

    def first_cross(level):
        for t, v in zip(ts, transformed):
            if v >= level:
                return t
        return None

    t10 = first_cross(0.1*mag)
    t90 = first_cross(0.9*mag)
    rise = (t90-t10) if t10 is not None and t90 is not None else None
    tol = 0.05*mag
    settling = None
    for i in range(len(ys)):
        if all(abs(rs[j]-ys[j]) <= tol for j in range(i, len(ys))):
            settling = ts[i]-ts[0]
            break
    crossings = sum(1 for a,b in zip(ys,ys[1:]) if (a-target)*(b-target) < 0)
    return {
        "target": target,
        "overshoot_pct": overshoot,
        "rise_time_s": rise,
        "settling_time_s": settling,
        "steady_error": steady_error,
        "rmse": rmse,
        "target_crossings": crossings,
    }


def score_speed_metrics(m):
    if not m:
        return 1e9
    return (
        float(m.get("rmse", 0))*1.0
        + float(m.get("steady_error", 0))*1.2
        + float(m.get("overshoot_pct", 0))*3.0
        + float(m.get("rise_time_s") or 3.0)*20.0
        + float(m.get("settling_time_s") or 4.0)*12.0
        + float(m.get("target_crossings", 0))*8.0
    )
