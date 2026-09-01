from __future__ import annotations

import urllib.parse


_installed = False


def install_v530_features(app_module) -> None:
    """Layer the v5.3+ visual/PWA controller over the proven v5.2.20 shell.

    v5.3.2 keeps the stable launcher/data core while replacing the interval-heavy
    post-5.3.0 O2 polish with one deterministic, idempotent runtime layer.
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
                if "sleepmate-aurora.css" not in text:
                    head_assets.append('<link rel="stylesheet" href="/sleepmate-aurora.css?v=5.3.2">')
                if "sleepmate-v530.css" not in text:
                    head_assets.append('<link rel="stylesheet" href="/sleepmate-v530.css?v=5.3.2">')
                if "sm-o2-master-visibility" not in text:
                    head_assets.append(
                        '<style id="sm-o2-master-visibility">'
                        '#page-settings [data-settings-panel="display"]:has(#smO2Enabled:not(:checked))>'
                        ':not(#smO2Master){display:none!important}'
                        'body:has(#smO2Enabled:not(:checked)) .o2ring-report-option{display:none!important}'
                        '</style>'
                    )

                # v5.3.2 is intentionally the only active post-release O2 polish.
                # It is embedded into the no-cache HTML shell, so PWA and desktop
                # receive the same code without waiting on stale cache entries.
                polish_css_path = app_module.WEB / "o2ring-v532.css"
                if polish_css_path.is_file() and "sm-o2-v532-inline-css" not in text:
                    polish_css = polish_css_path.read_text(encoding="utf-8").replace("</style", "<\\/style")
                    head_assets.append(f'<style id="sm-o2-v532-inline-css">{polish_css}</style>')

                if head_assets:
                    marker = "</head>"
                    inject = "\n  " + "\n  ".join(head_assets) + "\n"
                    text = text.replace(marker, inject + marker, 1) if marker in text else inject + text

                scripts: list[str] = []
                # Preserve every v5.2.20 shell extension normally injected by
                # sleep_analysis_v522._install_shell_loader.
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
                    scripts.append('<script src="/sleepmate-v530.js?v=5.3.2"></script>')

                inline_features = (
                    ("o2ring-data-management.js", "sm-o2-data-management-inline"),
                    ("o2ring-v532.js", "sm-o2-v532-inline"),
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
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception:
                pass
        return previous_get(self)

    handler_cls.do_GET = do_GET
    _installed = True


__all__ = ["install_v530_features"]
