# -*- coding: utf-8 -*-
import os
import io
import json
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz

# ============================================================================
# ⚙️ 1. CẤU HÌNH SCHEMA CHUẨN & FIELD MAPPING CHO FLEET
# ============================================================================

LICENSE_RANKS = {
    "A1": 1, "A2": 2, "A3": 3, "A4": 4,
    "B1": 5, "B2": 6, "C": 7,
    "D": 8, "E": 9,
    "FB2": 10, "FC": 11, "FD": 12, "FE": 13
}
LICENSE_LIST = list(LICENSE_RANKS.keys())

VEHICLE_FIELDS = {
    "ID_VEHICLE":     ["mã xe", "vehicle id", "vehicle code", "vehicle", "xe", "id xe", "truck id", "id_vehicle"],
    "TRUCK":          ["loại xe", "truck type", "truck", "nhóm xe", "tên xe", "vehicle type"],
    "MAX_WEIGHT_KG":  ["trọng tải", "trong tai", "weight", "payload", "khối lượng", "kg", "tấn", "max weight", "max_weight_kg"],
    "MAX_VOLUME_M3":  ["thể tích", "the tich", "volume", "m3", "cbm", "max volume", "max_volume_m3"],
    "FIXED_COST":     ["chi phí cố định", "fixed cost", "cost fix", "fixed_cost", "chi phí định phí"],
    "VARIABLE_COST":  ["chi phí biến đổi", "variable cost", "cost km", "variable_cost", "chi phí mỗi km"],
    "MAX_DISTANCE":   ["khoảng cách tối đa", "max distance", "quãng đường tối đa", "km tối đa", "max km", "max_distance"],
    "LICENSE":        ["bằng lái", "giấy phép lái xe", "bằng", "license", "loại bằng", "gplx", "min license"]
}

VEHICLE_NUMERIC = ["MAX_WEIGHT_KG", "MAX_VOLUME_M3", "FIXED_COST", "VARIABLE_COST", "MAX_DISTANCE"]

# ============================================================================
# 🛠️ 2. HÀM XỬ LÝ & VALIDATE DỮ LIỆU
# ============================================================================

def parse_num(val) -> float:
    if pd.isna(val) or val is None or str(val).strip() == "":
        return 0.0
    try:
        cleaned = pd.Series([str(val)]).str.replace(r"[^\d.-]", "", regex=True).iloc[0]
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0

def process_fleet_record(rec: dict) -> dict:
    out = {}
    out["ID_VEHICLE"] = str(rec.get("ID_VEHICLE", "")).strip() if rec.get("ID_VEHICLE") else ""
    out["TRUCK"]      = str(rec.get("TRUCK", "")).strip() if rec.get("TRUCK") else "Xe tải tiêu chuẩn"
    
    for f in VEHICLE_NUMERIC:
        out[f] = parse_num(rec.get(f))
        
    lic_raw = str(rec.get("LICENSE", "")).strip().upper()
    out["LICENSE"] = lic_raw if lic_raw in LICENSE_RANKS else "C"
    return out

def validate_fleet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    dup_id = out["ID_VEHICLE"].astype(str).duplicated(keep=False)
    msgs = []
    
    for i, row in out.iterrows():
        errs = []
        if not str(row.get("ID_VEHICLE", "")).strip():
            errs.append("Thiếu ID_VEHICLE")
        if dup_id.iloc[i] and str(row.get("ID_VEHICLE", "")).strip():
            errs.append("Trùng ID_VEHICLE")
        if row.get("MAX_WEIGHT_KG", 0) <= 0:
            errs.append("MAX_WEIGHT_KG phải > 0")
        if row.get("MAX_VOLUME_M3", 0) <= 0:
            errs.append("MAX_VOLUME_M3 phải > 0")
            
        msgs.append("❌ " + "; ".join(errs) if errs else "✅ Hợp lệ")
        
    out["KIỂM_TRA"] = msgs
    return out

# ============================================================================
# 🖥️ 3. GIAO DIỆN NHẬP DỮ LIỆU FLEET
# ============================================================================

