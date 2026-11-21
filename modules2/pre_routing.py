# -*- coding: utf-8 -*-
import os
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz

# ============================================================================
# ⚙️ 1. CẤU HÌNH SCHEMA CHUẨN & FIELD MAPPING CHO MA TRẬN TẮC ĐƯỜNG NGANG
# ============================================================================
DAYS_SPEC = [
    ("T2", "Thứ 2", ["thứ 2", "thu 2", "t2", "mon"]),
    ("T3", "Thứ 3", ["thứ 3", "thu 3", "t3", "tue"]),
    ("T4", "Thứ 4", ["thứ 4", "thu 4", "t4", "wed"]),
    ("T5", "Thứ 5", ["thứ 5", "thu 5", "t5", "thu"]),
    ("T6", "Thứ 6", ["thứ 6", "thu 6", "t6", "fri"]),
    ("T7", "Thứ 7", ["thứ 7", "thu 7", "t7", "sat"]),
    ("CN", "Chủ Nhật", ["chủ nhật", "chu nhat", "cn", "sun", "thứ 8"])
]

SHIFTS_SPEC = [
    ("CA1", "🌅 Ca 1 (Sớm)",     ["ca 1", "ca1", "ca sớm", "sớm", "early"]),
    ("CA2", "☀️ Ca 2 (Trưa)",    ["ca 2", "ca2", "ca trưa", "trưa", "noon"]),
    ("CA3", "🌤️ Ca 3 (Chiều)",   ["ca 3", "ca3", "ca chiều", "chiều", "afternoon"]),
    ("CA4", "🌆 Ca 4 (Chập tối)", ["ca 4", "ca4", "ca chập tối", "chập tối", "tối", "evening"])
]

TIMELINE_COLS = [f"{d_code}_{s_code}" for d_code, _, _ in DAYS_SPEC for s_code, _, _ in SHIFTS_SPEC]

BASE_TRAFFIC_FIELDS = {
    "WARD": ["tên phường", "phường", "xã", "phường/xã", "ward", "commune", "địa bàn"],
    "ZONE": ["area", "khu vực", "vùng", "zone", "loại khu vực", "phân vùng"]
}

ZONE_OPTIONS = [
    "🏙️ Đô thị lõi",
    "🛣️ Gần trục đường lớn",
    "🏘️ Đô thị vệ tinh",
    "🌾 Ngoại thành"
]

SPEED_ZONE_COLS = ["SPD_CORE", "SPD_ARTERIAL", "SPD_SATELLITE", "SPD_SUBURBAN"]

# ============================================================================
# 🛠️ 2. HÀM ĐỌC FILE EXCEL MA TRẬN NGANG 2 TẦNG & CHUẨN HÓA DỮ LIỆU
# ============================================================================
def parse_traffic_matrix_horizontal(uploaded_file) -> pd.DataFrame:
    xl = pd.ExcelFile(uploaded_file)
    target_sheet = "DIM_AREA" if "DIM_AREA" in xl.sheet_names else xl.sheet_names[0]

    preview = pd.read_excel(xl, sheet_name=target_sheet, header=None, nrows=3)
    if len(preview) < 2:
        return pd.read_excel(xl, sheet_name=target_sheet)

    row0_str = " ".join(preview.iloc[0].dropna().astype(str)).lower()
    row1_str = " ".join(preview.iloc[1].dropna().astype(str)).lower()

    is_matrix_2_rows = ("thứ" in row0_str or "thu" in row0_str) and ("ca 1" in row1_str or "ca 2" in row1_str)

    if not is_matrix_2_rows:
        return pd.read_excel(xl, sheet_name=target_sheet)

    raw = pd.read_excel(xl, sheet_name=target_sheet, header=None)
    top_header = raw.iloc[0].ffill().fillna("").astype(str).str.strip()
    sub_header = raw.iloc[1].fillna("").astype(str).str.strip()
    data_body = raw.iloc[2:].copy().reset_index(drop=True)

    flat_columns = []
    for idx in range(len(sub_header)):
        t_val = top_header[idx]
        s_val = sub_header[idx]

        if not any(k in t_val.lower() for k in ["thứ", "thu", "chủ nhật", "cn"]):
            col_name = s_val if s_val else (t_val if t_val else f"COL_{idx}")
            flat_columns.append(col_name)
        else:
            flat_columns.append(f"{t_val} - {s_val}")

    data_body.columns = flat_columns
    data_body = data_body.dropna(how="all").reset_index(drop=True)
    return data_body

