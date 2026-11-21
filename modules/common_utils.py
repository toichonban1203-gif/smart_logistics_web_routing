# -*- coding: utf-8 -*-
"""Hàm dùng chung cho các module master data (tránh lặp code)."""
import datetime as dt
import pandas as pd

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y")
SHIFT_OPTIONS = ["Ca Sáng", "Ca Chiều", "Ca Đêm"]


def parse_num(val) -> float:
    if val is None or pd.isna(val) or str(val).strip() == "":
        return 0.0
    try:
        cleaned = pd.Series([str(val)]).str.replace(r"[^\d.-]", "", regex=True).iloc[0]
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0


def parse_date(dstr) -> str:
    """Trả về 'YYYY-MM-DD'. Nếu trống/sai định dạng trả về "" (KHÔNG tự điền ngày hôm nay)."""
    if dstr is None or pd.isna(dstr) or str(dstr).strip() == "":
        return ""
    dstr = str(dstr).strip()
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(dstr, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    parsed = pd.to_datetime(dstr, errors="coerce")
    return parsed.strftime("%Y-%m-%d") if pd.notna(parsed) else ""


def normalize_shift(s) -> str:
    """Một quy tắc ca duy nhất cho Orders và Orders_solving."""
    t = str(s).strip().lower()
    if "chiều" in t or "pm" in t:
        return "Ca Chiều"
    if "đêm" in t or "tối" in t or "flexible" in t or "linh hoạt" in t:
        return "Ca Đêm"
    return "Ca Sáng"
