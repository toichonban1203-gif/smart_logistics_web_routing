# -*- coding: utf-8 -*-
import os
import io
import json
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz

# ============================================================================
# ⚙️ 1. CẤU HÌNH SCHEMA CHUẨN & FIELD MAPPING CHO PRODUCT
# ============================================================================

PRODUCT_FIELDS = {
    "ID_PRODUCT": ["mã sản phẩm", "product id", "sku", "item code", "mã sp", "code", "id_product", "id product"],
    "PRODUCT":    ["tên sản phẩm", "product name", "item name", "tên sp", "name", "product", "sản phẩm"],
    "LENGTH":     ["dài", "length", "chiều dài", "length_m", "dài (m)"],
    "WIDTH":      ["rộng", "width", "chiều rộng", "width_m", "rộng (m)"],
    "HEIGHT":     ["cao", "height", "chiều cao", "height_m", "cao (m)"],
    "VOLUME_M3":  ["thể tích", "volume", "m3", "cbm", "max volume", "volume_m3", "thể tích m3"],
    "WEIGHT_KG":  ["trọng lượng", "weight", "kg", "khối lượng", "weight_kg", "trọng lượng kg"]
}

PRODUCT_NUMERIC = ["LENGTH", "WIDTH", "HEIGHT", "VOLUME_M3", "WEIGHT_KG"]

# ============================================================================
# 🛠️ 2. HÀM CHUẨN HÓA & TÍNH TOÁN THỂ TÍCH TỰ ĐỘNG
# ============================================================================

def parse_num(val) -> float:
    if pd.isna(val) or val is None or str(val).strip() == "":
        return 0.0
    try:
        cleaned = pd.Series([str(val)]).str.replace(r"[^\d.-]", "", regex=True).iloc[0]
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0

def process_product_record(rec: dict) -> dict:
    out = {}
    out["ID_PRODUCT"] = str(rec.get("ID_PRODUCT", "")).strip() if rec.get("ID_PRODUCT") else ""
    out["PRODUCT"]    = str(rec.get("PRODUCT", "")).strip() if rec.get("PRODUCT") else "Sản phẩm chưa đặt tên"
    
    length_m = parse_num(rec.get("LENGTH"))
    width_m  = parse_num(rec.get("WIDTH"))
    height_m = parse_num(rec.get("HEIGHT"))
    
    out["LENGTH"]    = round(length_m, 3)
    out["WIDTH"]     = round(width_m, 3)
    out["HEIGHT"]    = round(height_m, 3)
    out["WEIGHT_KG"] = round(parse_num(rec.get("WEIGHT_KG")), 3)

    # Thể tích 1 Unit (m³): Nếu đã nhập thủ công VOLUME_M3 thì ưu tiên, không thì tự động tính Dài x Rộng x Cao
    vol_input = parse_num(rec.get("VOLUME_M3"))
    if vol_input > 0:
        out["VOLUME_M3"] = round(vol_input, 4)
    else:
        out["VOLUME_M3"] = round(length_m * width_m * height_m, 4)

    return out

def validate_product(df: pd.DataFrame) -> pd.DataFrame:
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
        if row.get("VOLUME_M3", 0) <= 0:
            errs.append("VOLUME_M3 phải > 0 (kiểm tra lại D x R x C)")
            
        msgs.append("❌ " + "; ".join(errs) if errs else "✅ Hợp lệ")
        
    out["KIỂM_TRA"] = msgs
    return out

# ============================================================================
# 🖥️ 3. GIAO DIỆN NHẬP DỮ LIỆU SẢN PHẨM (PRODUCT MASTER DATA)
# ============================================================================

def render_product_input_section():
    st.subheader("📦 3. Nhập Dữ Liệu Sản Phẩm (Product Master Data)")
    st.caption("📏 *Lưu ý: Tất cả kích thước Dài, Rộng, Cao đều quy đổi về đơn vị Mét (m).*")
    
    seed_product = pd.DataFrame({
        "ID_PRODUCT": ["SKU_01", "SKU_02", "SKU_03"],
        "PRODUCT":    ["Ghế Sofa Gỗ", "Tủ Lạnh 2 Cánh", "Bàn Làm Việc"],
        "LENGTH":     [1.20, 0.75, 1.40],
        "WIDTH":      [0.80, 0.70, 0.60],
        "HEIGHT":     [0.90, 1.80, 0.75],
        "VOLUME_M3":  [0.864, 0.945, 0.630],
        "WEIGHT_KG":  [25.0, 85.0, 30.0]
    })

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
            column_config={
                "LENGTH": st.column_config.NumberColumn("Chiềụ Dài (m)", min_value=0.0, step=0.01),
                "WIDTH": st.column_config.NumberColumn("Chiều Rộng (m)", min_value=0.0, step=0.01),
                "HEIGHT": st.column_config.NumberColumn("Chiều Cao (m)", min_value=0.0, step=0.01),
                "VOLUME_M3": st.column_config.NumberColumn("Thể tích 1 Unit (m³)", help="Để 0 hệ thống sẽ tự động tính = Dài x Rộng x Cao"),
                "WEIGHT_KG": st.column_config.NumberColumn("Trọng lượng 1 Unit (kg)", min_value=0.0, step=0.1)
            },
            key="prod_editor"
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
    # 🔍 ÁNH XẠ CỘT SEMANTIC MAPPING CHO SẢN PHẨM
    # ============================================================================
    if raw_df is not None and not raw_df.empty:
        st.divider()
        st.markdown("### 🔍 Quét & Ánh Xạ Cột Sản Phẩm Chuẩn Hóa")
        st.info("💡 Hệ thống tự động ánh xạ cột. Hãy đảm bảo các cột Dài, Rộng, Cao ở đơn vị Mét (m).")

        input_cols = ["-- Bỏ qua / Không sử dụng --"] + [str(c) for c in raw_df.columns]
        chosen_mapping = {}

        cols_ui = st.columns(3)
        for i, (target_field, aliases) in enumerate(PRODUCT_FIELDS.items()):
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
                    key=f"select_map_prod_{target_field}"
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
                processed_rows.append(process_product_record(rec))

            final_df = validate_product(pd.DataFrame(processed_rows))
            st.session_state["prod_final_df"] = final_df

    # ============================================================================
    # 📋 BẢNG OUTPUT SẢN PHẨM & NÚT TẢI DIM_PRODUCT.XLSX
    # ============================================================================
    if "prod_final_df" in st.session_state:
        st.markdown("### 📋 Danh Sách Sản Phẩm Đã Chuẩn Hóa (Cho phép kiểm tra & sửa lại số liệu)")
        
        edited_final_df = st.data_editor(
            st.session_state["prod_final_df"],
            num_rows="dynamic",
            column_order=["ID_PRODUCT", "PRODUCT", "LENGTH", "WIDTH", "HEIGHT", "VOLUME_M3", "WEIGHT_KG", "KIỂM_TRA"],
            key="prod_final_editor"
        )

        # Xuất file DIM_PRODUCT.xlsx
        out_dir = "output_product"
        os.makedirs(out_dir, exist_ok=True)
        xlsx_path = os.path.join(out_dir, "DIM_PRODUCT.xlsx")

        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            edited_final_df.drop(columns=["KIỂM_TRA"], errors="ignore").to_excel(
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