def parse_factor(val) -> float:
    if pd.isna(val) or val is None or str(val).strip() == "":
        return 1.0
    try:
        cleaned = pd.Series([str(val)]).str.replace(r"[^\d.-]", "", regex=True).iloc[0]
        num = float(cleaned) if cleaned else 1.0
        return round(max(1.0, num), 2)
    except Exception:
        return 1.0

def normalize_zone(z_raw: str) -> str:
    z = str(z_raw).lower().strip()
    if "trục" in z or "lớn" in z or "quốc lộ" in z or "vành đai" in z:
        return "🛣️ Gần trục đường lớn"
    if "vệ tinh" in z or "đô thị mới" in z:
        return "🏘️ Đô thị vệ tinh"
    if "ngoại thành" in z or "ngoại ô" in z or "huyện" in z:
        return "🌾 Ngoại thành"
    return "🏙️ Đô thị lõi"

def auto_match_timeline_cols(df_columns) -> dict:
    mapping = {}
    for d_code, d_name, d_kws in DAYS_SPEC:
        for s_code, s_name, s_kws in SHIFTS_SPEC:
            target_key = f"{d_code}_{s_code}"
            best_col = None
            best_score = 0

            for col in df_columns:
                c_low = str(col).lower()
                has_day = any(dk in c_low for dk in d_kws)
                has_shift = any(sk in c_low for sk in s_kws)
                if has_day and has_shift:
                    score = fuzz.token_set_ratio(c_low, f"{d_name} {s_code}".lower())
                    if score > best_score:
                        best_score = score
                        best_col = str(col)
                elif c_low == target_key.lower():
                    best_col = str(col)
                    break

            mapping[target_key] = best_col
    return mapping

def process_traffic_row_horizontal(row_dict: dict) -> dict:
    out = {
        "WARD": str(row_dict.get("WARD", "")).strip() if row_dict.get("WARD") else "",
        "ZONE": normalize_zone(row_dict.get("ZONE", ""))
    }
    for t_col in TIMELINE_COLS:
        out[t_col] = parse_factor(row_dict.get(t_col))
    return out

