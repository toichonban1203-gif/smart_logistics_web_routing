# -*- coding: utf-8 -*-
import os
import io
import json
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz
from modules.common_utils import parse_num
# ============================================================================
# ⚙️ 1. CẤU HÌNH SCHEMA CHUẨN & FIELD MAPPING CHO PRODUCT
# ============================================================================
PRODUCT_FIELDS_CUBE = {
    "ID_PRODUCT": ["mã sản phẩm", "product id", "sku", "item code", "mã sp", "code", "id_product", "id product"],
    "PRODUCT":    ["tên sản phẩm", "product name", "item name", "tên sp", "name", "product", "sản phẩm"],
    "LENGTH":     ["dài", "length", "chiều dài", "length_m", "dài (m)"],
    "WIDTH":      ["rộng", "width", "chiều rộng", "width_m", "rộng (m)"],
    "HEIGHT":     ["cao", "height", "chiều cao", "height_m", "cao (m)"],
    "WEIGHT_KG":  ["trọng lượng", "weight", "kg", "khối lượng", "weight_kg", "trọng lượng kg"],
    "VOLUME_M3":  ["thể tích", "volume", "m3", "cbm", "max volume", "volume_m3", "thể tích m3"]
}
PRODUCT_FIELDS_WEIGHT = {
    "ID_PRODUCT": ["mã sản phẩm", "product id", "sku", "item code", "mã sp", "code", "id_product", "id product"],
    "PRODUCT":    ["tên sản phẩm", "product name", "item name", "tên sp", "name", "product", "sản phẩm"],
    "VOLUME_M3":  ["thể tích nén", "thể tích", "volume", "m3", "cbm", "volume_m3", "thể tích m3", "compressed volume"],
    "WEIGHT_KG":  ["trọng lượng", "weight", "kg", "khối lượng", "weight_kg", "trọng lượng kg"]
}
# ============================================================================
# 🛠️ 2. HÀM CHUẨN HÓA & TÍNH TOÁN THỂ TÍCH TỰ ĐỘNG
# ============================================================================
def process_product_record(rec: dict, is_cube_out: bool) -> dict:
    out = {}
    out["ID_PRODUCT"] = str(rec.get("ID_PRODUCT", "")).strip() if rec.get("ID_PRODUCT") else ""
    out["PRODUCT"]    = str(rec.get("PRODUCT", "")).strip() if rec.get("PRODUCT") else "Sản phẩm chưa đặt tên"
    out["CARGO_TYPE"] = "Cube Out" if is_cube_out else "Weight Out"
    out["WEIGHT_KG"]  = round(parse_num(rec.get("WEIGHT_KG")), 3)
    if is_cube_out:
        length_m = parse_num(rec.get("LENGTH"))
        width_m  = parse_num(rec.get("WIDTH"))
        height_m = parse_num(rec.get("HEIGHT"))
        out["LENGTH"] = round(length_m, 3)
        out["WIDTH"]  = round(width_m, 3)
        out["HEIGHT"] = round(height_m, 3)
        # Ưu tiên tính Dài x Rộng x Cao; nếu người dùng có nhập sẵn VOLUME_M3 thì lấy theo input
        vol_input = parse_num(rec.get("VOLUME_M3"))
        if length_m > 0 and width_m > 0 and height_m > 0:
            out["VOLUME_M3"] = round(length_m * width_m * height_m, 4)
        else:
            out["VOLUME_M3"] = round(vol_input, 4)
    else:
        # Chế độ Weight Out: Không dùng 3 chiều, lấy trực tiếp thể tích nén
        out["LENGTH"]    = 0.0
        out["WIDTH"]     = 0.0
        out["HEIGHT"]    = 0.0
        out["VOLUME_M3"] = round(parse_num(rec.get("VOLUME_M3")), 4)
    return out
def validate_product(df: pd.DataFrame, is_cube_out: bool) -> pd.DataFrame:
    out = df.copy()
    dup_id = out["ID_PRODUCT"].astype(str).duplicated(keep=False)
    msgs = []
    for i, row in out.iterrows():
        errs = []
        if not str(row.get("ID_PRODUCT", "")).strip():
            errs.append("Thiếu ID_PRODUCT")
        if dup_id.iloc[i] and str(row.get("ID_PRODUCT", "")).strip():
            errs.append("Trùng ID_PRODUCT")
        if row.get("WEIGHT_KG", 0) <= 0:
            errs.append("WEIGHT_KG phải > 0")
        if is_cube_out:
            if row.get("LENGTH", 0) <= 0 or row.get("WIDTH", 0) <= 0 or row.get("HEIGHT", 0) <= 0:
                errs.append("Cube Out bắt buộc đủ Dài, Rộng, Cao > 0")
            if row.get("VOLUME_M3", 0) <= 0:
                errs.append("VOLUME_M3 phải > 0")
        else:
            if row.get("VOLUME_M3", 0) <= 0:
                errs.append("Weight Out bắt buộc Thể tích nén (VOLUME_M3) > 0")
        msgs.append("❌ " + "; ".join(errs) if errs else "✅ Hợp lệ")
    out["KIỂM_TRA"] = msgs
    return out
