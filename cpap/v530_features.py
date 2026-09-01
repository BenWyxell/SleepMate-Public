from __future__ import annotations

import urllib.parse


_installed = False


def install_v530_features(app_module) -> None:
    """Layer the v5.3 visual/PWA controller over the proven v5.2.20 shell.

    Root HTML is served here so source runs and packaged builds use the same
    deterministic asset order. Existing v5.2.20 sleep/chart extensions remain
    present exactly as before; v5.3 only adds its own CSS and controller.
    """
    global _installed
    if _installed:
        return

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
                    head_assets.append('<link rel="stylesheet" href="/sleepmate-aurora.css?v=5.3.0">')
                if "sleepmate-v530.css" not in text:
                    head_assets.append('<link rel="stylesheet" href="/sleepmate-v530.css?v=5.3.0">')
                # v5.2.20 already contained preparatory SpO2/HR controls inside
                # the Display panel. With the v5.3 master switch OFF those must
                # disappear too, otherwise O2Ring is still visibly present. The
                # master block itself remains visible so the feature can be enabled.
                if "sm-o2-master-visibility" not in text:
                    head_assets.append(
                        '<style id="sm-o2-master-visibility">'
                        '#page-settings [data-settings-panel="display"]:has(#smO2Enabled:not(:checked))>'
                        ':not(#smO2Master){display:none!important}'
                        'body:has(#smO2Enabled:not(:checked)) .o2ring-report-option{display:none!important}'
                        '</style>'
                    )
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
                    scripts.append('<script src="/sleepmate-v530.js?v=5.3.0"></script>')

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
