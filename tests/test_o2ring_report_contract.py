from cpap import o2ring_report as report


class FakeService:
    def daily(self, day, max_points=2000):
        assert day == "20260901"
        return {
            "available": True,
            "summary": {
                "spo2_average": 95.4,
                "spo2_minimum": 88,
                "t90_seconds": 32.0,
                "heart_rate_average": 64.5,
                "odi3": 2.1,
                "odi4": 0.8,
                "coverage_percent": 98.5,
            },
            "matches": [{"cpap_coverage_percent": 97.0}],
        }


class FakeReport:
    def __init__(self):
        self.days = ["20260901"]
        self.story = []
        self.styles = {"small": object()}
        self.chart_primary = "primary"
        self.chart_secondary = "secondary"
        self.titles = []
        self.metrics = []
        self.charts = []

    def _title(self, title, subtitle=None):
        self.titles.append((title, subtitle))

    def _metric_cards(self, metrics, columns=3):
        self.metrics.extend(metrics)

    def _chart_title(self, title, subtitle=""):
        self.charts.append((title, subtitle))

    def _line_chart(self, *args, **kwargs):
        return ("chart", args, kwargs)


def test_pdf_oximetry_section_builds_metrics_and_charts(monkeypatch):
    fake = FakeReport()
    monkeypatch.setattr(report, "get_service", lambda: FakeService())
    monkeypatch.setattr(report.rp, "Paragraph", lambda text, style: ("paragraph", text))
    report._oximetry_section(fake)

    assert fake.titles[0][0] == "Oximetria és pulzus"
    labels = [row[0] for row in fake.metrics]
    assert "Átlagos SpO₂" in labels
    assert "Legalacsonyabb SpO₂" in labels
    assert "T90 összesen" in labels
    assert "Átlagpulzus" in labels
    assert "ODI3 / ODI4" in labels
    assert any(title == "SpO₂ trend" for title, _ in fake.charts)
    assert any(title == "Pulzus és T90" for title, _ in fake.charts)
    assert any(item[0] == "paragraph" for item in fake.story if isinstance(item, tuple))
