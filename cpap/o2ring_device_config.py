from __future__ import annotations

import urllib.parse
from typing import Any

from .o2ring_integration import get_service


_installed = False


def _device_update(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    def number(name, low, high):
        if name not in data or data.get(name) in (None, ""):
            return None
        value = int(data[name])
        if value < low or value > high:
            raise ValueError(f"{name}: megengedett tartomány {low}–{high}.")
        return value
    oxi = number("oxi_threshold", 70, 95)
    hr_low = number("hr_low", 20, 200)
    hr_high = number("hr_high", 20, 200)
    motor = number("motor", 1, 100)
    lighting = number("lighting_mode", 0, 2)
    brightness = number("brightness", 0, 2)
    if hr_low is not None and hr_high is not None and hr_low > hr_high:
        raise ValueError("A pulzus alsó határa nem lehet magasabb a felső határnál.")
    if oxi is not None: out.update(SetOxiSwitch="1", SetOxiThr=str(oxi))
    if hr_low is not None or hr_high is not None:
        out["SetHRSwitch"] = "1"
        if hr_low is not None: out["SetHRLowThr"] = str(hr_low)
        if hr_high is not None: out["SetHRHighThr"] = str(hr_high)
    if motor is not None: out["SetMotor"] = str(motor)
    if lighting is not None: out["SetLightingMode"] = str(lighting)
    if brightness is not None: out["SetLightStr"] = str(brightness)
    return out


def install_o2ring_device_config(app_module) -> None:
    global _installed
    if _installed:
        return
    service = get_service(app_module)
    handler_cls = app_module.Handler
    original_post = handler_cls.do_POST

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/o2ring/device-config":
            try:
                cfg = service.settings()
                if not cfg.get("o2ring_enabled"):
                    return self._json({"error": "Az O2Ring integráció nincs bekapcsolva."}, 409)
                update = _device_update(self._read_json_body(max_bytes=50_000))
                if not update:
                    return self._json({"error": "Nincs módosítható készülékbeállítás."}, 400)
                service.manager.queue_device_config(update)
                return self._json({"ok": True, "queued": sorted(update)})
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        return original_post(self)

    handler_cls.do_POST = do_POST
    _installed = True


__all__ = ["install_o2ring_device_config", "_device_update"]