# ============================================================================
# 🖥️ 3. GIAO DIỆN NHẬP DỮ LIỆU SẢN PHẨM (PRODUCT MASTER DATA)
# ============================================================================
def render_product_input_section():
    st.subheader("📦 3. Nhập Dữ Liệu Sản Phẩm (Product Master Data)")
    # Dropdown chọn đặc tính lô hàng
    cargo_mode = st.selectbox(
        "⚖️ Chọn đặc tính nhóm hàng hóa (Tối ưu xếp dỡ):",
        options=[
            "📦 Cube Out (Hàng cồng kềnh - Quét kỹ Dài × Rộng × Cao)",
            "🏋️ Weight Out (Hàng nặng - Chỉ cần Thể tích nén & Khối lượng)"
        ],
        key="prod_cargo_type"
    )
    is_cube_out = "Cube Out" in cargo_mode
    if is_cube_out:
        st.caption("📏 *Chế độ Cube Out: Hệ thống yêu cầu đủ 3 kích thước Dài, Rộng, Cao (đơn vị Mét) để tính thể tích chiếm chỗ.*")
        seed_product = pd.DataFrame({
            "ID_PRODUCT": ["SKU_01", "SKU_02", "SKU_03"],
            "PRODUCT":    ["Ghế Sofa Gỗ", "Tủ Lạnh 2 Cánh", "Bàn Làm Việc"],
            "LENGTH":     [1.20, 0.75, 1.40],
            "WIDTH":      [0.80, 0.70, 0.60],
            "HEIGHT":     [0.90, 1.80, 0.75],
            "WEIGHT_KG":  [25.0, 85.0, 30.0]
        })
        editor_col_config = {
            "LENGTH": st.column_config.NumberColumn("Chiều Dài (m)*", min_value=0.0, step=0.01, required=True),
            "WIDTH": st.column_config.NumberColumn("Chiều Rộng (m)*", min_value=0.0, step=0.01, required=True),
            "HEIGHT": st.column_config.NumberColumn("Chiều Cao (m)*", min_value=0.0, step=0.01, required=True),
            "WEIGHT_KG": st.column_config.NumberColumn("Trọng lượng 1 Unit (kg)", min_value=0.0, step=0.1)
        }
        active_fields = PRODUCT_FIELDS_CUBE
    else:
        st.caption("🗜️ *Chế độ Weight Out: Bỏ qua kích thước 3 chiều, chỉ cần nhập Thể tích nén (m³) và Trọng lượng (kg).*")
        seed_product = pd.DataFrame({
            "ID_PRODUCT": ["SKU_W01", "SKU_W02", "SKU_W03"],
            "PRODUCT":    ["Cuộn Thép Cán Nguội", "Bao Xi Măng 50kg", "Thùng Linh Kiện Kim Loại"],
            "VOLUME_M3":  [0.150, 0.035, 0.080],
            "WEIGHT_KG":  [500.0, 50.0, 120.0]
        })
        editor_col_config = {
            "VOLUME_M3": st.column_config.NumberColumn("Thể tích nén 1 Unit (m³)*", min_value=0.0, step=0.001, required=True),
            "WEIGHT_KG": st.column_config.NumberColumn("Trọng lượng 1 Unit (kg)*", min_value=0.0, step=0.1, required=True)
        }
        active_fields = PRODUCT_FIELDS_WEIGHT
    mode = st.radio(
        "Phương thức nhập dữ liệu Sản phẩm:",
        ["✍️ Nhập trực tiếp (Data Editor)", "📂 Upload file Excel/CSV/JSON"],
        horizontal=True,
        key="prod_input_mode"
    )
    raw_df = None
    if mode == "✍️ Nhập trực tiếp (Data Editor)":
        st.markdown("##### 📝 Chỉnh sửa thông tin sản phẩm trực tiếp:")
        raw_df = st.data_editor(
            seed_product,
            num_rows="dynamic",
            column_config=editor_col_config,
            key=f"prod_editor_{'cube' if is_cube_out else 'weight'}"
        )
    else:
        st.markdown("##### 📂 Upload file sản phẩm từ máy tính:")
        uploaded_file = st.file_uploader("Chọn file sản phẩm (xlsx, xls, csv, json)", type=["xlsx", "xls", "csv", "json"], key="prod_upload")
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".json"):
                    raw_df = pd.read_json(uploaded_file)
                else:
                    raw_df = pd.read_excel(uploaded_file)
                st.caption(f"📄 Tìm thấy `{len(raw_df)}` dòng dữ liệu sản phẩm từ file.")
            except Exception as e:
                st.error(f"❌ Lỗi đọc file: {e}")
    # ============================================================================
    # 🔍 ÁNH XẠ CỘT SEMANTIC MAPPING THEO CHẾ ĐỘ ĐÃ CHỌN
    # ============================================================================
    if raw_df is not None and not raw_df.empty:
        st.divider()
        st.markdown("### 🔍 Quét & Ánh Xạ Cột Sản Phẩm Chuẩn Hóa")
        if is_cube_out:
            st.info("💡 Đang quét ở chế độ **Cube Out**: Vui lòng đảm bảo khớp đủ 3 cột `LENGTH`, `WIDTH`, `HEIGHT` (đơn vị Mét).")
        else:
            st.info("💡 Đang quét ở chế độ **Weight Out**: Chỉ cần khớp `VOLUME_M3` (thể tích nén) và `WEIGHT_KG` (khối lượng).")
        input_cols = ["-- Bỏ qua / Không sử dụng --"] + [str(c) for c in raw_df.columns]
        chosen_mapping = {}
        cols_ui = st.columns(3)
        for i, (target_field, aliases) in enumerate(active_fields.items()):
            best_match = "-- Bỏ qua / Không sử dụng --"
            best_score = 0
            for col in raw_df.columns:
                score = max(fuzz.token_set_ratio(str(col).lower(), a.lower()) for a in aliases + [target_field])
                if score > best_score and score > 40:
                    best_score = score
                    best_match = str(col)
            with cols_ui[i % 3]:
                chosen_mapping[target_field] = st.selectbox(
                    f"Cột chuẩn `{target_field}` gán từ:",
                    options=input_cols,
                    index=input_cols.index(best_match) if best_match in input_cols else 0,
                    key=f"select_map_prod_{'cube' if is_cube_out else 'weight'}_{target_field}"
                )
        # ============================================================================
        # 🚀 CHUẨN HÓA & TÍNH THỂ TÍCH M3
        # ============================================================================
        st.divider()
        if st.button("🚀 Chuẩn Hóa & Tính Thể Tích Sản Phẩm", type="primary", key="btn_process_prod"):
            processed_rows = []
            for _, row in raw_df.iterrows():
                rec = {}
                for target_field, mapped_col in chosen_mapping.items():
                    if mapped_col != "-- Bỏ qua / Không sử dụng --" and mapped_col in raw_df.columns:
                        rec[target_field] = row[mapped_col]
                    else:
                        rec[target_field] = None
                processed_rows.append(process_product_record(rec, is_cube_out=is_cube_out))
            final_df = validate_product(pd.DataFrame(processed_rows), is_cube_out=is_cube_out)
            st.session_state["prod_final_df"] = final_df
            st.session_state["prod_is_cube"] = is_cube_out
    # ============================================================================
    # 📋 BẢNG OUTPUT SẢN PHẨM & NÚT TẢI DIM_PRODUCT.XLSX
    # ============================================================================
    if "prod_final_df" in st.session_state:
        st.markdown("### 📋 Danh Sách Sản Phẩm Đã Chuẩn Hóa (Cho phép kiểm tra & sửa lại số liệu)")
        saved_is_cube = st.session_state.get("prod_is_cube", True)
        display_cols = (
            ["ID_PRODUCT", "PRODUCT", "CARGO_TYPE", "LENGTH", "WIDTH", "HEIGHT", "VOLUME_M3", "WEIGHT_KG", "KIỂM_TRA"]
            if saved_is_cube
            else ["ID_PRODUCT", "PRODUCT", "CARGO_TYPE", "VOLUME_M3", "WEIGHT_KG", "KIỂM_TRA"]
        )
        edited_final_df = st.data_editor(
            st.session_state["prod_final_df"],
            num_rows="dynamic",
            column_order=display_cols,
            key="prod_final_editor"
        )
        # Xuất file DIM_PRODUCT.xlsx (Giữ nguyên schema chuẩn đầy đủ cột để đồng bộ với các module sau)
        out_dir = "output_product"
        os.makedirs(out_dir, exist_ok=True)
        xlsx_path = os.path.join(out_dir, "DIM_PRODUCT.xlsx")
        export_cols = ["ID_PRODUCT", "PRODUCT", "CARGO_TYPE", "LENGTH", "WIDTH", "HEIGHT", "VOLUME_M3", "WEIGHT_KG"]
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            edited_final_df.reindex(columns=export_cols).to_excel(
                writer, sheet_name="DIM_PRODUCT", index=False
            )
        with open(xlsx_path, "rb") as f:
            st.download_button(
                label="⬇️ Tải file chốt DIM_PRODUCT.xlsx",
                data=f,
                file_name="DIM_PRODUCT.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_dim_product"
            )
        st.success("✅ Đã ghi nhận và sẵn sàng lưu file `output_product/DIM_PRODUCT.xlsx`!")
