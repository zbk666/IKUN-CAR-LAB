from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class CornerEvent:
    index: int
    lap_no: int
    direction: str
    enter_time: float
    exit_time: Optional[float]
    enter_speed: float
    min_speed: float
    exit_speed: Optional[float]
    duration: Optional[float]
    max_error: float
    peak_yaw_rate: float
    peak_strength: float

    def to_dict(self) -> dict:
        return asdict(self)


class CornerAnalyzer:
    """Hysteresis + debounce based corner event detector.

    The analyzer is transport-independent. It only consumes telemetry dictionaries.
    The detection source can be yaw rate, track curvature, or auto.
    """

    def __init__(self, config: Optional[dict] = None):
        self.configure(config or {})
        self.reset()

    def configure(self, config: dict) -> None:
        self.cfg = dict(config or {})
        self.source = str(self.cfg.get("source", "yaw_rate")).lower()
        self.yaw_rate_key = str(self.cfg.get("yaw_rate_key", "gyro_z"))
        self.curvature_key = str(self.cfg.get("curvature_key", "curvature"))
        self.speed_key = str(self.cfg.get("speed_key", "speed"))
        self.error_key = str(self.cfg.get("error_key", "tracking_error"))
        self.direction_sign = -1.0 if float(self.cfg.get("direction_sign", 1.0)) < 0 else 1.0

        self.enter_yaw_rate = max(0.0, float(self.cfg.get("enter_yaw_rate", 15.0)))
        self.exit_yaw_rate = max(0.0, float(self.cfg.get("exit_yaw_rate", 8.0)))
        self.enter_curvature = max(0.0, float(self.cfg.get("enter_curvature", 0.08)))
        self.exit_curvature = max(0.0, float(self.cfg.get("exit_curvature", 0.035)))
        self.enter_hold_s = max(0.0, float(self.cfg.get("enter_hold_ms", 100.0)) / 1000.0)
        self.exit_hold_s = max(0.0, float(self.cfg.get("exit_hold_ms", 150.0)) / 1000.0)
        self.direction_change_hold_s = max(0.0, float(self.cfg.get("direction_change_hold_ms", 120.0)) / 1000.0)

        # Make sure the exit threshold is lower than the entry threshold.
        if self.exit_yaw_rate >= self.enter_yaw_rate and self.enter_yaw_rate > 0:
            self.exit_yaw_rate = self.enter_yaw_rate * 0.6
        if self.exit_curvature >= self.enter_curvature and self.enter_curvature > 0:
            self.exit_curvature = self.enter_curvature * 0.45

    def reset(self) -> None:
        self.state = "STRAIGHT"
        self.enter_candidate_at: Optional[float] = None
        self.enter_candidate_data: Optional[dict] = None
        self.enter_candidate_metric: float = 0.0
        self.exit_candidate_at: Optional[float] = None
        self.exit_candidate_data: Optional[dict] = None
        self.turn_candidate_at: Optional[float] = None
        self.turn_candidate_sign = 0
        self.current: Optional[CornerEvent] = None
        self.events: List[CornerEvent] = []
        self.enter_count = 0
        self.exit_count = 0
        self.left_count = 0
        self.right_count = 0

    def _metric(self, data: dict):
        yaw = self._num(data.get(self.yaw_rate_key))
        curvature = self._num(data.get(self.curvature_key))

        if self.source in ("curvature", "curve"):
            return curvature, self.enter_curvature, self.exit_curvature, "curvature"
        if self.source in ("yaw_rate", "gyro", "gyro_z"):
            return yaw, self.enter_yaw_rate, self.exit_yaw_rate, "yaw_rate"

        # auto: prefer a meaningful curvature field when present, otherwise yaw rate.
        if self.curvature_key in data and curvature is not None:
            return curvature, self.enter_curvature, self.exit_curvature, "curvature"
        return yaw, self.enter_yaw_rate, self.exit_yaw_rate, "yaw_rate"

    @staticmethod
    def _num(value) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _sign(value: float) -> int:
        return 1 if value > 0 else (-1 if value < 0 else 0)

    def _direction(self, signed_metric: float) -> str:
        sign = self._sign(signed_metric * self.direction_sign)
        return "左弯" if sign >= 0 else "右弯"

    def _start_corner(self, data: dict, now: float, lap_no: int, signed_metric: float, strength: float) -> dict:
        speed = self._num(data.get(self.speed_key)) or 0.0
        err = abs(self._num(data.get(self.error_key)) or 0.0)
        yaw = abs(self._num(data.get(self.yaw_rate_key)) or 0.0)
        self.enter_count += 1
        direction = self._direction(signed_metric)
        if direction == "左弯":
            self.left_count += 1
        else:
            self.right_count += 1
        self.current = CornerEvent(
            index=self.enter_count,
            lap_no=int(lap_no),
            direction=direction,
            enter_time=float(now),
            exit_time=None,
            enter_speed=speed,
            min_speed=speed,
            exit_speed=None,
            duration=None,
            max_error=err,
            peak_yaw_rate=yaw,
            peak_strength=abs(strength),
        )
        self.state = "CORNER"
        self.enter_candidate_at = None
        self.enter_candidate_data = None
        self.enter_candidate_metric = 0.0
        self.exit_candidate_at = None
        self.exit_candidate_data = None
        self.turn_candidate_at = None
        self.turn_candidate_sign = 0
        return {"type": "enter", "corner": self.current.to_dict()}

    def _update_current(self, data: dict, strength: float) -> None:
        if self.current is None:
            return
        speed = self._num(data.get(self.speed_key))
        if speed is not None:
            self.current.min_speed = min(self.current.min_speed, speed)
        err = abs(self._num(data.get(self.error_key)) or 0.0)
        self.current.max_error = max(self.current.max_error, err)
        yaw = abs(self._num(data.get(self.yaw_rate_key)) or 0.0)
        self.current.peak_yaw_rate = max(self.current.peak_yaw_rate, yaw)
        self.current.peak_strength = max(self.current.peak_strength, abs(strength))

    def _finish_corner(self, data: dict, now: float) -> Optional[dict]:
        if self.current is None:
            self.state = "STRAIGHT"
            return None
        speed = self._num(data.get(self.speed_key)) or 0.0
        self.current.exit_time = float(now)
        self.current.exit_speed = speed
        self.current.duration = max(0.0, self.current.exit_time - self.current.enter_time)
        finished = self.current
        self.events.append(finished)
        self.exit_count += 1
        self.current = None
        self.state = "STRAIGHT"
        self.enter_candidate_at = None
        self.enter_candidate_data = None
        self.enter_candidate_metric = 0.0
        self.exit_candidate_at = None
        self.exit_candidate_data = None
        self.turn_candidate_at = None
        self.turn_candidate_sign = 0
        return {"type": "exit", "corner": finished.to_dict()}

    def update(self, data: dict, now: float, lap_no: int = 1) -> List[dict]:
        emitted: List[dict] = []
        metric, enter_thr, exit_thr, source_name = self._metric(data)
        if metric is None or enter_thr <= 0:
            return emitted

        strength = float(metric)
        abs_strength = abs(strength)
        current_sign = self._sign(strength * self.direction_sign)

        if self.state == "STRAIGHT":
            if abs_strength >= enter_thr:
                if self.enter_candidate_at is None:
                    self.enter_candidate_at = now
                    self.enter_candidate_data = dict(data)
                    self.enter_candidate_metric = strength
                if now - self.enter_candidate_at >= self.enter_hold_s:
                    start_data = self.enter_candidate_data or data
                    emitted.append(self._start_corner(start_data, self.enter_candidate_at, lap_no, self.enter_candidate_metric, self.enter_candidate_metric))
            else:
                self.enter_candidate_at = None
                self.enter_candidate_data = None
                self.enter_candidate_metric = 0.0
            return emitted

        self._update_current(data, strength)

        # S-bend support: if the turn direction reverses strongly without a true straight,
        # close the old corner and open a new one after a short confirmation period.
        active_sign = 0
        if self.current is not None:
            active_sign = 1 if self.current.direction == "左弯" else -1
        if abs_strength >= enter_thr and current_sign and active_sign and current_sign != active_sign:
            if self.turn_candidate_sign != current_sign:
                self.turn_candidate_sign = current_sign
                self.turn_candidate_at = now
            elif self.turn_candidate_at is not None and now - self.turn_candidate_at >= self.direction_change_hold_s:
                boundary_time = self.turn_candidate_at
                out = self._finish_corner(data, boundary_time)
                if out:
                    emitted.append(out)
                emitted.append(self._start_corner(data, boundary_time, lap_no, strength, strength))
                return emitted
        else:
            self.turn_candidate_at = None
            self.turn_candidate_sign = 0

        if abs_strength <= exit_thr:
            if self.exit_candidate_at is None:
                self.exit_candidate_at = now
                self.exit_candidate_data = dict(data)
            if now - self.exit_candidate_at >= self.exit_hold_s:
                exit_data = self.exit_candidate_data or data
                out = self._finish_corner(exit_data, self.exit_candidate_at)
                if out:
                    emitted.append(out)
        else:
            self.exit_candidate_at = None
            self.exit_candidate_data = None

        return emitted

    def counts(self) -> Dict[str, int]:
        return {
            "enter": self.enter_count,
            "exit": self.exit_count,
            "left": self.left_count,
            "right": self.right_count,
            "completed": len(self.events),
        }

    def active_corner(self) -> Optional[dict]:
        return self.current.to_dict() if self.current else None
