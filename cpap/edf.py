from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import struct
from typing import Iterable


@dataclass(frozen=True)
class SignalHeader:
    label: str
    phys_dim: str
    phys_min: float
    phys_max: float
    dig_min: int
    dig_max: int
    samples_per_record: int
    bytes_per_sample: int = 2

    @property
    def scale(self) -> float:
        dr = self.dig_max - self.dig_min
        if dr == 0:
            return 1.0
        return (self.phys_max - self.phys_min) / dr

    @property
    def offset(self) -> float:
        return self.phys_min - self.dig_min * self.scale


@dataclass(frozen=True)
class Annotation:
    onset_s: float
    duration_s: float | None
    description: str


class EDFFile:
    """Small dependency-free EDF/EDF+ reader tailored for ResMed files.

    It intentionally reads the actual number of complete data records present in
    the file instead of blindly trusting the EDF header. This also lets us detect
    incomplete/corrupt copies from a Wi-Fi SD card.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._raw = self.path.read_bytes()
        if len(self._raw) < 256:
            raise ValueError(f"EDF header is truncated: {self.path}")

        self.patient = self._field(8, 80)
        self.recording = self._field(88, 80)
        self.start_time = self._parse_start()
        self.header_bytes = self._int_field(184, 8)
        self.reserved = self._field(192, 44)
        self.header_num_records = self._int_field(236, 8)
        self.record_duration_s = self._float_field(244, 8)
        self.num_signals = self._int_field(252, 4)
        self.signals = self._parse_signal_headers()
        self.record_size_bytes = sum(s.samples_per_record * s.bytes_per_sample for s in self.signals)
        data_bytes = max(0, len(self._raw) - self.header_bytes)
        self.actual_num_records = data_bytes // self.record_size_bytes if self.record_size_bytes else 0
        self.trailing_bytes = data_bytes % self.record_size_bytes if self.record_size_bytes else data_bytes

    def _field(self, offset: int, width: int) -> str:
        return self._raw[offset:offset + width].decode("latin1", "replace").strip(" \x00")

    def _int_field(self, offset: int, width: int) -> int:
        v = self._field(offset, width)
        return int(v or 0)

    def _float_field(self, offset: int, width: int) -> float:
        v = self._field(offset, width)
        return float(v or 0.0)

    def _parse_start(self) -> datetime:
        d = self._field(168, 8)
        t = self._field(176, 8)
        day, month, yy = [int(x) for x in d.split(".")]
        hh, mm, ss = [int(x) for x in t.split(".")]
        year = 1900 + yy if yy >= 85 else 2000 + yy
        return datetime(year, month, day, hh, mm, ss)

    def _parse_signal_headers(self) -> list[SignalHeader]:
        ns = self.num_signals
        if ns <= 0 or ns > 512:
            raise ValueError(f"Invalid EDF signal count {ns}: {self.path}")
        needed = 256 + 256 * ns
        if len(self._raw) < needed:
            raise ValueError(f"EDF signal headers are truncated: {self.path}")

        pos = 256

        def read_array(width: int) -> list[str]:
            nonlocal pos
            out = []
            for _ in range(ns):
                out.append(self._raw[pos:pos + width].decode("latin1", "replace").strip(" \x00"))
                pos += width
            return out

        labels = read_array(16)
        _transducers = read_array(80)
        phys_dims = read_array(8)
        phys_mins = read_array(8)
        phys_maxs = read_array(8)
        dig_mins = read_array(8)
        dig_maxs = read_array(8)
        _prefilters = read_array(80)
        samples = read_array(8)
        reserved = read_array(32)

        signals: list[SignalHeader] = []
        for i in range(ns):
            # WMEDF variants can explicitly mark 8-bit samples with #1.
            bps = 1 if "#1" in reserved[i] else 2
            signals.append(SignalHeader(
                label=labels[i],
                phys_dim=phys_dims[i],
                phys_min=float(phys_mins[i] or 0),
                phys_max=float(phys_maxs[i] or 0),
                dig_min=int(dig_mins[i] or 0),
                dig_max=int(dig_maxs[i] or 0),
                samples_per_record=int(samples[i] or 0),
                bytes_per_sample=bps,
            ))
        return signals

    @property
    def complete(self) -> bool:
        return (
            self.trailing_bytes == 0
            and (self.header_num_records < 0 or self.actual_num_records >= self.header_num_records)
        )

    @property
    def duration_s(self) -> float:
        return self.actual_num_records * self.record_duration_s

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(seconds=self.duration_s)

    def find_signal(self, startswith: str) -> int | None:
        target = startswith.lower()
        for i, sig in enumerate(self.signals):
            if sig.label.lower().startswith(target):
                return i
        return None

    def _signal_offset(self, signal_idx: int) -> int:
        return sum(
            s.samples_per_record * s.bytes_per_sample
            for s in self.signals[:signal_idx]
        )

    def read_signal(self, signal_idx: int) -> list[float]:
        sig = self.signals[signal_idx]
        if sig.label.startswith("EDF Annotations"):
            raise ValueError("Use read_annotations() for EDF annotation signals")

        out: list[float] = []
        sig_offset = self._signal_offset(signal_idx)
        n = sig.samples_per_record
        for rec in range(self.actual_num_records):
            base = self.header_bytes + rec * self.record_size_bytes + sig_offset
            size = n * sig.bytes_per_sample
            chunk = self._raw[base:base + size]
            if len(chunk) != size:
                break
            if sig.bytes_per_sample == 2:
                vals = struct.unpack("<" + "h" * n, chunk)
            else:
                fmt = "B" if sig.dig_min >= 0 else "b"
                vals = struct.unpack("<" + fmt * n, chunk)
            scale, offset = sig.scale, sig.offset
            out.extend(v * scale + offset for v in vals)
        return out

    def read_signal_range(
        self,
        signal_idx: int,
        start_s: float | None = None,
        end_s: float | None = None,
    ) -> tuple[list[float], int]:
        """Decode only the requested time slice of one signal.

        Returns ``(values, first_sample_index)`` where the index is relative to
        the EDF signal start. This avoids decoding an entire night every time the
        browser zooms into a short interval.
        """
        sig = self.signals[signal_idx]
        if sig.label.startswith("EDF Annotations"):
            raise ValueError("Use read_annotations() for EDF annotation signals")
        dt_s = self.signal_sample_interval_s(signal_idx)
        if dt_s <= 0 or sig.samples_per_record <= 0:
            return [], 0

        total_samples = self.actual_num_records * sig.samples_per_record
        first = 0 if start_s is None else max(0, min(total_samples, int(start_s / dt_s)))
        if end_s is None:
            last = total_samples
        else:
            # +1 keeps the point immediately around the selected right edge.
            last = max(0, min(total_samples, int(end_s / dt_s) + 1))
        if last <= first:
            return [], first

        n = sig.samples_per_record
        first_rec = first // n
        last_rec = (last - 1) // n
        sig_offset = self._signal_offset(signal_idx)
        scale, offset = sig.scale, sig.offset
        out: list[float] = []

        for rec in range(first_rec, last_rec + 1):
            base = self.header_bytes + rec * self.record_size_bytes + sig_offset
            size = n * sig.bytes_per_sample
            chunk = self._raw[base:base + size]
            if len(chunk) != size:
                break
            if sig.bytes_per_sample == 2:
                vals = struct.unpack("<" + "h" * n, chunk)
            else:
                fmt = "B" if sig.dig_min >= 0 else "b"
                vals = struct.unpack("<" + fmt * n, chunk)

            abs_a = rec * n
            local_a = max(0, first - abs_a)
            local_z = min(n, last - abs_a)
            if local_z <= local_a:
                continue
            out.extend(vals[i] * scale + offset for i in range(local_a, local_z))

        return out, first

    def signal_sample_interval_s(self, signal_idx: int) -> float:
        sig = self.signals[signal_idx]
        if sig.samples_per_record <= 0 or self.record_duration_s <= 0:
            return 0.0
        return self.record_duration_s / sig.samples_per_record

    def read_annotations(self) -> list[Annotation]:
        idx = next((i for i, s in enumerate(self.signals) if s.label.startswith("EDF Annotations")), None)
        if idx is None:
            return []
        sig = self.signals[idx]
        sig_offset = self._signal_offset(idx)
        bytes_per_record = sig.samples_per_record * sig.bytes_per_sample
        annotations: list[Annotation] = []

        for rec in range(self.actual_num_records):
            base = self.header_bytes + rec * self.record_size_bytes + sig_offset
            block = self._raw[base:base + bytes_per_record]
            if len(block) != bytes_per_record:
                continue
            # EDF+ annotation bytes are stored verbatim in the annotation signal.
            for tal in block.split(b"\x00"):
                if not tal:
                    continue
                try:
                    text = tal.decode("latin1")
                except UnicodeDecodeError:
                    continue
                parts = text.split("\x14")
                if not parts:
                    continue
                timing = parts[0]
                descriptions = [p for p in parts[1:] if p]
                if not descriptions:
                    continue
                duration = None
                if "\x15" in timing:
                    onset_txt, duration_txt = timing.split("\x15", 1)
                    try:
                        duration = float(duration_txt) if duration_txt else None
                    except ValueError:
                        duration = None
                else:
                    onset_txt = timing
                try:
                    onset = float(onset_txt)
                except ValueError:
                    continue
                for desc in descriptions:
                    if desc.strip():
                        annotations.append(Annotation(onset, duration, desc.strip()))
        return annotations
