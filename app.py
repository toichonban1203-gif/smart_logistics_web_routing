# -*- coding: utf-8 -*-
from __future__ import annotations
import io
import json
import re
import numpy as np
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz
from unidecode import unidecode

# ============================================================================
# ⚙️ 1. CORE INFRASTRUCTURE: TỐI ƯU HÓA DUNG LƯỢNG (RAM OPTIMIZATION)
# ============================================================================

INT32_MIN, INT32_MAX = -2_147_483_648, 2_147_483_647
FLOAT32_SAFE_MAX = 1e7
KEEP_FLOAT64 = {"lat", "lng", "lon", "latitude", "longitude"}

def optimize_dtypes(df: pd.DataFrame, categorize: bool = False, cat_ratio: float = 0.5, keep_float64: set = KEEP_FLOAT64) -> pd.DataFrame:
    """
    Tối ưu dung lượng RAM của DataFrame:
    - Ép kiểu số nguyên 64-bit về 32-bit nếu nằm trong khoảng an toàn.
    - Ép kiểu số thực 64-bit về 32-bit (giữ nguyên float64 cho tọa độ GIS).
    - Tự động chuyển đổi chuỗi lặp lại nhiều thành kiểu 'category'.
    """
    if df is None or len(df) == 0 or len(df.columns) == 0 or df.columns.duplicated().any():
        return df
    
    out = df.copy()
    for col in out.columns:
        s = out[col]
        dtype = s.dtype
        try:
            is_text = (dtype == object) or (pd.api.types.is_string_dtype(dtype) and not isinstance(dtype, pd.CategoricalDtype))
            if categorize and is_text and len(s) > 0:
                if s.nunique(dropna=True) / len(s) < cat_ratio:
                    out[col] = s.astype("category")
                continue
            if not isinstance(dtype, np.dtype):
                continue
            
            # Tối ưu kiểu số nguyên
            if dtype.kind == "i" and dtype.itemsize > 4:
                if s.min() >= INT32_MIN and s.max() <= INT32_MAX:
                    out[col] = s.astype("int32")
            # Tối ưu kiểu số thực (Tránh hạ cấp tọa độ GIS)
            elif dtype.kind == "f" and dtype.itemsize > 4:
                if str(col).strip().lower() in keep_float64:
                    continue
                mx = s.abs().max()
                if pd.isna(mx) or mx < FLOAT32_SAFE_MAX:
                    out[col] = s.astype("float32")
        except Exception:
            continue
    return out

def mem_kb(df: pd.DataFrame) -> float:
    """Tính dung lượng RAM hiện tại của DataFrame (KB)."""
    if df is None or df.empty:
        return 0.0
    return float(df.memory_usage(deep=True).sum()) / 1024.0


# ============================================================================
# ⚙️ 2. CORE INFRASTRUCTURE: SEMANTIC MAPPING & DATA PROFILING THÔNG MINH
# ============================================================================

def norm_basic(v: str) -> str:
    """Chuẩn hóa chuỗi: Bỏ dấu tiếng Việt, chuyển chữ thường, loại bỏ ký tự đặc biệt."""
    if v is None:
        return ""
    return re.sub(r"[^a-z0-9 ]+", " ", unidecode(str(v)).lower()).strip()

def default_profile_score(series: pd.Series, field_name: str) -> float:
    """
    Data Profiling: Kiểm tra độ tương thích về mặt dữ liệu thực tế trong cột.
    Trả về điểm số từ 0.0 -> 1.0.
    """
    valid_s = series.dropna().astype(str).str.strip()
    valid_s = valid_s[valid_s != ""]
    if valid_s.empty:
        return 0.0
    
    # Nếu là trường định lượng/số
    if any(k in field_name.lower() for k in ["weight", "volume", "speed", "distance", "cost", "price", "qty", "quantity", "kg", "m3"]):
        numeric_ratio = float(valid_s.str.replace(r"[^\d.]", "", regex=True).str.len().gt(0).mean())
        return numeric_ratio
    
    # Nếu là trường định danh ID / Tên / Mã
    return float(valid_s.nunique() / len(valid_s))

def basic_semantic_mapping(
    df: pd.DataFrame, 
    fields: dict[str, list[str]], 
    profile_fn = default_profile_score, 
    threshold: float = 0.35
) -> dict[str, tuple[str | None, float, str]]:
    """
    Ánh xạ ngữ nghĩa cột dữ liệu đầu vào với Schema chuẩn của hệ thống:
    - Kết hợp So khớp chuỗi mờ (RapidFuzz token_set_ratio)
    - So khớp từ khóa chính xác (Keyword matching)
    - Kiểm tra cấu trúc dữ liệu thực tế (Data Profiling)
    """
    result = {}
    used_cols = set()

    for fld, aliases in fields.items():
        all_aliases = list(aliases) + [fld]
        best_col, best_score, best_reason = None, 0.0, ""

        for col in df.columns:
            if col in used_cols:
                continue
            
            col_norm = norm_basic(col)
            
            # 1. Fuzzy Matching Score (RapidFuzz)
            fuzzy_score = max(fuzz.token_set_ratio(col_norm, norm_basic(a)) for a in all_aliases) / 100.0
            
            # 2. Keyword Match Score
            keyword_score = float(any(norm_basic(a) in col_norm for a in all_aliases if len(norm_basic(a)) >= 2))
            
            # 3. Data Profiling Score (Kiểm tra kiểu dữ liệu thực tế trong cột)
            prof_score = profile_fn(df[col], fld)
            
            # Tổng hợp điểm trọng số: 75% Text Matching + 25% Data Profiling
            text_score = 0.7 * fuzzy_score + 0.3 * keyword_score
            total_score = 0.75 * text_score + 0.25 * prof_score

            if total_score > best_score:
                best_col = col
                best_score = total_score
                best_reason = f"Text: {text_score:.0%} | Profile: {prof_score:.0%}"

        if best_col is not None and best_score >= threshold:
            result[fld] = (best_col, best_score, best_reason)
            used_cols.add(best_col)
        else:
            result[fld] = (None, 0.0, "Không tìm thấy cột phù hợp")

    return result
