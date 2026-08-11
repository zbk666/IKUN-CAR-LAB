from bisect import bisect_left
import pyqtgraph as pg
from PySide6.QtCore import Qt


class CurveInspector:
    """Reusable oscilloscope cursor: hover snap + A/B measurement."""

    def __init__(self, plot_widget, data_provider, on_hover=None, on_ab=None, show_overlay=True):
        self.plot = plot_widget
        self.data_provider = data_provider
        self.on_hover = on_hover
        self.on_ab = on_ab
        self.show_overlay = show_overlay

        pen_hover = pg.mkPen((116, 192, 252, 190), width=1)
        self.hover_v = pg.InfiniteLine(angle=90, movable=False, pen=pen_hover)
        self.hover_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen((116, 192, 252, 90), width=1))
        self.hover_v.setZValue(1000)
        self.hover_h.setZValue(1000)
        self.plot.addItem(self.hover_v, ignoreBounds=True)
        self.plot.addItem(self.hover_h, ignoreBounds=True)
        self.hover_v.hide(); self.hover_h.hide()

        self.text = pg.TextItem(anchor=(0, 1), fill=pg.mkBrush(18, 24, 33, 225), border=pg.mkPen(70, 86, 105))
        self.text.setZValue(1001)
        # Overlay items must never participate in PlotItem auto-range.
        # Otherwise moving the mouse can make pyqtgraph recalculate the view
        # from the pixel-sized TextItem and the visible curves appear to shrink.
        self.plot.addItem(self.text, ignoreBounds=True)
        self.text.hide()

        self.a_line = pg.InfiniteLine(angle=90, movable=False, label="A", pen=pg.mkPen((255, 202, 58), width=2))
        self.b_line = pg.InfiniteLine(angle=90, movable=False, label="B", pen=pg.mkPen((255, 121, 198), width=2))
        self.a_line.setZValue(999); self.b_line.setZValue(999)
        self.plot.addItem(self.a_line, ignoreBounds=True); self.plot.addItem(self.b_line, ignoreBounds=True)
        self.a_line.hide(); self.b_line.hide()
        self.a = None; self.b = None

        self.proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved, rateLimit=60, slot=self._moved)
        self.plot.scene().sigMouseClicked.connect(self._clicked)

    def reset_ab(self):
        self.a = None; self.b = None
        self.a_line.hide(); self.b_line.hide()
        if self.on_ab:
            self.on_ab(None, None, None)

    def _snapshot(self, scene_pos):
        if not self.plot.sceneBoundingRect().contains(scene_pos):
            return None
        x_values, series = self.data_provider()
        x_values = list(x_values)
        if not x_values:
            return None
        mouse = self.plot.plotItem.vb.mapSceneToView(scene_pos)
        x = float(mouse.x())
        idx = bisect_left(x_values, x)
        if idx <= 0:
            idx = 0
        elif idx >= len(x_values):
            idx = len(x_values) - 1
        elif abs(x_values[idx - 1] - x) <= abs(x_values[idx] - x):
            idx -= 1
        vals = {}
        for name, values in series.items():
            ys = list(values)
            offset = len(x_values) - len(ys)
            yi = idx - offset
            if 0 <= yi < len(ys):
                try:
                    vals[str(name)] = float(ys[yi])
                except Exception:
                    pass
        return {"i": idx, "x": float(x_values[idx]), "values": vals}

    def _moved(self, evt):
        pos = evt[0] if isinstance(evt, (tuple, list)) else evt
        snap = self._snapshot(pos)
        if snap is None:
            self.hover_v.hide(); self.hover_h.hide(); self.text.hide()
            if self.on_hover:
                self.on_hover(None)
            return
        self.hover_v.setPos(snap["x"]); self.hover_v.show()
        first_y = next(iter(snap["values"].values()), None)
        if first_y is not None:
            self.hover_h.setPos(first_y); self.hover_h.show()
        else:
            self.hover_h.hide()

        if self.show_overlay:
            lines = [f"t = {snap['x']:.4f} s"]
            lines.extend(f"{name}: {value:.4f}" for name, value in snap["values"].items())
            self.text.setText("\n".join(lines))
            yr = self.plot.plotItem.vb.viewRange()[1]
            self.text.setPos(snap["x"], yr[1]); self.text.show()
        else:
            self.text.hide()
        if self.on_hover:
            self.on_hover(snap)

    def _clicked(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        snap = self._snapshot(event.scenePos())
        if snap is None:
            return
        if self.a is None or self.b is not None:
            self.a = snap; self.b = None
            self.a_line.setPos(snap["x"]); self.a_line.show(); self.b_line.hide()
        else:
            self.b = snap
            self.b_line.setPos(snap["x"]); self.b_line.show()
        self._notify_ab()

    def _notify_ab(self):
        if not self.on_ab:
            return
        if not self.a or not self.b:
            self.on_ab(self.a, self.b, None)
            return
        dt = self.b["x"] - self.a["x"]
        common = [k for k in self.a["values"] if k in self.b["values"]]
        delta = {"dt": dt, "values": {k: self.b["values"][k] - self.a["values"][k] for k in common}}
        self.on_ab(self.a, self.b, delta)
