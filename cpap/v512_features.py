from __future__ import annotations


_installed = False


def install_v512_features() -> None:
    """Small visual refinements for the 5.1.2 maintenance release.

    5.1.1 already switched the report cover to the real SleepMate logo and
    suppresses the redundant standalone wordmark. 5.1.2 keeps that behaviour
    and only improves the visual hierarchy of the first page: a larger logo,
    a larger report title and tighter spacing between the cover elements.
    """
    global _installed
    if _installed:
        return

    from . import report_pdf

    report_cls = report_pdf.SleepMateReport
    previous_page = report_cls._page
    mm = report_pdf.mm
    page_width, page_height = report_pdf.A4

    def patched_page(self, canvas, doc):
        if int(getattr(doc, "page", 0) or 0) != 1:
            return previous_page(self, canvas, doc)

        original_draw_image = canvas.drawImage
        original_draw_string = canvas.drawString

        def cover_draw_image(image, x, y, width=None, height=None, *args, **kwargs):
            name = str(image or "").replace("\\", "/").lower()
            if name.endswith(("sleepmate-icon-v410.webp", "pwa-512.png", "pwa-192.png")):
                # The logo already contains the SleepMate wordmark, so let it be
                # the main visual anchor of the cover instead of a small icon.
                return original_draw_image(
                    image,
                    18 * mm,
                    page_height - 87 * mm,
                    58 * mm,
                    58 * mm,
                    *args,
                    **kwargs,
                )
            return original_draw_image(image, x, y, width, height, *args, **kwargs)

        def cover_draw_string(x, y, text, *args, **kwargs):
            value = str(text or "")
            if value == "PAP-TERÁPIÁS JELENTÉS":
                canvas.setFont("SleepSansBold", 16)
                return original_draw_string(22 * mm, page_height - 105 * mm, value, *args, **kwargs)

            # Keep the remaining cover copy visually tied to the enlarged title.
            if abs(float(y) - float(page_height - 128 * mm)) < 1.0:
                return original_draw_string(x, page_height - 119 * mm, value, *args, **kwargs)
            if page_height - 162 * mm <= float(y) <= page_height - 146 * mm:
                return original_draw_string(x, float(y) + 10 * mm, value, *args, **kwargs)
            return original_draw_string(x, y, value, *args, **kwargs)

        canvas.drawImage = cover_draw_image
        canvas.drawString = cover_draw_string
        try:
            return previous_page(self, canvas, doc)
        finally:
            canvas.drawImage = original_draw_image
            canvas.drawString = original_draw_string

    report_cls._page = patched_page
    _installed = True
