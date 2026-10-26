"""Conservative selection of a thermal counter scale using lifetime SCOP."""

import math

THERMAL_SCALES = (0.1, 1.0)
REQUIRED_SAMPLES = 3


def matching_thermal_scale(electrical_kwh, thermal_raw, scop):
    """Return a unique scale within 5% of SCOP, or no decision."""
    try:
        electrical_kwh, thermal_raw, scop = map(float, (electrical_kwh, thermal_raw, scop))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (electrical_kwh, thermal_raw, scop)):
        return None
    if electrical_kwh < 10 or thermal_raw <= 0 or not 1 <= scop <= 10:
        return None
    matches = [scale for scale in THERMAL_SCALES
               if abs(thermal_raw * scale / electrical_kwh - scop) / scop <= 0.05]
    return matches[0] if len(matches) == 1 else None


class ThermalScaleSelector:
    """Require consecutive matching polls and freeze the result once chosen."""

    def __init__(self, selected=None):
        self.selected = selected if type(selected) in (int, float) and selected in THERMAL_SCALES else None
        self.candidate = None
        self.samples = 0

    def observe(self, electrical_kwh, thermal_raw, scop):
        if self.selected is not None:
            return self.selected
        candidate = matching_thermal_scale(electrical_kwh, thermal_raw, scop)
        self.samples = self.samples + 1 if candidate is not None and candidate == self.candidate else 1
        self.candidate = candidate
        if candidate is not None and self.samples >= REQUIRED_SAMPLES:
            self.selected = candidate
        return self.selected
