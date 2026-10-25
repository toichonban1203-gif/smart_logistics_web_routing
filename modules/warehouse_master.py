# -*- coding: utf-8 -*-
import os
import io
import json
import re
import time
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz
from geopy.geocoders import ArcGIS

# ============================================================================
# ⚙️ 1. CẤU HÌNH SCHEMA CHUẨN & GEOLOCATION CHO WAREHOUSE
# ============================================================================

VIETNAM_BOUNDS = (8.0, 24.5, 102.0, 110.0)

WAREHOUSE_FIELDS = {
    "ID_WAREHOUSE": ["mã kho", "warehouse id", "warehouse code", "warehouse", "kho", "id kho", "id_warehouse"],
    "NAME":         ["tên kho", "warehouse name", "name", "tên chi nhánh", "depot name", "wh name"],
    "LOCATION":     ["địa chỉ", "địa điểm", "address", "location", "vị trí", "địa chỉ kho"]
}

ADDRESS_ABBR = [
    (r"\bTP\.?\b", "Thành phố"), (r"\bQ\.?\b", "Quận"), (r"\bH\.?\b", "Huyện"),
    (r"\bTX\.?\b", "Thị xã"), (r"\bTT\.?\b", "Thị trấn"), (r"\bP\.?\b", "Phường"),
    (r"\bX\.?\b", "Xã"), (r"\bĐg\.?\b", "Đường"),
]

# ============================================================================
# 🛠️ 2. HÀM CHUẨN HÓA ĐỊA CHỈ & GEOCODING ARCGIS
# ============================================================================

def clean_address(address: str) -> str:
    if pd.isna(address) or address is None or str(address).strip() == "":
        return ""
    text = str(address).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"[\u00A0\u2000-\u200B\u202F\u3000]", " ", text)
    text = re.sub(r"\s*[|;→–—]\s*", ", ", text)
    text = re.sub(r"\s+-\s+", ", ", text)
    text = re.sub(r"[^0-9A-Za-zÀ-ỹĐđ\s,./'-]", " ", text)
    for pattern, repl in ADDRESS_ABBR:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ,.")
    if text and not re.search(r"\bViệt Nam\b|\bVietnam\b", text, re.I):
        text += ", Việt Nam"
    return text

def coordinate_in_vietnam(lat: float, lng: float) -> bool:
    try:
        lat, lng = float(lat), float(lng)
        return VIETNAM_BOUNDS[0] <= lat <= VIETNAM_BOUNDS[1] and VIETNAM_BOUNDS[2] <= lng <= VIETNAM_BOUNDS[3]
    except Exception:
        return False

@st.cache_resource(show_spinner=False)
def get_geocoder():
    try:
        return ArcGIS(user_agent="smart-logistics-warehouse/1.0", timeout=10)
    except Exception:
        return None

def geocode_address(address: str, retries: int = 2) -> dict:
    cleaned = clean_address(address)
    if not cleaned:
        return {"ok": False, "lat": None, "lng": None, "status": "❌ Địa chỉ trống"}
    
    geocoder = get_geocoder()
    if geocoder is None:
        return {"ok": False, "lat": None, "lng": None, "status": "❌ Không kết nối được ArcGIS"}

    for attempt in range(1, retries + 1):
        try:
            loc = geocoder.geocode(cleaned, timeout=10)
            if loc is None:
                return {"ok": False, "lat": None, "lng": None, "status": "⚠️ Không tìm thấy vị trí"}
            lat, lng = float(loc.latitude), float(loc.longitude)
            if not coordinate_in_vietnam(lat, lng):
                return {"ok": False, "lat": lat, "lng": lng, "status": "⚠️ Tọa độ nằm ngoài VN"}
            return {"ok": True, "lat": lat, "lng": lng, "status": "✅ Geocode thành công"}
        except Exception:
            if attempt == retries:
                break
            time.sleep(1)
    return {"ok": False, "lat": None, "lng": None, "status": "❌ Lỗi kết nối Geocoding"}

