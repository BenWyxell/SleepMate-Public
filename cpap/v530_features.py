from __future__ import annotations

"""Install the v5.3 O2Ring backend feature set.

The browser assets are ordinary, versioned files referenced by ``index.html``.
They deliberately are not rewritten or injected by the HTTP handler: source,
the development server and the frozen Windows package must execute identical
JavaScript bytes in an identical order.
"""


_installed = False
UI_VERSION = "5.3.4"


def install_v530_features(app_module) -> None:
    global _installed
    if _installed:
        return

    from .o2ring_ai import install_o2ring_ai
    from .o2ring_data_management import install_o2ring_data_management
    from .o2ring_diagnostics import install_o2ring_diagnostics
    from .o2ring_restore import install_o2ring_restore
    from .o2ring_runtime_v534 import install_o2ring_runtime_v534
    from .o2ring_v532 import install_o2ring_v532

    install_o2ring_data_management(app_module)
    install_o2ring_ai(app_module)
    install_o2ring_diagnostics(app_module)
    install_o2ring_restore(app_module)
    install_o2ring_v532(app_module)
    install_o2ring_runtime_v534(app_module)
    _installed = True


__all__ = ["install_v530_features", "UI_VERSION"]
