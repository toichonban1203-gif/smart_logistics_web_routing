# -*- coding: utf-8 -*-
import os
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz

# ============================================================================
# ⚙️ 1. CẤU HÌNH SCHEMA CHUẨN & FIELD MAPPING CHO HỆ SỐ TẮC ĐƯỜNG
# ============================================================================
TRAFFIC_FIELDS = {
    "WARD":         ["phường", "xã", "phường/xã", "ward", "commune", "địa bàn", "tên phường"],
    "ZONE":         ["khu vực", "vùng", "zone", "area", "loại khu vực", "phân vùng"],
    "DAY_OF_WEEK":  ["thứ", "ngày", "ngày trong tuần", "day", "day of week", "weekday", "thứ trong tuần"],
    "CA_SOM":       ["ca sớm", "sáng sớm", "early", "morning", "ca_som", "hệ số ca sớm"],
    "CA_TRUA":      ["ca trưa", "buổi trưa", "noon", "midday", "ca_trua", "hệ số ca trưa"],
    "CA_CHIEU":     ["ca chiều", "buổi chiều", "afternoon", "ca_chieu", "hệ số ca chiều"],
    "CA_CHAP_TOI":  ["ca chập tối", "chập tối", "chiều tối", "tối", "evening", "dusk", "ca_chap_toi", "hệ số ca chập tối"]
}

ZONE_OPTIONS = [
    "🏙️ Nội đô",
    "🛣️ Gần trục đường lớn",
    "🏘️ Đô thị vệ tinh",
    "🌾 Ngoại thành"
]

DAY_OPTIONS = [
    "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"
]

# ============================================================================
# 🛠️ 2. HÀM CHUẨN HÓA & VALIDATE DỮ LIỆU TẮC ĐƯỜNG
# ============================================================================
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
    return "🏙️ Nội đô"

def normalize_day(d_raw: str) -> str:
    d = str(d_raw).lower().strip()
    if "2" in d or "mon" in d: return "Thứ 2"
    if "3" in d or "tue" in d: return "Thứ 3"
    if "4" in d or "wed" in d: return "Thứ 4"
    if "5" in d or "thu" in d: return "Thứ 5"
    if "6" in d or "fri" in d: return "Thứ 6"
    if "7" in d or "sat" in d: return "Thứ 7"
    if "nhật" in d or "nhat" in d or "cn" in d or "sun" in d or "8" in d: return "Chủ Nhật"
    return "Thứ 2"

def process_traffic_record(rec: dict) -> dict:
    return {
        "WARD":        str(rec.get("WARD", "")).strip() if rec.get("WARD") else "",
        "ZONE":        normalize_zone(rec.get("ZONE", "")),
        "DAY_OF_WEEK": normalize_day(rec.get("DAY_OF_WEEK", "")),
        "CA_SOM":      parse_factor(rec.get("CA_SOM")),
        "CA_TRUA":     parse_factor(rec.get("CA_TRUA")),
        "CA_CHIEU":    parse_factor(rec.get("CA_CHIEU")),
        "CA_CHAP_TOI": parse_factor(rec.get("CA_CHAP_TOI"))
    }