def validate_warehouse(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    dup_id = out["ID_WAREHOUSE"].astype(str).duplicated(keep=False)
    msgs = []
    
    for i, row in out.iterrows():
        errs = []
        if not str(row.get("ID_WAREHOUSE", "")).strip():
            errs.append("Thiếu ID_WAREHOUSE")
        if dup_id.iloc[i] and str(row.get("ID_WAREHOUSE", "")).strip():
            errs.append("Trùng ID_WAREHOUSE")
        if not str(row.get("LOCATION", "")).strip():
            errs.append("Thiếu địa chỉ LOCATION")
        if pd.isna(row.get("LAT")) or pd.isna(row.get("LNG")):
            errs.append("Chưa lấy được tọa độ")
            
        msgs.append("❌ " + "; ".join(errs) if errs else "✅ Hợp lệ")
        
    out["KIỂM_TRA"] = msgs
    return out

# ============================================================================
# 🖥️ 3. GIAO DIỆN NHẬP DỮ LIỆU KHO (WAREHOUSE MASTER DATA)
# ============================================================================

def render_warehouse_input_section():
    st.subheader("🏭 2. Nhập Dữ Liệu Kho & Tọa Độ (Warehouse Master Data)")
    
    seed_warehouse = pd.DataFrame({
        "ID_WAREHOUSE": ["WH_HN_01", "WH_HN_02"],
        "NAME":         ["Kho Tổng Hà Nội", "Kho Cầu Giấy"],
        "LOCATION":     ["Số 1 Tràng Tiền, Hoàn Kiếm, Hà Nội", "123 Cầu Giấy, Hà Nội"]
    })

    do_geocode = st.checkbox("🌍 Tự động quét ArcGIS Geocoding để tìm tọa độ (LAT, LNG)", value=True, key="wh_do_geo")

    mode = st.radio(
        "Phương thức nhập dữ liệu Kho:",
        ["✍️ Nhập trực tiếp (Data Editor)", "📂 Upload file Excel/CSV/JSON"],
        horizontal=True,
        key="wh_input_mode"
    )

    raw_df = None

    if mode == "✍️ Nhập trực tiếp (Data Editor)":
        st.markdown("##### 📝 Chỉnh sửa thông tin kho trực tiếp:")
        raw_df = st.data_editor(
            seed_warehouse,
            num_rows="dynamic",
            key="wh_editor"
        )
    else:
        st.markdown("##### 📂 Upload file kho từ máy tính:")
        uploaded_file = st.file_uploader("Chọn file kho (xlsx, xls, csv, json)", type=["xlsx", "xls", "csv", "json"], key="wh_upload")
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".json"):
                    raw_df = pd.read_json(uploaded_file)
                else:
                    raw_df = pd.read_excel(uploaded_file)
                st.caption(f"📄 Tìm thấy `{len(raw_df)}` dòng dữ liệu kho từ file.")
            except Exception as e:
                st.error(f"❌ Lỗi đọc file: {e}")

    # ============================================================================
    # 🔍 ÁNH XẠ CỘT SEMANTIC MAPPING CHO KHO
    # ============================================================================
    if raw_df is not None and not raw_df.empty:
        st.divider()
        st.markdown("### 🔍 Quét & Ánh Xạ Cột Kho Chuẩn Hóa")
        st.info("💡 Hệ thống khớp các cột `ID_WAREHOUSE`, `NAME`, `LOCATION`. Cậu có thể tùy chỉnh lại selectbox nếu cần.")

        input_cols = ["-- Bỏ qua / Không sử dụng --"] + [str(c) for c in raw_df.columns]
        chosen_mapping = {}

        cols_ui = st.columns(3)
        for i, (target_field, aliases) in enumerate(WAREHOUSE_FIELDS.items()):
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
                    key=f"select_map_wh_{target_field}"
                )

        # ============================================================================
        # 🚀 CHUẨN HÓA, QUÉT ARCGIS GEOCODE & LƯU SESSION
        # ============================================================================
        st.divider()
        if st.button("🚀 Chuẩn Hóa Dữ Liệu Kho & Quét Tọa Độ", type="primary", key="btn_process_wh"):
            processed_rows = []
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            total_rows = len(raw_df)
            for idx, (_, row) in enumerate(raw_df.iterrows()):
                wh_id = str(row[chosen_mapping["ID_WAREHOUSE"]]).strip() if chosen_mapping.get("ID_WAREHOUSE") in raw_df.columns else ""
                wh_name = str(row[chosen_mapping["NAME"]]).strip() if chosen_mapping.get("NAME") in raw_df.columns else "Kho hàng"
                raw_loc = str(row[chosen_mapping["LOCATION"]]).strip() if chosen_mapping.get("LOCATION") in raw_df.columns else ""
                
                cleaned_loc = clean_address(raw_loc)
                lat, lng, geo_status = None, None, "— Chưa quét"

                if do_geocode and cleaned_loc:
                    status_text.text(f"🌍 Đang geocode kho [{idx+1}/{total_rows}]: {cleaned_loc}...")
                    geo_res = geocode_address(cleaned_loc)
                    lat, lng = geo_res["lat"], geo_res["lng"]
                    geo_status = geo_res["status"]

                processed_rows.append({
                    "ID_WAREHOUSE": wh_id,
                    "NAME": wh_name,
                    "LOCATION": cleaned_loc,
                    "LAT": lat,
                    "LNG": lng,
                    "TRẠNG_THÁI_GEOCODE": geo_status
                })
                progress_bar.progress((idx + 1) / total_rows)

            status_text.empty()
            progress_bar.empty()
            final_df = validate_warehouse(pd.DataFrame(processed_rows))
            st.session_state["wh_final_df"] = final_df

    # ============================================================================
    # 📋 BẢNG OUTPUT KHO & NÚT TẢI WAREHOUSE_WITH_COORDINATES.XLSX
    # ============================================================================
    if "wh_final_df" in st.session_state:
        st.markdown("### 📋 Danh Sách Kho Đã Quét Tọa Độ (Cho phép kéo thả & chỉnh sửa)")
        
        edited_final_df = st.data_editor(
            st.session_state["wh_final_df"],
            num_rows="dynamic",
            column_order=["ID_WAREHOUSE", "NAME", "LOCATION", "LAT", "LNG", "TRẠNG_THÁI_GEOCODE", "KIỂM_TRA"],
            key="wh_final_editor"
        )

        # Hiển thị bản đồ trực quan nếu có tọa độ
        map_df = edited_final_df.dropna(subset=["LAT", "LNG"]).rename(columns={"LAT": "lat", "LNG": "lon"})
        if not map_df.empty:
            st.markdown("##### 🗺️ Bản đồ vị trí các kho:")
            st.map(map_df[["lat", "lon"]])

        # Xuất file WAREHOUSE_WITH_COORDINATES.xlsx
        out_dir = "output_warehouse"
        os.makedirs(out_dir, exist_ok=True)
        xlsx_path = os.path.join(out_dir, "WAREHOUSE_WITH_COORDINATES.xlsx")

        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            edited_final_df.drop(columns=["KIỂM_TRA", "TRẠNG_THÁI_GEOCODE"], errors="ignore").to_excel(
                writer, sheet_name="DIM_WAREHOUSE", index=False
            )

        with open(xlsx_path, "rb") as f:
            st.download_button(
                label="⬇️ Tải file chốt WAREHOUSE_WITH_COORDINATES.xlsx",
                data=f,
                file_name="WAREHOUSE_WITH_COORDINATES.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_warehouse_coords"
            )
        st.success("✅ Đã ghi nhận và sẵn sàng lưu file `output_warehouse/WAREHOUSE_WITH_COORDINATES.xlsx`!")
