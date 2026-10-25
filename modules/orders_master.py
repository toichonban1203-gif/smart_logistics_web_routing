# -*- coding: utf-8 -*-
import os
import io
import json
import re
import datetime as dt
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz
from geopy.geocoders import ArcGIS

# Import hàm geocode và clean_address từ module warehouse nếu có
try:
    from modules.warehouse_master import clean_address, geocode_address
except Exception:
    def clean_address(addr):
        return str(addr).strip() if addr else ""
    def geocode_address(addr):
        return {"ok": False, "lat": None, "lng": None, "status": "— Chưa quét"}

# ============================================================================
# ⚙️ 1. CẤU HÌNH SCHEMA CHUẨN & FIELD MAPPING CHO ORDERS
# ============================================================================

ORDER_FIELDS = {
    "ORDER_ID":       ["mã đơn", "order id", "order code", "mã đơn hàng", "id_order", "order_id"],
    "ORDER_DATE":     ["ngày đặt", "order date", "order_date", "ngày tạo đơn"],
    "DELIVERY_DATE":  ["ngày giao", "delivery date", "delivery_date", "ngày cần giao", "ship date"],
    "LOADING_TIME":   ["thời gian bốc", "loading time", "loading_time", "bốc hàng (phút)"],
    "UNLOADING_TIME": ["thời gian dỡ", "unloading time", "unloading_time", "dỡ hàng (phút)"],
    "SHIFT":          ["ca", "shift", "kíp", "buổi", "ca giao", "ca làm việc"],
    "CUSTOMER_ID":    ["mã khách", "customer id", "customer_id", "mã kh"],
    "CUSTOMER_NAME":  ["tên khách", "customer name", "customer_name", "tên kh"],
    "TYPE":           ["loại đơn", "order type", "type", "loại khách", "channel", "b2b/b2c"],
    "LOCATION":       ["địa chỉ", "location", "address", "địa chỉ giao", "điểm giao"],
    "PRODUCT_ID":     ["mã sản phẩm", "product id", "sku", "mã sp", "product_id"],
    "QUANTITY":       ["số lượng", "qty", "quantity", "units", "sl"]
}

SHIFT_OPTIONS = ["Ca Sáng", "Ca Chiều", "Ca Đêm"]

# ============================================================================
# 🛠️ 2. HÀM CHUẨN HÓA & TRA CỨU TÍNH TOÁN THEO SẢN PHẨM
# ============================================================================

def parse_num(val) -> float:
    if pd.isna(val) or val is None or str(val).strip() == "":
        return 0.0
    try:
        cleaned = pd.Series([str(val)]).str.replace(r"[^\d.-]", "", regex=True).iloc[0]
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0

