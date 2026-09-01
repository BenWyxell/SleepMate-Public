from __future__ import annotations

import urllib.parse


_installed = False


def install_v530_features(app_module) -> None:
    """Layer the v5.3+ visual/PWA controller over the proven data core.

    v5.3.3 adds a deterministic frontend recovery controller which owns version
    synchronization, settings deduplication and the dashboard/O2 view state.
    """
    global _installed
    if _installed:
        return

    from .o2ring_data_management import install_o2ring_data_management
    from .o2ring_ai import install_o2ring_ai
    from .o2ring_diagnostics import install_o2ring_diagnostics
    from .o2ring_restore import install_o2ring_restore
    from .o2ring_v532 import install_o2ring_v532

    install_o2ring_data_management(app_module)
    install_o2ring_ai(app_module)
    install_o2ring_diagnostics(app_module)
    install_o2ring_restore(app_module)
    install_o2ring_v532(app_module)

    handler_cls = app_module.Handler
    previous_get = handler_cls.do_GET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            try:
                index_path = app_module.WEB / "index.html"
                text = index_path.read_text(encoding="utf-8")

                head_assets: list[str] = []
                if 'name="sleepmate-ui-version"' not in text:
                    head_assets.append('<meta name="sleepmate-ui-version" content="5.3.3">')
                if "sleepmate-aurora.css" not in text:
                    head_assets.append('<link rel="stylesheet" href="/sleepmate-aurora.css?v=5.3.3">')
                if "sleepmate-v530.css" not in text:
                    head_assets.append('<link rel="stylesheet" href="/sleepmate-v530.css?v=5.3.3">')
                if "sm-o2-master-visibility" not in text:
                    head_assets.append(
                        '<style id="sm-o2-master-visibility">'
                        '#page-settings [data-settings-panel="display"]:has(#smO2Enabled:not(:checked))>'
                        ':not(#smO2Master){display:none!important}'
                        'body:has(#smO2Enabled:not(:checked)) .o2ring-report-option{display:none!important}'
                        '</style>'
                    )

                for filename, element_id in (
                    ("o2ring-v532.css", "sm-o2-v532-inline-css"),
                    ("frontend-v533.css", "sm-frontend-v533-inline-css"),
                ):
                    css_path = app_module.WEB / filename
                    if css_path.is_file() and element_id not in text:
                        css = css_path.read_text(encoding="utf-8").replace("</style", "<\\/style")
                        head_assets.append(f'<style id="{element_id}">{css}</style>')

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
                if "sleepmate-v530.js" not in text:
                    scripts.append('<script src="/sleepmate-v530.js?v=5.3.3"></script>')

                inline_features = (
                    ("o2ring-data-management.js", "sm-o2-data-management-inline"),
                    ("o2ring-v532.js", "sm-o2-v532-inline"),
                    ("frontend-v533.js", "sm-frontend-v533-inline"),
                )
                for filename, element_id in inline_features:
                    feature_path = app_module.WEB / filename
                    if feature_path.is_file() and element_id not in text:
                        feature_js = feature_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
                        scripts.append(f'<script id="{element_id}">{feature_js}</script>')

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
                self.send_header("X-SleepMate-UI-Version", "5.3.3")
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception:
                pass
        return previous_get(self)

    handler_cls.do_GET = do_GET
    _installed = True


__all__ = ["install_v530_features"]
