from __future__ import annotations

import urllib.parse


_installed = False
UI_VERSION = "5.3.4"


def install_v530_features(app_module) -> None:
    """Install the v5.3.4 frontend shell over the stable SleepMate data core.

    v5.3.4 deliberately removes the layered v5.3.2/v5.3.3 O2 controllers from
    the active shell. The base ``o2ring.js`` is now the single O2 UI owner;
    ``frontend-v534.js`` owns general PWA/settings/cache normalization and is
    registered before the v5.3 navigation bootstrap so Dashboard load wrappers
    are deterministic before O2Ring is dynamically mounted.
    """
    global _installed
    if _installed:
        return

    from .o2ring_data_management import install_o2ring_data_management
    from .o2ring_ai import install_o2ring_ai
    from .o2ring_diagnostics import install_o2ring_diagnostics
    from .o2ring_restore import install_o2ring_restore
    from .o2ring_v532 import install_o2ring_v532
    from .o2ring_runtime_v534 import install_o2ring_runtime_v534

    install_o2ring_data_management(app_module)
    install_o2ring_ai(app_module)
    install_o2ring_diagnostics(app_module)
    install_o2ring_restore(app_module)
    install_o2ring_v532(app_module)
    install_o2ring_runtime_v534(app_module)

    handler_cls = app_module.Handler
    previous_get = handler_cls.do_GET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            try:
                index_path = app_module.WEB / "index.html"
                text = index_path.read_text(encoding="utf-8")
                text = text.replace('/style.css?v=5.0.0', f'/style.css?v={UI_VERSION}')
                text = text.replace('/app.js?v=5.0.0', f'/app.js?v={UI_VERSION}')
                text = text.replace('<strong id="sidebarVersion">v2.7</strong>', f'<strong id="sidebarVersion">v{UI_VERSION}</strong>')
                text = text.replace('<strong id="sidebarVersion">v5.0.0</strong>', f'<strong id="sidebarVersion">v{UI_VERSION}</strong>')

                head_assets: list[str] = []
                if 'name="sleepmate-ui-version"' not in text:
                    head_assets.append(f'<meta name="sleepmate-ui-version" content="{UI_VERSION}">')
                if 'name="sleepmate-o2ring-enabled"' not in text:
                    enabled = bool(app_module.load_config().get("o2ring_enabled", False))
                    head_assets.append(f'<meta name="sleepmate-o2ring-enabled" content="{1 if enabled else 0}">')
                if "sleepmate-aurora.css" not in text:
                    head_assets.append(f'<link rel="stylesheet" href="/sleepmate-aurora.css?v={UI_VERSION}">')
                if "sleepmate-v530.css" not in text:
                    head_assets.append(f'<link rel="stylesheet" href="/sleepmate-v530.css?v={UI_VERSION}">')
                if "o2ring-v534.css" not in text:
                    head_assets.append(f'<link rel="stylesheet" href="/o2ring-v534.css?v={UI_VERSION}">')
                if "sm-o2-master-visibility" not in text:
                    head_assets.append(
                        '<style id="sm-o2-master-visibility">'
                        'body:has(#smO2Enabled:not(:checked)) .o2ring-report-option{display:none!important}'
                        '[data-settings-tab="pwa"]{display:none!important}'
                        '</style>'
                    )

                if head_assets:
                    marker = "</head>"
                    inject = "\n  " + "\n  ".join(head_assets) + "\n"
                    text = text.replace(marker, inject + marker, 1) if marker in text else inject + text

                scripts: list[str] = []
                if "sleepmate-sleep.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep.js?v=5.2.6"></script>')
                if "sleepmate-sleep-v523.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep-v523.js?v=5.2.6"></script>')
                if "sleepmate-chart-v523.js" not in text:
                    scripts.append('<script src="/sleepmate-chart-v523.js?v=5.2.14"></script>')
                if "sleepmate-sleep-v524.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep-v524.js?v=5.2.6"></script>')
                if "sleepmate-sleep-refresh-v5212.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep-refresh-v5212.js?v=5.2.12"></script>')

                # Frontend ownership is established before sleepmate-v530 starts
                # its asynchronous O2 module loader. This guarantees that the
                # Dashboard loading-state wrapper sits directly around the core
                # loader, so the temporary legacy value can never survive across
                # the later O2 network await and reach a painted frame.
                frontend_path = app_module.WEB / "frontend-v534.js"
                if frontend_path.is_file() and "sm-frontend-v534-inline" not in text:
                    feature_js = frontend_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
                    scripts.append(f'<script id="sm-frontend-v534-inline">{feature_js}</script>')

                if "sleepmate-v530.js" not in text:
                    scripts.append(f'<script src="/sleepmate-v530.js?v={UI_VERSION}"></script>')

                data_management_path = app_module.WEB / "o2ring-data-management.js"
                if data_management_path.is_file() and "sm-o2-data-management-inline" not in text:
                    feature_js = data_management_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
                    scripts.append(f'<script id="sm-o2-data-management-inline">{feature_js}</script>')

                # Historical v532/v533 files remain in the source tree for old
                # release reproducibility, but are intentionally not active here.
                if scripts:
                    marker = "</body>"
                    inject = "\n" + "\n".join(scripts) + "\n"
                    text = text.replace(marker, inject + marker, 1) if marker in text else text + inject

                body = text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("X-SleepMate-UI-Version", UI_VERSION)
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception:
                pass
        return previous_get(self)

    handler_cls.do_GET = do_GET
    _installed = True


__all__ = ["install_v530_features", "UI_VERSION"]