def render_fleet_input_section():
    st.subheader("🚚 1. Nhập Dữ Liệu Hạm Đội Xe (Fleet Master Data)")
    
    seed_fleet = pd.DataFrame({
        "ID_VEHICLE":     ["VEH_01", "VEH_02", "VEH_03"],
        "TRUCK":          ["Xe 1.25 Tấn", "Xe 2.5 Tấn", "Xe 5 Tấn"],
        "MAX_WEIGHT_KG":  [1250.0, 2500.0, 5000.0],
        "MAX_VOLUME_M3":  [8.0, 15.0, 24.0],
        "FIXED_COST":     [300000.0, 450000.0, 700000.0],
        "VARIABLE_COST":  [4000.0, 5500.0, 8000.0],
        "MAX_DISTANCE":   [100.0, 120.0, 150.0],
        "LICENSE":        ["B2", "C", "C"]
    })

    mode = st.radio(
        "Phương thức nhập dữ liệu Xe:",
        ["✍️ Nhập trực tiếp (Data Editor)", "📂 Upload file Excel/CSV/JSON"],
        horizontal=True,
        key="fleet_input_mode"
    )

    raw_df = None

    if mode == "✍️ Nhập trực tiếp (Data Editor)":
        st.markdown("##### 📝 Chỉnh sửa bảng trực tiếp:")
        raw_df = st.data_editor(
            seed_fleet,
            num_rows="dynamic",
            column_config={
                "LICENSE": st.column_config.SelectboxColumn("Loại bằng tối thiểu", options=LICENSE_LIST, required=True),
                "MAX_WEIGHT_KG": st.column_config.NumberColumn("Tải trọng (kg)", min_value=0),
                "MAX_VOLUME_M3": st.column_config.NumberColumn("Thể tích (m³)", min_value=0),
            },
            key="fleet_editor"
        )
    else:
        st.markdown("##### 📂 Upload file từ máy tính:")
        uploaded_file = st.file_uploader("Chọn file xe (xlsx, xls, csv, json)", type=["xlsx", "xls", "csv", "json"], key="fleet_upload")
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".json"):
                    raw_df = pd.read_json(uploaded_file)
                else:
                    raw_df = pd.read_excel(uploaded_file)
                st.caption(f"📄 Tìm thấy `{len(raw_df)}` dòng dữ liệu từ file.")
            except Exception as e:
                st.error(f"❌ Lỗi đọc file: {e}")

    if raw_df is not None and not raw_df.empty:
        st.divider()
        st.markdown("### 🔍 Quét & Ánh Xạ Cột Chuẩn Hóa (Semantic Mapping)")
        st.info("💡 Hệ thống tự động đề xuất ghép cột. Cậu có thể chọn lại các cột bên dưới nếu muốn thay đổi.")

        input_cols = ["-- Bỏ qua / Không sử dụng --"] + [str(c) for c in raw_df.columns]
        chosen_mapping = {}

        cols_ui = st.columns(2)
        for i, (target_field, aliases) in enumerate(VEHICLE_FIELDS.items()):
            best_match = "-- Bỏ qua / Không sử dụng --"
            best_score = 0
            for col in raw_df.columns:
                score = max(fuzz.token_set_ratio(str(col).lower(), a.lower()) for a in aliases + [target_field])
                if score > best_score and score > 40:
                    best_score = score
                    best_match = str(col)

            with cols_ui[i % 2]:
                chosen_mapping[target_field] = st.selectbox(
                    f"Cột chuẩn `{target_field}` gán từ:",
                    options=input_cols,
                    index=input_cols.index(best_match) if best_match in input_cols else 0,
                    key=f"select_map_{target_field}"
                )

        st.divider()
        if st.button("🚀 Xử lý & Chuẩn Hóa Dữ Liệu Xe", type="primary", key="btn_process_fleet"):
            processed_rows = []
            for _, row in raw_df.iterrows():
                rec = {}
                for target_field, mapped_col in chosen_mapping.items():
                    if mapped_col != "-- Bỏ qua / Không sử dụng --" and mapped_col in raw_df.columns:
                        rec[target_field] = row[mapped_col]
                    else:
                        rec[target_field] = None
                processed_rows.append(process_fleet_record(rec))

            final_df = validate_fleet(pd.DataFrame(processed_rows))
            st.session_state["fleet_final_df"] = final_df

    if "fleet_final_df" in st.session_state:
        st.markdown("### 📋 Bảng Dữ Liệu Hạm Đội Xe Đã Chuẩn Hóa (Cho phép chỉnh sửa lần cuối)")
        
        edited_final_df = st.data_editor(
            st.session_state["fleet_final_df"],
            num_rows="dynamic",
            column_order=["ID_VEHICLE", "TRUCK", "MAX_WEIGHT_KG", "MAX_VOLUME_M3", "FIXED_COST", "VARIABLE_COST", "MAX_DISTANCE", "LICENSE", "KIỂM_TRA"],
            key="fleet_final_editor"
        )

        out_dir = "output_fleet"
        os.makedirs(out_dir, exist_ok=True)
        xlsx_path = os.path.join(out_dir, "DIM_VEHICLE.xlsx")

        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            edited_final_df.drop(columns=["KIỂM_TRA"], errors="ignore").to_excel(writer, sheet_name="DIM_VEHICLE", index=False)

        with open(xlsx_path, "rb") as f:
            st.download_button(
                label="⬇️ Tải file chốt DIM_VEHICLE.xlsx",
                data=f,
                file_name="DIM_VEHICLE.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_dim_vehicle"
            )
        st.success("✅ Đã ghi nhận và sẵn sàng lưu file `output_fleet/DIM_VEHICLE.xlsx`!")
