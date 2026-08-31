from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


PROMPT_VERSION = 1
FORBIDDEN_KEYS = {
    "name", "full_name", "first_name", "last_name", "email", "phone", "address",
    "taj", "ssn", "birth_date", "birth_place", "serial_number", "device_serial",
    "username", "windows_user", "ip", "mac", "ssid", "patient_id", "doctor_name",
    "institution", "source", "file", "path", "notes", "note",
}


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        d = datetime.strptime(dob, "%Y-%m-%d").date()
    except Exception:
        return None
    t = date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def _compact(obj: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if v not in (None, "", [], {})}


def _safe_stat_rows(stats: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for r in stats.get("rows") or []:
        if not isinstance(r, dict):
            continue
        key = str(r.get("key") or "")
        if key not in {"pressure", "epr_pressure", "mask_pressure", "leak", "flow_lim", "snore", "resp_rate", "tidal_volume", "minute_vent"}:
            continue
        out[key] = _compact({
            "unit": r.get("unit"), "min": r.get("min"), "median": r.get("median"),
            "p95": r.get("p95"), "p995": r.get("p995"), "max": r.get("max"),
        })
    return out


def _safe_profile(patient: dict[str, Any]) -> dict[str, Any]:
    profile = patient.get("profile") if isinstance(patient.get("profile"), dict) else {}
    diagnoses = patient.get("diagnoses") or []
    latest_diag = sorted((x for x in diagnoses if isinstance(x, dict)), key=lambda x: str(x.get("date") or ""), reverse=True)
    diag = latest_diag[0] if latest_diag else {}
    age = _age(profile.get("birth_date"))
    return _compact({
        "age_years": age,
        "therapy_start_date": profile.get("therapy_start_date"),
        "baseline": _compact({
            "diagnosis_type": diag.get("diagnosis_type"),
            "ahi": diag.get("ahi"), "odi": diag.get("odi"),
            "spo2_min": diag.get("spo2_min"), "spo2_avg": diag.get("spo2_avg"),
        }),
    })


def _safe_prescriptions(patient: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for r in patient.get("prescriptions") or []:
        if not isinstance(r, dict):
            continue
        rows.append(_compact({
            "effective_from": r.get("effective_from"), "effective_to": r.get("effective_to"),
            "mode": r.get("mode"), "fixed_pressure": r.get("fixed_pressure"),
            "min_pressure": r.get("min_pressure"), "max_pressure": r.get("max_pressure"),
        }))
    return sorted(rows, key=lambda x: str(x.get("effective_from") or ""))


def _safe_equipment(patient: dict[str, Any], dataset) -> dict[str, Any]:
    devices = {str(x.get("id")): x for x in patient.get("devices") or [] if isinstance(x, dict)}
    masks = {str(x.get("id")): x for x in patient.get("masks") or [] if isinstance(x, dict)}
    accessories = {str(x.get("id")): x for x in patient.get("accessories") or [] if isinstance(x, dict)}
    setups = []
    for s in patient.get("setups") or []:
        if not isinstance(s, dict):
            continue
        d = devices.get(str(s.get("device_id"))) or {}
        m = masks.get(str(s.get("mask_id"))) or {}
        acc = []
        for aid in s.get("accessory_ids") or []:
            a = accessories.get(str(aid)) or {}
            if a:
                acc.append(_compact({"category": a.get("category"), "manufacturer": a.get("manufacturer"), "model": a.get("model")}))
        setups.append(_compact({
            "start_date": s.get("start_date"), "end_date": s.get("end_date"), "active": bool(s.get("active")),
            "device": _compact({"manufacturer": d.get("manufacturer"), "model": d.get("model")}),
            "mask": _compact({"manufacturer": m.get("manufacturer"), "model": m.get("model"), "category": m.get("mask_type"), "size": m.get("size")}),
            "accessories": acc,
        }))
    detected = dataset.equipment()
    detected_safe = {}
    if detected.get("available"):
        detected_safe = _compact({"manufacturer": detected.get("manufacturer"), "model": detected.get("product_name")})
    return _compact({"detected_device": detected_safe, "setups": sorted(setups, key=lambda x: str(x.get("start_date") or ""))})


def _choose_days(dataset, analysis_type: str, month: str = "") -> list[str]:
    newest_first = dataset.days()
    if not newest_first:
        return []
    if analysis_type == "night":
        return newest_first[:1]
    if analysis_type == "week":
        return newest_first[:7]
    if analysis_type == "month":
        prefix = month.replace("-", "")
        return [d for d in newest_first if d.startswith(prefix)]
    if analysis_type == "full_period":
        return newest_first
    raise ValueError("Ismeretlen AI kiértékelési mód.")


def build_safe_payload(dataset, patient_store, analysis_type: str, month: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    chosen = _choose_days(dataset, analysis_type, month)
    if not chosen:
        raise ValueError("Ehhez a kiértékeléshez nincs rendelkezésre álló terápiás adat.")
    patient = patient_store.all_data()
    chronological = list(reversed(chosen))
    day_rows = []
    include_event_detail = len(chosen) <= 31
    for day in chronological:
        sm = dataset.summary(day)
        st = dataset.statistics(day)
        counts = sm.get("counts") or {}
        sessions = []
        for s in sm.get("sessions") or []:
            sessions.append(_compact({
                "start": s.get("start"), "end": s.get("end"), "duration_seconds": s.get("duration_s")
            }))
        row = _compact({
            "date": sm.get("date"),
            "usage_seconds": sm.get("therapy_seconds"),
            "session_count": len(sessions),
            "sessions": sessions,
            "ahi": sm.get("ahi"),
            "events_count": _compact({k: int(counts.get(k) or 0) for k in ("OA", "CA", "H", "UA", "RERA", "CSR")}),
            "statistics": _safe_stat_rows(st),
            "apnea_seconds": st.get("apnea_seconds"),
            "oximetry": (sm.get("oximetry") if (sm.get("oximetry") or {}).get("available") else None),
        })
        if include_event_detail:
            row["events"] = [
                _compact({"time": e.get("time"), "duration_seconds": e.get("duration_s"), "type": e.get("type")})
                for e in sm.get("events") or []
                if e.get("type") in {"OA", "CA", "H", "UA", "RERA", "CSR"}
            ]
        day_rows.append(row)

    therapy_start = day_rows[0].get("date") if day_rows else None
    period_end = day_rows[-1].get("date") if day_rows else None
    total_s = sum(float(x.get("usage_seconds") or 0) for x in day_rows)
    total_ahi_events = sum(sum(int(v or 0) for k, v in (x.get("events_count") or {}).items() if k in {"OA", "CA", "H", "UA"}) for x in day_rows)
    weighted_ahi = total_ahi_events / (total_s / 3600.0) if total_s else None
    payload = {
        "schema": "cpap-ai-safe-payload-v1",
        "analysis_type": analysis_type,
        "period": {"start": therapy_start, "end": period_end, "therapy_days": len(day_rows)},
        "anonymous_profile": _safe_profile(patient),
        "therapy_prescriptions": _safe_prescriptions(patient),
        "equipment_history": _safe_equipment(patient, dataset),
        "aggregate": _compact({
            "therapy_days": len(day_rows), "total_usage_seconds": round(total_s, 3),
            "weighted_ahi": round(weighted_ahi, 3) if weighted_ahi is not None else None,
        }),
        "days": day_rows,
    }
    validate_safe_payload(payload)
    meta = {"period_start": therapy_start, "period_end": period_end, "therapy_days": len(day_rows), "session_count": sum(int(x.get("session_count") or 0) for x in day_rows)}
    return payload, meta


def build_comparison_payload(dataset, patient_store, comparison: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    a_start = str(comparison.get("a_start") or "")
    a_end = str(comparison.get("a_end") or "")
    b_start = str(comparison.get("b_start") or "")
    b_end = str(comparison.get("b_end") or "")
    result = dataset.compare_periods(a_start, a_end, b_start, b_end)
    if not result.get("period_a", {}).get("days") or not result.get("period_b", {}).get("days"):
        raise ValueError("Mindkét összehasonlítási időszakhoz szükség van legalább egy terápiás napra.")
    patient = patient_store.all_data()
    payload = {
        "schema": "cpap-ai-safe-payload-v1",
        "analysis_type": "comparison",
        "anonymous_profile": _safe_profile(patient),
        "therapy_prescriptions": _safe_prescriptions(patient),
        "equipment_history": _safe_equipment(patient, dataset),
        "comparison": result,
    }
    validate_safe_payload(payload)
    pa, pb = result["period_a"], result["period_b"]
    meta = {
        "period_start": pa.get("from"), "period_end": pb.get("to"),
        "therapy_days": int(pa.get("days") or 0) + int(pb.get("days") or 0),
        "session_count": 0,
        "comparison": {"a_start": pa.get("from"), "a_end": pa.get("to"), "b_start": pb.get("from"), "b_end": pb.get("to")},
    }
    return payload, meta


def validate_safe_payload(payload: Any, path: str = "root") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lower = str(key).lower()
            if lower in FORBIDDEN_KEYS or any(token in lower for token in ("serial", "username", "email", "phone", "address", "taj", "patient_id", "file_path")):
                raise ValueError(f"Az AI adatvédelmi szűrő tiltott mezőt talált: {path}.{key}")
            validate_safe_payload(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for idx, value in enumerate(payload):
            validate_safe_payload(value, f"{path}[{idx}]")


COMMON_SYSTEM_PROMPT = """Te egy PAP/CPAP terápiás adatelemző asszisztens vagy. Magyarul válaszolj, laikus számára érthetően, de szakmailag pontosan.
Kizárólag a kapott anonim terápiás JSON-ból dolgozz. Ne találj ki hiányzó adatot. Ne diagnosztizálj és ne adj kötelező, konkrét nyomásmódosítási utasítást. OA, CA, H, RERA és UA eseményeket külön értelmezd. A saját korábbi adatok és trendek legyenek az elsődleges referencia. Korrelációból ne állíts automatikusan okozati kapcsolatot. A fontosabb következtetésekhez használj high/medium/low bizonyossági szintet.
Minden felhasználónak szánt szöveg magyar legyen, beleértve az overall.title és a trends[].title mezőket is. Az overall.title legyen rövid, természetes és informatív magyar cím, ne programozói/generikus cím (tilos például: „Therapy performance for ...”, „Analysis”, „Summary”, „PAP-terápiás AI kiértékelés”). A címben dátumot csak akkor használj, ha tényleg szükséges; ha használsz, kizárólag ÉÉÉÉ.HH.NN. formátumban. Minden más dátumot is ÉÉÉÉ.HH.NN. formában írj ki a természetes szövegekben.
A válaszod KIZÁRÓLAG érvényes JSON objektum legyen, markdown kódblokk nélkül. A JSON első mezője legyen a live_text, amely 2-5 mondatos, természetes magyar összefoglaló, hogy a felület már generálás közben meg tudja jeleníteni. A séma:
{
  "live_text":"...",
  "analysis_type":"night|week|month|full_period|comparison",
  "overall":{"status":"very_good|good|acceptable|attention|unfavorable","title":"...","summary":"..."},
  "therapy_effectiveness":{"text":"...","confidence":"high|medium|low"},
  "events":{"text":"...","confidence":"high|medium|low"},
  "pressure":{"text":"...","confidence":"high|medium|low"},
  "leak":{"text":"...","confidence":"high|medium|low"},
  "oxygen":null vagy {"text":"...","confidence":"high|medium|low"},
  "trends":[{"title":"...","text":"...","confidence":"high|medium|low"}],
  "positives":["..."],
  "attention_points":["..."],
  "recommendations":[{"priority":"low|medium|high","type":"monitor|comfort|mask|leak|data|medical_review","text":"..."}],
  "medical_review":{"suggested":false,"reason":null},
  "data_quality":{"sufficient":true,"missing_useful_data":[]}
}
Ha egy teljes témához nincs adat, a megfelelő mező legyen null vagy röviden jelezd az adathiányt; ne gyárts értéket."""

TYPE_PROMPTS = {
    "night": "Az utolsó terápiás éjszakát elemezd részletesen. Keresd a session megszakításokat, AHI/OA/CA/H/RERA szerkezetét, nyomás- és szivárgási mintázatot, és hasonlítsd a rendelkezésre álló saját előzményekhez. Fő kérdés: mi történt ezen az éjszakán, mennyire volt eredményes és stabil a terápia, és van-e valami, amire érdemes figyelni?",
    "week": "Az utolsó 7 rendelkezésre álló terápiás nap mintázatait értékeld. Ne reagálj túl egyetlen rossz éjszakára; keresd az ismétlődő trendeket, compliance-et, AHI és eseménytípusok, nyomás és szivárgás változását. Fő kérdés: látható-e már ismétlődő minta vagy egyértelmű heti tendencia?",
    "month": "A kiválasztott hónap terápiás fejlődését értékeld. Vizsgáld az AHI, OA/CA/H/RERA, használat, nyomás, szivárgás és légzési mutatók trendjét, valamint az időszak eleje és vége közötti változást. Fő kérdés: merre halad a terápia: stabilizálódik, javul, romlik vagy lényegében változatlan?",
    "full_period": "A rendelkezésre álló teljes PAP-terápiás időszakot értékeld átfogóan. Emeld ki a hosszú távú trendeket, stabil és visszatérő problémákat, legjobb/rosszabb időszakokat, valamint a terápiás előírások vagy felszerelés-változások utáni mérhető eltéréseket. Fő kérdés: hogyan alakult a PAP-terápia a kezelés megkezdésétől mostanáig?",
    "comparison": "Két külön terápiás időszakot hasonlíts össze. A B időszakot tekintsd az újabb/összehasonlítandó állapotnak. Külön értékeld az AHI, OA/CA/H/RERA index, használati idő, nyomás P95 és szivárgás P95 változását. Ne csak azt írd le, hogy eltérnek: mondd meg, melyik irány kedvező vagy kedvezőtlen, és jelezd, ha a kevés terápiás nap miatt gyenge a bizonyosság. Fő kérdés: mi változott mérhetően a két időszak között?",
}


def analysis_prompts(analysis_type: str, safe_payload: dict[str, Any]) -> tuple[str, str]:
    specific = TYPE_PROMPTS.get(analysis_type)
    if not specific:
        raise ValueError("Ismeretlen AI kiértékelési mód.")
    user = specific + "\n\nANONIM TERÁPIÁS JSON:\n" + json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"))
    return COMMON_SYSTEM_PROMPT, user


def chat_prompts(analysis: dict[str, Any], question: str) -> tuple[str, str]:
    result = analysis.get("result") if isinstance(analysis.get("result"), dict) else {}
    safe_payload = analysis.get("safe_payload") if isinstance(analysis.get("safe_payload"), dict) else {}
    system = """Egy már elkészült PAP/CPAP terápiás kiértékelés folytatólagos chat-asszisztense vagy. Magyarul, közérthetően válaszolj. Csak a mentett anonim terápiás adatcsomagból, az elkészült értékelésből és a beszélgetésből dolgozz. Ne találj ki adatot, ne diagnosztizálj, és ne adj kötelező konkrét nyomásmódosítást. Ha a kérdéshez nincs elég adat, mondd ki egyértelműen. A válasz most természetes szöveg legyen, ne JSON."""
    history = []
    for m in (analysis.get("messages") or [])[-16:]:
        if isinstance(m, dict) and m.get("role") in {"user", "assistant"}:
            history.append({"role": m.get("role"), "content": str(m.get("content") or "")[:5000]})
    context = {
        "saved_analysis": result,
        "anonymous_therapy_payload": safe_payload,
        "chat_history": history,
        "new_question": question,
    }
    return system, json.dumps(context, ensure_ascii=False, separators=(",", ":"))