def validate_traffic_horizontal(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    dup_ward = out["WARD"].astype(str).str.lower().str.strip().duplicated(keep=False)
    msgs = []

    for i, row in out.iterrows():
        errs = []
        w = str(row.get("WARD", "")).strip()
        if not w:
            errs.append("Thiếu Tên Phường")
        if dup_ward.iloc[i] and w:
            errs.append("Trùng Tên Phường")
        if any(row.get(c, 0) < 1.0 for c in TIMELINE_COLS):
            errs.append("Có hệ số < 1.0")
        msgs.append("❌ " + "; ".join(errs) if errs else "✅ Hợp lệ")

    out["KIỂM_TRA"] = msgs
    return out

def export_traffic_matrix_excel(df: pd.DataFrame, xlsx_path: str):
    clean_df = df.drop(columns=["KIỂM_TRA"], errors="ignore").copy()
    clean_df["ZONE"] = clean_df["ZONE"].str.replace(r"^[^\wÀ-ỹ]+\s*", "", regex=True)

    multi_tuples = [("", "STT"), ("", "Tên Phường"), ("", "Area")]
    for _, d_name, _ in DAYS_SPEC:
        for s_code, _, _ in SHIFTS_SPEC:
            multi_tuples.append((d_name, f"Ca {s_code[-1]}"))

    export_data = pd.DataFrame()
    export_data[("", "STT")] = range(1, len(clean_df) + 1)
    export_data[("", "Tên Phường")] = clean_df["WARD"].values
    export_data[("", "Area")] = clean_df["ZONE"].values

    for d_code, d_name, _ in DAYS_SPEC:
        for s_code, _, _ in SHIFTS_SPEC:
            export_data[(d_name, f"Ca {s_code[-1]}")] = clean_df[f"{d_code}_{s_code}"].values

    export_data.columns = pd.MultiIndex.from_tuples(multi_tuples)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        export_data.to_excel(writer, sheet_name="DIM_AREA")

def suggest_zone_speeds(weight_kg: float) -> tuple:
    """Gợi ý vận tốc cơ sở (km/h) theo 4 khu vực chuẩn như mẫu DIM_VEHICLE"""
    if weight_kg >= 2000:
        return (45.0, 35.0, 50.0, 55.0)
    elif weight_kg >= 500:
        return (40.0, 30.0, 45.0, 50.0)
    return (30.0, 25.0, 35.0, 40.0)

def export_vehicle_speed_matrix_excel(df: pd.DataFrame, xlsx_path: str):
    """Xuất file Excel giữ đúng format nhóm cột 'Vận tốc cơ sở' gộp ngang trên 4 khu vực"""
    multi_tuples = [
        ("", "ID_VEHICLE"),
        ("", "TRUCK"),
        ("", "MAX_WEIGHT_KG"),
        ("", "MAX_VOLUME_M3"),
        ("Vận tốc cơ sở", "Đô thị lõi"),
        ("Vận tốc cơ sở", "Gần trục đường lớn"),
        ("Vận tốc cơ sở", "Đô thị vệ tinh"),
        ("Vận tốc cơ sở", "Ngoại thành"),
    ]
    export_data = pd.DataFrame()
    export_data[("", "ID_VEHICLE")] = df["ID_VEHICLE"].values
    export_data[("", "TRUCK")] = df["TRUCK"].values
    export_data[("", "MAX_WEIGHT_KG")] = df["MAX_WEIGHT_KG"].values
    export_data[("", "MAX_VOLUME_M3")] = df["MAX_VOLUME_M3"].values
    export_data[("Vận tốc cơ sở", "Đô thị lõi")] = df["SPD_CORE"].values
    export_data[("Vận tốc cơ sở", "Gần trục đường lớn")] = df["SPD_ARTERIAL"].values
    export_data[("Vận tốc cơ sở", "Đô thị vệ tinh")] = df["SPD_SATELLITE"].values
    export_data[("Vận tốc cơ sở", "Ngoại thành")] = df["SPD_SUBURBAN"].values

    export_data.columns = pd.MultiIndex.from_tuples(multi_tuples)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        export_data.to_excel(writer, sheet_name="DIM_VEHICLE_SPEED")

# ============================================================================
# ⚙️ 3. KHỞI TẠO GIÁ TRỊ MẶC ĐỊNH TRONG SESSION STATE
# ============================================================================
def init_pre_routing_state():
    if "shift_count" not in st.session_state:
        st.session_state["shift_count"] = 2
    default_shifts = [
        ("Ca Sáng", "06:00", "12:00"),
        ("Ca Chiều", "13:00", "17:30"),
        ("Ca Đêm", "18:00", "22:00"),
        ("Ca Linh Hoạt", "08:00", "17:00")
    ]
    for i in range(4):
        dn, ds, de = default_shifts[i]
        if f"sh_name_{i}" not in st.session_state:
            st.session_state[f"sh_name_{i}"] = dn
        if f"sh_start_{i}" not in st.session_state:
            st.session_state[f"sh_start_{i}"] = ds
        if f"sh_end_{i}" not in st.session_state:
            st.session_state[f"sh_end_{i}"] = de

# ============================================================================
# 🖥️ 4. GIAO DIỆN PRE-ROUTING (CẤU HÌNH THAM SỐ VẬN TẢI & HỆ SỐ TẮC ĐƯỜNG)
# ============================================================================
def render_pre_routing_tab():
    init_pre_routing_state()
    st.header("⚙️ Tab 3: Pre-Routing — Quy Định Vận Tải & Tham Số Đầu Vào")
    st.caption("🛠️ *Thiết lập các quy định về hàng hóa, ca làm việc, thời điểm kiểm tra xe, ma trận tắc đường và vận tốc cơ sở theo khu vực.*")
    st.divider()

    # ------------------------------------------------------------------------
    # 📦 PHẦN 1: ĐẶC THÙ HÀNG HÓA (CUBE OUT / WEIGHT OUT)
    # ------------------------------------------------------------------------
    st.markdown("### 📦 1. Đặc Thù Hàng Hóa (Ràng buộc lấp đầy xe)")
    constraint_mode = st.selectbox(
        "Phương thức ưu tiên lấp đầy phương tiện (Drop-down chọn):",
        options=["Cube Out (Thể tích m³)", "Weight Out (Trọng tải kg)"],
        index=0,
        help="Cube Out: Ưu tiên lấp đầy thể tích trước. Weight Out: Ưu tiên lấp đầy trọng tải trước.",
        key="cfg_constraint_mode"
    )
    st.divider()

    # ------------------------------------------------------------------------
    # ⏰ PHẦN 2: CẤU HÌNH CÁC CA TRONG NGÀY (THÊM / BỚT ĐỘNG)
    # ------------------------------------------------------------------------
    st.markdown("### ⏰ 2. Cấu Hình Các Ca Làm Việc Trong Ngày")
    st.caption("Thêm hoặc bớt các ca làm việc phù hợp với khung giờ hoạt động của doanh nghiệp.")
    col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 5])
    if col_btn1.button("➕ Thêm ca", key="btn_add_shift_pr"):
        if st.session_state["shift_count"] < 6:
            st.session_state["shift_count"] += 1
            st.rerun()
        else:
            st.warning("Tối đa 6 ca trong ngày.")
    if col_btn2.button("➖ Bớt ca", key="btn_rem_shift_pr"):
        if st.session_state["shift_count"] > 1:
            st.session_state["shift_count"] -= 1
            st.rerun()

    n_shifts = st.session_state["shift_count"]
    shifts_data = []
    h0, h1, h2, h3 = st.columns([0.5, 3, 2, 2])
    h0.markdown("**#**")
    h1.markdown("**Tên ca**")
    h2.markdown("**Giờ bắt đầu (HH:MM)**")
    h3.markdown("**Giờ kết thúc (HH:MM)**")

    for i in range(n_shifts):
        c0, c1, c2, c3 = st.columns([0.5, 3, 2, 2])
        c0.markdown(f"**Ca {i+1}**")
        name = c1.text_input(f"Tên ca {i+1}", key=f"sh_name_{i}", label_visibility="collapsed")
        start = c2.text_input(f"Bắt đầu {i+1}", key=f"sh_start_{i}", label_visibility="collapsed")
        end = c3.text_input(f"Kết thúc {i+1}", key=f"sh_end_{i}", label_visibility="collapsed")
        shifts_data.append({"name": name, "start": start, "end": end})
    st.divider()

    # ------------------------------------------------------------------------
    # 🔄 PHẦN 3: THỜI ĐIỂM KIỂM TRA HẠM ĐỘI XE (FLEET CUTOFF TIME)
    # ------------------------------------------------------------------------
    st.markdown("### 🔄 3. Thời Điểm Kiểm Tra Hạm Đội Xe")
    split_time = st.text_input(
        "Giờ chốt kiểm tra xe quay về kho (HH:MM):",
        value="12:00",
        help="Tại mốc giờ này, hệ thống sẽ xác định các xe đã hoàn thành chuyến ca sáng để chuẩn bị phục vụ ca tiếp theo.",
        key="cfg_split_time"
    )
    st.divider()

    # ------------------------------------------------------------------------
    # 🚦 PHẦN 4: MA TRẬN HỆ SỐ TẮC ĐƯỜNG NGANG (1 PHƯỜNG = 1 HÀNG, 28 CỘT TIMELINE)
    # ------------------------------------------------------------------------
    st.markdown("### 🚦 4. Ma Trận Hệ Số Tắc Đường Theo Phường & Timeline (7 Ngày × 4 Ca)")
    st.caption("📍 *Mỗi phường là 1 hàng ngang, trải dài qua 28 khung giờ từ Thứ 2 (Ca 1 → Ca 4) đến Chủ Nhật (Ca 1 → Ca 4).*")

    seed_data = {
        "WARD": ["Hoàn Kiếm", "Vĩnh Tuy", "Dương Nội", "Đông Anh"],
        "ZONE": ["🏙️ Đô thị lõi", "🛣️ Gần trục đường lớn", "🏘️ Đô thị vệ tinh", "🌾 Ngoại thành"],
    }
    base_patterns = [
        [2.20, 1.60, 1.50, 1.80],
        [4.00, 2.80, 2.40, 3.20],
        [1.40, 1.15, 1.25, 1.50],
        [1.15, 1.05, 1.10, 1.20],
    ]
    for d_idx, (d_code, _, _) in enumerate(DAYS_SPEC):
        decay = 1.0 if d_idx == 0 else (0.85 if d_idx == 6 else 0.90)
        for s_idx, (s_code, _, _) in enumerate(SHIFTS_SPEC):
            seed_data[f"{d_code}_{s_code}"] = [
                round(max(1.0, base_patterns[w_i][s_idx] * decay), 2) for w_i in range(4)
            ]
    seed_traffic_df = pd.DataFrame(seed_data)

    mode = st.radio(
        "Phương thức nhập Ma trận tắc đường:",
        ["📂 Upload file Excel/CSV/JSON", "✍️ Nhập trực tiếp (Data Editor)"],
        horizontal=True,
        key="traffic_input_mode"
    )

    raw_df = None
    if mode == "✍️ Nhập trực tiếp (Data Editor)":
        st.markdown("##### 📝 Chỉnh sửa trực tiếp ma trận ngang (cuộn ngang để xem đủ Thứ 2 → Chủ Nhật):")
        col_cfg = {
            "WARD": st.column_config.TextColumn("📍 Tên Phường", required=True, pinned=True),
            "ZONE": st.column_config.SelectboxColumn("🗺️ Khu vực", options=ZONE_OPTIONS, required=True, pinned=True),
        }
        for d_code, d_name, _ in DAYS_SPEC:
            for s_code, _, _ in SHIFTS_SPEC:
                col_cfg[f"{d_code}_{s_code}"] = st.column_config.NumberColumn(
                    f"{d_code} | Ca {s_code[-1]}", min_value=1.0, max_value=10.0, step=0.05, format="%.2f"
                )
        raw_df = st.data_editor(
            seed_traffic_df,
            num_rows="dynamic",
            column_config=col_cfg,
            key="traffic_editor_horiz"
        )
    else:
        st.markdown("##### 📂 Upload file ma trận tắc đường từ máy tính:")
        uploaded_file = st.file_uploader(
            "Chọn file ma trận tắc đường (xlsx, xls, csv, json)",
            type=["xlsx", "xls", "csv", "json"],
            key="traffic_upload_horiz"
        )
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".json"):
                    raw_df = pd.read_json(uploaded_file)
                else:
                    raw_df = parse_traffic_matrix_horizontal(uploaded_file)
                st.caption(f"📄 Tìm thấy `{len(raw_df)}` phường (hàng ngang) và `{len(raw_df.columns)}` cột dữ liệu trong file.")
            except Exception as e:
                st.error(f"❌ Lỗi đọc file: {e}")

    # ============================================================================
    # 🔍 ÁNH XẠ CỘT SEMANTIC MAPPING CHO MA TRẬN NGANG
    # ============================================================================
    if raw_df is not None and not raw_df.empty:
        st.divider()
        st.markdown("#### 🔍 Quét & Ánh Xạ Cột Ma Trận Ngang")
        st.info("💡 Hệ thống tự động nhận diện cột **Tên Phường**, **Khu vực (Area)** và **28 cột timeline (Thứ 2 → Chủ Nhật × Ca 1 → Ca 4)**.")

        input_cols = ["-- Bỏ qua / Không sử dụng --"] + [str(c) for c in raw_df.columns]
        chosen_base_map = {}
        c_map1, c_map2 = st.columns(2)

        for idx, (target_field, aliases) in enumerate(BASE_TRAFFIC_FIELDS.items()):
            best_match = "-- Bỏ qua / Không sử dụng --"
            best_score = 0
            for col in raw_df.columns:
                score = max(fuzz.token_set_ratio(str(col).lower(), a.lower()) for a in aliases + [target_field])
                if score > best_score and score > 40:
                    best_score = score
                    best_match = str(col)
            target_col_ui = c_map1 if idx == 0 else c_map2
            label_txt = "📍 Cột Tên Phường (`WARD`):" if target_field == "WARD" else "🗺️ Cột Khu Vực (`ZONE / Area`):"
            with target_col_ui:
                chosen_base_map[target_field] = st.selectbox(
                    label_txt,
                    options=input_cols,
                    index=input_cols.index(best_match) if best_match in input_cols else 0,
                    key=f"map_tf_base_{target_field}"
                )

        auto_timeline_map = auto_match_timeline_cols(raw_df.columns)
        matched_count = sum(1 for v in auto_timeline_map.values() if v is not None)
        st.caption(f"🎯 Đã tự động khớp **{matched_count}/28** cột timeline (`Thứ 2 Ca 1` → `Chủ Nhật Ca 4`).")

        with st.expander("🛠️ Kiểm tra / Tùy chỉnh chi tiết ánh xạ 28 cột timeline (Thứ × Ca)", expanded=(matched_count < 28)):
            chosen_timeline_map = {}
            for d_code, d_name, _ in DAYS_SPEC:
                st.markdown(f"**📅 {d_name}**")
                d_cols = st.columns(4)
                for s_idx, (s_code, s_label, _) in enumerate(SHIFTS_SPEC):
                    t_key = f"{d_code}_{s_code}"
                    detected_col = auto_timeline_map.get(t_key)
                    default_idx = input_cols.index(detected_col) if detected_col in input_cols else 0
                    with d_cols[s_idx]:
                        chosen_timeline_map[t_key] = st.selectbox(
                            s_label,
                            options=input_cols,
                            index=default_idx,
                            key=f"map_tl_{t_key}"
                        )

        st.divider()
        if st.button("🚀 Quét & Tổng Hợp Ma Trận Tắc Đường", type="primary", key="btn_process_traffic_horiz"):
            processed_rows = []
            for _, row in raw_df.iterrows():
                rec = {}
                for b_field, m_col in chosen_base_map.items():
                    rec[b_field] = row[m_col] if (m_col != "-- Bỏ qua / Không sử dụng --" and m_col in raw_df.columns) else None
                for t_key, m_col in chosen_timeline_map.items():
                    rec[t_key] = row[m_col] if (m_col != "-- Bỏ qua / Không sử dụng --" and m_col in raw_df.columns) else 1.0
                processed_rows.append(process_traffic_row_horizontal(rec))

            final_tf_df = validate_traffic_horizontal(pd.DataFrame(processed_rows))
            st.session_state["traffic_final_df"] = final_tf_df

    # ============================================================================
    # 📋 BẢNG TỔNG HỢP MA TRẬN NGANG ĐẸP & XUẤT FILE EXCEL DIM_TRAFFIC_FACTOR.XLSX
    # ============================================================================
    if "traffic_final_df" in st.session_state and not st.session_state["traffic_final_df"].empty:
        df_tf = st.session_state["traffic_final_df"]

        # Tự động dọn session cũ nếu lệch schema cột
        if any(c not in df_tf.columns for c in TIMELINE_COLS):
            del st.session_state["traffic_final_df"]
            st.rerun()

        st.markdown("#### 📊 Bảng Tổng Hợp Ma Trận Tắc Đường Đã Chuẩn Hóa")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("📍 Tổng Số Phường", f"{len(df_tf)} phường")
        k2.metric("🗺️ Số Nhóm Khu Vực", f"{df_tf['ZONE'].nunique()} khu vực")
        max_tf = df_tf[TIMELINE_COLS].max().max()
        avg_tf = df_tf[TIMELINE_COLS].mean().mean()
        k3.metric("🔥 Hệ Số Cao Nhất", f"{max_tf:.2f}x")
        k4.metric("⚖️ Hệ Số Trung Bình", f"{avg_tf:.2f}x")

        zone_filter = st.multiselect(
            "🔎 Lọc nhanh theo Khu vực:",
            options=ZONE_OPTIONS,
            default=ZONE_OPTIONS,
            key="filter_zone_tf"
        )
        df_view = df_tf[df_tf["ZONE"].isin(zone_filter)] if zone_filter else df_tf

        display_col_cfg = {
            "WARD":     st.column_config.TextColumn("📍 Tên Phường", pinned=True),
            "ZONE":     st.column_config.SelectboxColumn("🗺️ Khu Vực", options=ZONE_OPTIONS, pinned=True),
            "KIỂM_TRA": st.column_config.TextColumn("🛡️ Trạng Thái")
        }
        for d_code, _, _ in DAYS_SPEC:
            for s_code, _, _ in SHIFTS_SPEC:
                display_col_cfg[f"{d_code}_{s_code}"] = st.column_config.NumberColumn(
                    f"{d_code} | Ca {s_code[-1]}", format="%.2f"
                )

        edited_tf_df = st.data_editor(
            df_view,
            num_rows="dynamic",
            use_container_width=True,
            column_config=display_col_cfg,
            column_order=["WARD", "ZONE"] + TIMELINE_COLS + ["KIỂM_TRA"],
            key="traffic_final_editor_horiz"
        )

        out_dir = "output_pre_routing"
        os.makedirs(out_dir, exist_ok=True)
        xlsx_path = os.path.join(out_dir, "DIM_TRAFFIC_FACTOR.xlsx")
        export_traffic_matrix_excel(edited_tf_df, xlsx_path)

        with open(xlsx_path, "rb") as f:
            st.download_button(
                label="⬇️ Tải Ma Trận Tắc Đường Excel (DIM_TRAFFIC_FACTOR.xlsx)",
                data=f,
                file_name="DIM_TRAFFIC_FACTOR.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_dim_traffic_horiz"
            )
    else:
        edited_tf_df = pd.DataFrame()

    st.divider()

    # ------------------------------------------------------------------------
    # 🏎️ PHẦN 5: MA TRẬN VẬN TỐC CƠ SỞ THEO LOẠI XE (HÀNG) × KHU VỰC (CỘT)
    # ------------------------------------------------------------------------
    st.markdown("### 🏎️ 5. Ma Trận Vận Tốc Cơ Sở Theo Loại Xe & Khu Vực (Từ Tab 1)")
    st.caption("🚚 *Hàng là danh sách xe lấy từ **Tab 1 (Fleet Master)**, cột là 4 nhóm Khu vực (`Đô thị lõi`, `Gần trục đường lớn`, `Đô thị vệ tinh`, `Ngoại thành`) — đơn vị: **km/h**.*")

    if "fleet_final_df" in st.session_state and not st.session_state["fleet_final_df"].empty:
        pool_df = st.session_state["fleet_final_df"].copy()
        st.success(f"✅ Đã đồng bộ **{len(pool_df)} xe** từ hạm đội xe Tab 1.")
    else:
        st.warning("⚠️ Chưa tìm thấy dữ liệu hạm đội xe từ **Tab 1 (Fleet Master)**. Đang hiển thị danh sách xe mẫu để cấu hình tạm.")
        pool_df = pd.DataFrame({
            "ID_VEHICLE":    ["VH02", "VH03", "VH05", "VH09"],
            "TRUCK":         ["Xe 3 Tấn", "Xe 2.5 Tấn", "Xe 800 Kg", "Xe Van 100 Kg"],
            "MAX_WEIGHT_KG": [3000.0, 2500.0, 800.0, 100.0],
            "MAX_VOLUME_M3": [20.0, 15.0, 5.0, 1.0]
        })

    speed_rows = []
    for _, row in pool_df.iterrows():
        vid = str(row.get("ID_VEHICLE", "")).strip()
        if not vid:
            continue
        w_kg = pd.to_numeric(row.get("MAX_WEIGHT_KG", 0), errors="coerce") or 0.0
        v_m3 = pd.to_numeric(row.get("MAX_VOLUME_M3", 0), errors="coerce") or 0.0
        s_core, s_art, s_sat, s_sub = suggest_zone_speeds(float(w_kg))
        speed_rows.append({
            "ID_VEHICLE":    vid,
            "TRUCK":         str(row.get("TRUCK", "Xe tải tiêu chuẩn")).strip(),
            "MAX_WEIGHT_KG": float(w_kg),
            "MAX_VOLUME_M3": float(v_m3),
            "SPD_CORE":      s_core,
            "SPD_ARTERIAL":  s_art,
            "SPD_SATELLITE": s_sat,
            "SPD_SUBURBAN":  s_sub
        })

    df_speed_init = pd.DataFrame(speed_rows)

    edited_speed_df = st.data_editor(
        df_speed_init,
        num_rows="fixed",
        use_container_width=True,
        disabled=["ID_VEHICLE", "TRUCK", "MAX_WEIGHT_KG", "MAX_VOLUME_M3"],
        column_config={
            "ID_VEHICLE":    st.column_config.TextColumn("🆔 Mã Xe", pinned=True),
            "TRUCK":         st.column_config.TextColumn("🚚 Loại Xe", pinned=True),
            "MAX_WEIGHT_KG": st.column_config.NumberColumn("⚖️ Trọng Tải (kg)", format="%.0f"),
            "MAX_VOLUME_M3": st.column_config.NumberColumn("📦 Thể Tích (m³)", format="%.1f"),
            "SPD_CORE":      st.column_config.NumberColumn("🏙️ Đô thị lõi (km/h)", min_value=5.0, max_value=120.0, step=1.0, format="%.0f", required=True),
            "SPD_ARTERIAL":  st.column_config.NumberColumn("🛣️ Gần trục đường lớn (km/h)", min_value=5.0, max_value=120.0, step=1.0, format="%.0f", required=True),
            "SPD_SATELLITE": st.column_config.NumberColumn("🏘️ Đô thị vệ tinh (km/h)", min_value=5.0, max_value=120.0, step=1.0, format="%.0f", required=True),
            "SPD_SUBURBAN":  st.column_config.NumberColumn("🌾 Ngoại thành (km/h)", min_value=5.0, max_value=120.0, step=1.0, format="%.0f", required=True),
        },
        key="fleet_zone_speed_matrix_editor"
    )

    out_dir = "output_pre_routing"
    os.makedirs(out_dir, exist_ok=True)
    speed_xlsx_path = os.path.join(out_dir, "DIM_VEHICLE_SPEED.xlsx")
    export_vehicle_speed_matrix_excel(edited_speed_df, speed_xlsx_path)

    with open(speed_xlsx_path, "rb") as f:
        st.download_button(
            label="⬇️ Tải Ma Trận Vận Tốc Cơ Sở Excel (DIM_VEHICLE_SPEED.xlsx)",
            data=f,
            file_name="DIM_VEHICLE_SPEED.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_dim_vehicle_speed_matrix"
        )

    # ------------------------------------------------------------------------
    # 🔑 ĐÓNG GÓI LƯU CẤU HÌNH VÀO SESSION STATE CỦA HỆ THỐNG
    # ------------------------------------------------------------------------
    export_records = []
    if not edited_tf_df.empty:
        clean_records_df = edited_tf_df.drop(columns=["KIỂM_TRA"], errors="ignore").copy()
        clean_records_df["ZONE"] = clean_records_df["ZONE"].str.replace(r"^[^\wÀ-ỹ]+\s*", "", regex=True)
        export_records = clean_records_df.to_dict(orient="records")

    st.session_state["pre_routing_config"] = {
        "constraint_mode": constraint_mode,
        "shifts": shifts_data,
        "split_time": split_time,
        "traffic_matrix": export_records,
        "fleet_speed_matrix": edited_speed_df.to_dict(orient="records") if not edited_speed_df.empty else []
    }
    st.divider()
    st.success("✅ Toàn bộ cấu hình Pre-Routing, Ma trận tắc đường & Ma trận vận tốc theo khu vực đã được lưu!")