def validate_traffic(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    dup_key = out.duplicated(subset=["WARD", "DAY_OF_WEEK"], keep=False)
    msgs = []

    for i, row in out.iterrows():
        errs = []
        if not str(row.get("WARD", "")).strip():
            errs.append("Thiếu tên Phường")
        if dup_key.iloc[i] and str(row.get("WARD", "")).strip():
            errs.append("Trùng Phường + Thứ")
        for col in ["CA_SOM", "CA_TRUA", "CA_CHIEU", "CA_CHAP_TOI"]:
            if row.get(col, 0) < 1.0:
                errs.append(f"{col} phải >= 1.0")
        msgs.append("❌ " + "; ".join(errs) if errs else "✅ Hợp lệ")

    out["KIỂM_TRA"] = msgs
    return out

def suggest_base_speed(weight_kg: float) -> float:
    """Gợi ý vận tốc cơ sở (km/h) dựa trên tải trọng xe"""
    if weight_kg <= 1500:
        return 40.0
    elif weight_kg <= 3500:
        return 35.0
    return 30.0

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
    st.caption("🛠️ *Thiết lập các quy định về hàng hóa, ca làm việc, thời điểm kiểm tra xe, hệ số tắc đường và vận tốc cơ sở trước khi định tuyến.*")
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
    # 🚦 PHẦN 4: HỆ SỐ TẮC ĐƯỜNG THEO PHƯỜNG, KHU VỰC, 4 CA & 7 NGÀY (IMPORT + MAPPING)
    # ------------------------------------------------------------------------
    st.markdown("### 🚦 4. Bảng Hệ Số Tắc Đường Theo Phường, Khu Vực & Khung Ca")
    st.caption("📍 *Hỗ trợ đẩy file Excel/CSV/JSON và tự động quét ánh xạ theo Phường, 4 nhóm Khu vực, 4 Ca trong ngày và 7 Ngày trong tuần.*")

    seed_traffic = pd.DataFrame({
        "WARD":        ["Phường Tràng Tiền", "Phường Dịch Vọng", "Phường Dương Nội", "Xã Đông Anh"],
        "ZONE":        ["🏙️ Nội đô", "🛣️ Gần trục đường lớn", "🏘️ Đô thị vệ tinh", "🌾 Ngoại thành"],
        "DAY_OF_WEEK": ["Thứ 2", "Thứ 2", "Thứ 6", "Chủ Nhật"],
        "CA_SOM":      [1.85, 1.60, 1.30, 1.10],
        "CA_TRUA":     [1.35, 1.25, 1.10, 1.05],
        "CA_CHIEU":    [1.65, 1.50, 1.25, 1.10],
        "CA_CHAP_TOI": [2.10, 1.80, 1.45, 1.15]
    })

    mode = st.radio(
        "Phương thức nhập dữ liệu Hệ số tắc đường:",
        ["📂 Upload file Excel/CSV/JSON", "✍️ Nhập trực tiếp (Data Editor)"],
        horizontal=True,
        key="traffic_input_mode"
    )

    raw_df = None
    if mode == "✍️ Nhập trực tiếp (Data Editor)":
        st.markdown("##### 📝 Chỉnh sửa bảng hệ số trực tiếp:")
        raw_df = st.data_editor(
            seed_traffic,
            num_rows="dynamic",
            column_config={
                "WARD":        st.column_config.TextColumn("📍 Phường / Xã", required=True),
                "ZONE":        st.column_config.SelectboxColumn("🗺️ Khu vực", options=ZONE_OPTIONS, required=True),
                "DAY_OF_WEEK": st.column_config.SelectboxColumn("📅 Ngày trong tuần", options=DAY_OPTIONS, required=True),
                "CA_SOM":      st.column_config.NumberColumn("🌅 Ca Sớm", min_value=1.0, max_value=5.0, step=0.05),
                "CA_TRUA":     st.column_config.NumberColumn("☀️ Ca Trưa", min_value=1.0, max_value=5.0, step=0.05),
                "CA_CHIEU":    st.column_config.NumberColumn("🌤️ Ca Chiều", min_value=1.0, max_value=5.0, step=0.05),
                "CA_CHAP_TOI": st.column_config.NumberColumn("🌆 Ca Chập Tối", min_value=1.0, max_value=5.0, step=0.05),
            },
            key="traffic_editor"
        )
    else:
        st.markdown("##### 📂 Upload file hệ số tắc đường từ máy tính:")
        uploaded_file = st.file_uploader(
            "Chọn file hệ số tắc đường (xlsx, xls, csv, json)",
            type=["xlsx", "xls", "csv", "json"],
            key="traffic_upload"
        )
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".json"):
                    raw_df = pd.read_json(uploaded_file)
                else:
                    raw_df = pd.read_excel(uploaded_file)
                st.caption(f"📄 Tìm thấy `{len(raw_df)}` dòng dữ liệu tắc đường từ file.")
            except Exception as e:
                st.error(f"❌ Lỗi đọc file: {e}")

    # ============================================================================
    # 🔍 ÁNH XẠ CỘT SEMANTIC MAPPING CHO BẢNG TẮC ĐƯỜNG
    # ============================================================================
    if raw_df is not None and not raw_df.empty:
        st.divider()
        st.markdown("#### 🔍 Quét & Ánh Xạ Cột Hệ Số Tắc Đường Chuẩn Hóa")
        st.info("💡 Hệ thống tự động ghép cột từ file của cậu. Có thể chọn lại ở các ô bên dưới nếu tên cột trong file khác biệt.")

        input_cols = ["-- Bỏ qua / Không sử dụng --"] + [str(c) for c in raw_df.columns]
        chosen_mapping = {}
        cols_ui = st.columns(4)

        field_labels = {
            "WARD":        "📍 Phường (WARD)",
            "ZONE":        "🗺️ Khu vực (ZONE)",
            "DAY_OF_WEEK": "📅 Ngày trong tuần",
            "CA_SOM":      "🌅 Ca Sớm",
            "CA_TRUA":     "☀️ Ca Trưa",
            "CA_CHIEU":    "🌤️ Ca Chiều",
            "CA_CHAP_TOI": "🌆 Ca Chập Tối"
        }

        for i, (target_field, aliases) in enumerate(TRAFFIC_FIELDS.items()):
            best_match = "-- Bỏ qua / Không sử dụng --"
            best_score = 0
            for col in raw_df.columns:
                score = max(fuzz.token_set_ratio(str(col).lower(), a.lower()) for a in aliases + [target_field])
                if score > best_score and score > 40:
                    best_score = score
                    best_match = str(col)
            with cols_ui[i % 4]:
                chosen_mapping[target_field] = st.selectbox(
                    f"{field_labels[target_field]} gán từ:",
                    options=input_cols,
                    index=input_cols.index(best_match) if best_match in input_cols else 0,
                    key=f"select_map_tf_{target_field}"
                )

        st.divider()
        if st.button("🚀 Quét & Tổng Hợp Bảng Hệ Số Tắc Đường", type="primary", key="btn_process_traffic"):
            processed_rows = []
            for _, row in raw_df.iterrows():
                rec = {}
                for target_field, mapped_col in chosen_mapping.items():
                    if mapped_col != "-- Bỏ qua / Không sử dụng --" and mapped_col in raw_df.columns:
                        rec[target_field] = row[mapped_col]
                    else:
                        rec[target_field] = None
                processed_rows.append(process_traffic_record(rec))

            final_tf_df = validate_traffic(pd.DataFrame(processed_rows))
            st.session_state["traffic_final_df"] = final_tf_df

    # ============================================================================
    # 📋 BẢNG TỔNG HỢP ĐẸP & XUẤT FILE EXCEL DIM_TRAFFIC_FACTOR.XLSX
    # ============================================================================
    if "traffic_final_df" in st.session_state and not st.session_state["traffic_final_df"].empty:
        st.markdown("#### 📊 Bảng Tổng Hợp Hệ Số Tắc Đường Đã Chuẩn Hóa")

        df_tf = st.session_state["traffic_final_df"]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("📍 Tổng Số Phường", f"{df_tf['WARD'].nunique()} phường")
        k2.metric("📋 Tổng Bản Ghi", f"{len(df_tf)} dòng")
        max_tf = df_tf[["CA_SOM", "CA_TRUA", "CA_CHIEU", "CA_CHAP_TOI"]].max().max()
        avg_tf = df_tf[["CA_SOM", "CA_TRUA", "CA_CHIEU", "CA_CHAP_TOI"]].mean().mean()
        k3.metric("🔥 Hệ Số Cao Nhất", f"{max_tf:.2f}x")
        k4.metric("⚖️ Hệ Số Trung Bình", f"{avg_tf:.2f}x")

        edited_tf_df = st.data_editor(
            df_tf,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "WARD":        st.column_config.TextColumn("📍 Phường / Xã"),
                "ZONE":        st.column_config.SelectboxColumn("🗺️ Phân Loại Khu Vực", options=ZONE_OPTIONS),
                "DAY_OF_WEEK": st.column_config.SelectboxColumn("📅 Thứ Trong Tuần", options=DAY_OPTIONS),
                "CA_SOM":      st.column_config.NumberColumn("🌅 Ca Sớm", format="%.2f"),
                "CA_TRUA":     st.column_config.NumberColumn("☀️ Ca Trưa", format="%.2f"),
                "CA_CHIEU":    st.column_config.NumberColumn("🌤️ Ca Chiều", format="%.2f"),
                "CA_CHAP_TOI": st.column_config.NumberColumn("🌆 Ca Chập Tối", format="%.2f"),
                "KIỂM_TRA":    st.column_config.TextColumn("🛡️ Trạng Thái")
            },
            column_order=["WARD", "ZONE", "DAY_OF_WEEK", "CA_SOM", "CA_TRUA", "CA_CHIEU", "CA_CHAP_TOI", "KIỂM_TRA"],
            key="traffic_final_editor"
        )

        out_dir = "output_pre_routing"
        os.makedirs(out_dir, exist_ok=True)
        xlsx_path = os.path.join(out_dir, "DIM_TRAFFIC_FACTOR.xlsx")

        export_df = edited_tf_df.drop(columns=["KIỂM_TRA"], errors="ignore").copy()
        export_df["ZONE"] = export_df["ZONE"].str.replace(r"^[^\wÀ-ỹ]+\s*", "", regex=True)

        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            export_df.to_excel(writer, sheet_name="DIM_TRAFFIC_FACTOR", index=False)

        with open(xlsx_path, "rb") as f:
            st.download_button(
                label="⬇️ Tải bảng tổng hợp Excel (DIM_TRAFFIC_FACTOR.xlsx)",
                data=f,
                file_name="DIM_TRAFFIC_FACTOR.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_dim_traffic"
            )
    else:
        export_df = pd.DataFrame()

    st.divider()

    # ------------------------------------------------------------------------
    # 🏎️ PHẦN 5: THIẾT LẬP VẬN TỐC CƠ SỞ TỪ OUTPUT POOL XE (TAB 1)
    # ------------------------------------------------------------------------
    st.markdown("### 🏎️ 5. Thiết Lập Vận Tốc Cơ Sở Theo Hạm Đội Xe (Từ Tab 1)")
    st.caption("🚚 *Hệ thống tự động kéo danh sách xe từ **Tab 1 (Fleet Master)** để cấu hình vận tốc di chuyển tiêu chuẩn (km/h) trước khi nhân hệ số tắc đường.*")

    if "fleet_final_df" in st.session_state and not st.session_state["fleet_final_df"].empty:
        pool_df = st.session_state["fleet_final_df"].copy()
        st.success(f"✅ Đã đồng bộ **{len(pool_df)} xe** từ hạm đội xe Tab 1.")
    else:
        st.warning("⚠️ Chưa tìm thấy dữ liệu hạm đội xe từ **Tab 1 (Fleet Master)**. Đang hiển thị danh sách xe mẫu để cấu hình tạm.")
        pool_df = pd.DataFrame({
            "ID_VEHICLE":    ["VEH_01", "VEH_02", "VEH_03"],
            "TRUCK":         ["Xe 1.25 Tấn", "Xe 2.5 Tấn", "Xe 5 Tấn"],
            "MAX_WEIGHT_KG": [1250.0, 2500.0, 5000.0],
            "MAX_VOLUME_M3": [8.0, 15.0, 24.0]
        })

    # Chuẩn bị bảng cấu hình vận tốc cơ sở
    speed_rows = []
    for _, row in pool_df.iterrows():
        vid = str(row.get("ID_VEHICLE", "")).strip()
        if not vid:
            continue
        w_kg = pd.to_numeric(row.get("MAX_WEIGHT_KG", 0), errors="coerce") or 0.0
        v_m3 = pd.to_numeric(row.get("MAX_VOLUME_M3", 0), errors="coerce") or 0.0
        speed_rows.append({
            "ID_VEHICLE":      vid,
            "TRUCK":           str(row.get("TRUCK", "Xe tải tiêu chuẩn")).strip(),
            "MAX_WEIGHT_KG":   float(w_kg),
            "MAX_VOLUME_M3":   float(v_m3),
            "BASE_SPEED_KMH":  suggest_base_speed(float(w_kg))
        })

    df_speed_init = pd.DataFrame(speed_rows)

    edited_speed_df = st.data_editor(
        df_speed_init,
        num_rows="fixed",
        use_container_width=True,
        disabled=["ID_VEHICLE", "TRUCK", "MAX_WEIGHT_KG", "MAX_VOLUME_M3"],
        column_config={
            "ID_VEHICLE":     st.column_config.TextColumn("🆔 Mã Xe"),
            "TRUCK":          st.column_config.TextColumn("🚚 Loại Xe"),
            "MAX_WEIGHT_KG":  st.column_config.NumberColumn("⚖️ Trọng Tải (kg)", format="%.1f"),
            "MAX_VOLUME_M3":  st.column_config.NumberColumn("📦 Thể Tích (m³)", format="%.2f"),
            "BASE_SPEED_KMH": st.column_config.NumberColumn(
                "⚡ Vận Tốc Cơ Sở (km/h)",
                min_value=5.0,
                max_value=120.0,
                step=1.0,
                format="%.1f",
                required=True,
                help="Vận tốc trung bình trong điều kiện giao thông thông thoáng (hệ số tắc đường = 1.0)"
            )
        },
        key="fleet_base_speed_editor"
    )

    # Xuất file Excel vận tốc cơ sở nếu cần
    out_dir = "output_pre_routing"
    os.makedirs(out_dir, exist_ok=True)
    speed_xlsx_path = os.path.join(out_dir, "DIM_VEHICLE_SPEED.xlsx")
    with pd.ExcelWriter(speed_xlsx_path, engine="openpyxl") as writer:
        edited_speed_df.to_excel(writer, sheet_name="DIM_VEHICLE_SPEED", index=False)

    with open(speed_xlsx_path, "rb") as f:
        st.download_button(
            label="⬇️ Tải bảng vận tốc cơ sở xe (DIM_VEHICLE_SPEED.xlsx)",
            data=f,
            file_name="DIM_VEHICLE_SPEED.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_dim_vehicle_speed"
        )

    # ------------------------------------------------------------------------
    # 🔑 ĐÓNG GÓI LƯU CẤU HÌNH VÀO SESSION STATE CỦA HỆ THỐNG
    # ------------------------------------------------------------------------
    st.session_state["pre_routing_config"] = {
        "constraint_mode": constraint_mode,
        "shifts": shifts_data,
        "split_time": split_time,
        "traffic_table": export_df.to_dict(orient="records") if not export_df.empty else [],
        "fleet_base_speeds": edited_speed_df.to_dict(orient="records") if not edited_speed_df.empty else []
    }
    st.divider()
    st.success("✅ Toàn bộ cấu hình Pre-Routing, Hệ số tắc đường & Vận tốc cơ sở đã được lưu vào hệ thống!")