def parse_date(dstr) -> str:
    if pd.isna(dstr) or dstr is None or str(dstr).strip() == "":
        return dt.date.today().strftime("%Y-%m-%d")
    dstr = str(dstr).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(dstr, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(dstr, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass
    return dt.date.today().strftime("%Y-%m-%d")

def process_order_record(rec: dict, product_lookup: dict) -> dict:
    out = {}
    out["ORDER_ID"]      = str(rec.get("ORDER_ID", "")).strip() if rec.get("ORDER_ID") else ""
    out["ORDER_DATE"]    = parse_date(rec.get("ORDER_DATE"))
    out["DELIVERY_DATE"] = parse_date(rec.get("DELIVERY_DATE"))
    
    # Mặc định Loading: 20p, Unloading: 30p nếu không nhập
    out["LOADING_TIME"]   = parse_num(rec.get("LOADING_TIME")) or 20.0
    out["UNLOADING_TIME"] = parse_num(rec.get("UNLOADING_TIME")) or 30.0
    
    # Phân loại Ca giao hàng
    shift_raw = str(rec.get("SHIFT", "")).strip()
    if "chiều" in shift_raw.lower() or "pm" in shift_raw.lower():
        out["SHIFT"] = "Ca Chiều"
    elif "đêm" in shift_raw.lower() or "tối" in shift_raw.lower():
        out["SHIFT"] = "Ca Đêm"
    else:
        out["SHIFT"] = "Ca Sáng"

    out["CUSTOMER_ID"]   = str(rec.get("CUSTOMER_ID", "")).strip() if rec.get("CUSTOMER_ID") else ""
    out["CUSTOMER_NAME"] = str(rec.get("CUSTOMER_NAME", "")).strip() if rec.get("CUSTOMER_NAME") else "Khách lẻ"
    
    type_raw = str(rec.get("TYPE", "")).strip().upper()
    out["TYPE"] = "B2B" if "B2B" in type_raw or "CÔNG TY" in out["CUSTOMER_NAME"].upper() else "B2C"
    
    out["LOCATION"]   = str(rec.get("LOCATION", "")).strip() if rec.get("LOCATION") else ""
    out["PRODUCT_ID"] = str(rec.get("PRODUCT_ID", "")).strip() if rec.get("PRODUCT_ID") else ""
    
    qty = max(1, int(parse_num(rec.get("QUANTITY")) or 1))
    out["QUANTITY"] = qty

    # 🔗 TRA CỨU THÔNG TIN SẢN PHẨM ĐỂ TÍNH TỔNG VOLUME_M3 VÀ WEIGHT_KG
    prod_info = product_lookup.get(out["PRODUCT_ID"], {"volume_m3": 0.0, "weight_kg": 0.0})
    
    unit_v = prod_info["volume_m3"]
    unit_w = prod_info["weight_kg"]

    out["TOTAL_VOLUME_M3"] = round(unit_v * qty, 4)
    out["TOTAL_WEIGHT_KG"] = round(unit_w * qty, 3)

    return out

def validate_orders(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    dup_id = out["ORDER_ID"].astype(str).duplicated(keep=False)
    msgs = []
    
    for i, row in out.iterrows():
        errs = []
        if not str(row.get("ORDER_ID", "")).strip():
            errs.append("Thiếu ORDER_ID")
        if dup_id.iloc[i] and str(row.get("ORDER_ID", "")).strip():
            errs.append("Trùng ORDER_ID")
        if not str(row.get("LOCATION", "")).strip():
            errs.append("Thiếu địa chỉ LOCATION")
        if not str(row.get("PRODUCT_ID", "")).strip():
            errs.append("Thiếu PRODUCT_ID")
        if row.get("TOTAL_VOLUME_M3", 0) <= 0:
            errs.append("VOLUME=0 (Check PRODUCT_ID xem đúng danh mục sản phẩm chưa)")
            
        msgs.append("❌ " + "; ".join(errs) if errs else "✅ Hợp lệ")
        
    out["KIỂM_TRA"] = msgs
    return out

# ============================================================================
# 🖥️ 3. GIAO DIỆN NHẬP DỮ LIỆU ĐƠN HÀNG (ORDERS MASTER DATA)
# ============================================================================

def render_orders_input_section():
    st.subheader("🧾 4. Nhập Dữ Liệu Đơn Hàng (Orders Master Data)")
    
    # Đọc Lookup dữ liệu Sản phẩm từ session state (nếu người dùng đã nhập bước trước)
    product_lookup = {}
    if "prod_final_df" in st.session_state:
        pdf = st.session_state["prod_final_df"]
        for _, prow in pdf.iterrows():
            pid = str(prow.get("ID_PRODUCT", "")).strip()
            if pid:
                product_lookup[pid] = {
                    "volume_m3": parse_num(prow.get("VOLUME_M3")),
                    "weight_kg": parse_num(prow.get("WEIGHT_KG"))
                }

    if not product_lookup:
        st.warning("⚠️ *Khuyên dùng: Cậu nên hoàn tất phần 3. Nhập Dữ Liệu Sản Phẩm trước để hệ thống tự động nhân Thể tích & Trọng lượng cho Đơn hàng.*")

    seed_orders = pd.DataFrame({
        "ORDER_ID":       ["ORD_001", "ORD_002", "ORD_003"],
        "ORDER_DATE":     [dt.date.today().strftime("%Y-%m-%d")] * 3,
        "DELIVERY_DATE":  [dt.date.today().strftime("%Y-%m-%d")] * 3,
        "LOADING_TIME":   [20, 15, 30],
        "UNLOADING_TIME": [30, 25, 45],
        "SHIFT":          ["Ca Sáng", "Ca Chiều", "Ca Sáng"],
        "CUSTOMER_ID":    ["CUST_01", "CUST_02", "CUST_03"],
        "CUSTOMER_NAME":  ["Công ty A", "Nguyễn Văn B", "Trần Văn C"],
        "TYPE":           ["B2B", "B2C", "B2C"],
        "LOCATION":       ["Số 1 Tràng Tiền, Hà Nội", "123 Cầu Giấy, Hà Nội", "Thành phố Bắc Ninh, Bắc Ninh"],
        "PRODUCT_ID":     ["SKU_01", "SKU_02", "SKU_03"],
        "QUANTITY":       [10, 5, 12]
    })

    do_geocode = st.checkbox("🌍 Tự động quét ArcGIS Geocoding cho địa chỉ điểm giao đơn hàng", value=True, key="ord_do_geo")

    mode = st.radio(
        "Phương thức nhập dữ liệu Đơn hàng:",
        ["✍️ Nhập trực tiếp (Data Editor)", "📂 Upload file Excel/CSV/JSON"],
        horizontal=True,
        key="ord_input_mode"
    )

    raw_df = None

    if mode == "✍️ Nhập trực tiếp (Data Editor)":
        st.markdown("##### 📝 Chỉnh sửa đơn hàng trực tiếp:")
        raw_df = st.data_editor(
            seed_orders,
            num_rows="dynamic",
            column_config={
                "SHIFT": st.column_config.SelectboxColumn("Ca giao hàng", options=SHIFT_OPTIONS, required=True),
                "TYPE": st.column_config.SelectboxColumn("Loại khách hàng", options=["B2B", "B2C"], required=True),
                "QUANTITY": st.column_config.NumberColumn("Số lượng (Units)", min_value=1, step=1)
            },
            key="ord_editor"
        )
    else:
        st.markdown("##### 📂 Upload file đơn hàng từ máy tính:")
        uploaded_file = st.file_uploader("Chọn file đơn hàng (xlsx, xls, csv, json)", type=["xlsx", "xls", "csv", "json"], key="ord_upload")
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".json"):
                    raw_df = pd.read_json(uploaded_file)
                else:
                    raw_df = pd.read_excel(uploaded_file)
                st.caption(f"📄 Tìm thấy `{len(raw_df)}` dòng dữ liệu đơn hàng từ file.")
            except Exception as e:
                st.error(f"❌ Lỗi đọc file: {e}")

    # ============================================================================
    # 🔍 ÁNH XẠ CỘT SEMANTIC MAPPING CHO ORDERS
    # ============================================================================
    if raw_df is not None and not raw_df.empty:
        st.divider()
        st.markdown("### 🔍 Quét & Ánh Xạ Cột Đơn Hàng Chuẩn Hóa")
        st.info("💡 Hệ thống tự động ghép cột. Cậu có thể điều chỉnh lại các cột tương ứng.")

        input_cols = ["-- Bỏ qua / Không sử dụng --"] + [str(c) for c in raw_df.columns]
        chosen_mapping = {}

        cols_ui = st.columns(3)
        for i, (target_field, aliases) in enumerate(ORDER_FIELDS.items()):
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
                    key=f"select_map_ord_{target_field}"
                )

        # ============================================================================
        # 🚀 CHUẨN HÓA, TÍNH VOL & WEIGHT, QUÉT ARCGIS GEOCODE
        # ============================================================================
        st.divider()
        if st.button("🚀 Chuẩn Hóa Đơn Hàng & Quét Tọa Độ", type="primary", key="btn_process_ord"):
            processed_rows = []
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            total_rows = len(raw_df)
            for idx, (_, row) in enumerate(raw_df.iterrows()):
                rec = {}
                for target_field, mapped_col in chosen_mapping.items():
                    if mapped_col != "-- Bỏ qua / Không sử dụng --" and mapped_col in raw_df.columns:
                        rec[target_field] = row[mapped_col]
                    else:
                        rec[target_field] = None

                # Xử lý record & Tính toán tổng m3, kg từ Product
                p_rec = process_order_record(rec, product_lookup)
                
                # Quét ArcGIS Geocoding địa chỉ khách
                cleaned_loc = clean_address(p_rec["LOCATION"])
                lat, lng, geo_status = None, None, "— Chưa quét"

                if do_geocode and cleaned_loc:
                    status_text.text(f"🌍 Đang geocode đơn hàng [{idx+1}/{total_rows}]: {cleaned_loc}...")
                    geo_res = geocode_address(cleaned_loc)
                    lat, lng = geo_res["lat"], geo_res["lng"]
                    geo_status = geo_res["status"]

                p_rec["LOCATION"] = cleaned_loc
                p_rec["LAT"] = lat
                p_rec["LNG"] = lng
                p_rec["TRẠNG_THÁI_GEOCODE"] = geo_status
                
                processed_rows.append(p_rec)
                progress_bar.progress((idx + 1) / total_rows)

            status_text.empty()
            progress_bar.empty()
            final_df = validate_orders(pd.DataFrame(processed_rows))
            st.session_state["ord_final_df"] = final_df

    # ============================================================================
    # 📋 BẢNG OUTPUT ĐƠN HÀNG & NÚT TẢI DIM_ORDERS.XLSX
    # ============================================================================
    if "ord_final_df" in st.session_state:
        st.markdown("### 📋 Danh Sách Đơn Hàng Đã Chuẩn Hóa (Cho phép kiểm tra & chỉnh sửa)")
        
        edited_final_df = st.data_editor(
            st.session_state["ord_final_df"],
            num_rows="dynamic",
            column_order=[
                "ORDER_ID", "ORDER_DATE", "DELIVERY_DATE", "SHIFT", "CUSTOMER_ID", "CUSTOMER_NAME", 
                "TYPE", "LOCATION", "PRODUCT_ID", "QUANTITY", "TOTAL_VOLUME_M3", "TOTAL_WEIGHT_KG", 
                "LOADING_TIME", "UNLOADING_TIME", "LAT", "LNG", "TRẠNG_THÁI_GEOCODE", "KIỂM_TRA"
            ],
            key="ord_final_editor"
        )

        # Xuất file DIM_ORDERS.xlsx
        out_dir = "output_orders"
        os.makedirs(out_dir, exist_ok=True)
        xlsx_path = os.path.join(out_dir, "DIM_ORDERS.xlsx")

        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            edited_final_df.drop(columns=["KIỂM_TRA", "TRẠNG_THÁI_GEOCODE"], errors="ignore").to_excel(
                writer, sheet_name="DIM_ORDERS", index=False
            )

        with open(xlsx_path, "rb") as f:
            st.download_button(
                label="⬇️ Tải file chốt DIM_ORDERS.xlsx",
                data=f,
                file_name="DIM_ORDERS.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_dim_orders"
            )
        st.success("✅ Đã ghi nhận và sẵn sàng lưu file `output_orders/DIM_ORDERS.xlsx`!")
