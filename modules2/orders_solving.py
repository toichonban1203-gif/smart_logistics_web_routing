# -*- coding: utf-8 -*-
import pandas as pd
import plotly.express as px
import streamlit as st

# ============================================================================
# 🛠️ 1. HÀM PHÂN LOẠI TỈNH / THÀNH PHỐ TỪ ĐỊA CHỈ (LOCATION)
# ============================================================================

PROVINCE_KEYWORDS = {
    "Hà Nội":      ["hà nội", "ha noi", "hn"],
    "Hải Phòng":   ["hải phòng", "hai phong", "hp"],
    "Quảng Ninh":  ["quảng ninh", "quang ninh"],
    "Hải Dương":   ["hải dương", "hai duong"],
    "Bắc Ninh":    ["bắc ninh", "bac ninh"],
    "Hưng Yên":    ["hưng yên", "hung yen"],
    "Bắc Giang":   ["bắc giang", "bac giang"],
    "Thái Nguyên": ["thái nguyên", "thai nguyen"],
    "Nam Định":    ["nam định", "nam dinh"],
    "Ninh Bình":   ["ninh bình", "ninh binh"],
    "Thái Bình":   ["thái bình", "thai binh"],
    "Vĩnh Phúc":   ["vĩnh phúc", "vinh phuc"],
    "Hà Nam":      ["hà nam", "ha nam"],
    "Phú Thọ":     ["phú thọ", "phu tho"]
}

def detect_province(location_str: str) -> str:
    if not location_str or pd.isna(location_str):
        return "Chưa xác định"
    
    loc_clean = str(location_str).lower()
    for province, keywords in PROVINCE_KEYWORDS.items():
        if any(kw in loc_clean for kw in keywords):
            return province
            
    return "Tỉnh/Thành khác"

# ============================================================================
# 🖥️ 2. GIAO DIỆN TAB ORDERS SOLVING (PHÂN TÍCH ĐƠN HÀNG)
# ============================================================================

def render_orders_solving_tab():
    st.header("🧩 Tab 2: Orders Solving — Phân Tích Đơn Hàng Theo Vị Trí & Ca Giao")
    st.caption("📊 *Hệ thống tự động trích xuất vị trí địa lý (Tỉnh/Thành) và trực quan hóa phân bổ đơn hàng qua các biểu đồ chuyên sâu.*")

    # 1. Đọc dữ liệu đơn hàng từ Session State (nhập từ Tab 1)
    if "ord_final_df" not in st.session_state or st.session_state["ord_final_df"].empty:
        st.warning("⚠️ Chưa tìm thấy dữ liệu Đơn hàng. Vui lòng hoàn tất **1. Nhập Dữ Liệu Khách Hàng (Đơn hàng)** trước!")
        return

    df_orders = st.session_state["ord_final_df"].copy()

    # Làm sạch & chuẩn hóa dữ liệu cần thiết
    df_orders["TOTAL_VOLUME_M3"] = pd.to_numeric(df_orders["TOTAL_VOLUME_M3"], errors="coerce").fillna(0.0)
    df_orders["TOTAL_WEIGHT_KG"] = pd.to_numeric(df_orders["TOTAL_WEIGHT_KG"], errors="coerce").fillna(0.0)
    df_orders["QUANTITY"]        = pd.to_numeric(df_orders["QUANTITY"], errors="coerce").fillna(1)
    
    # Chuẩn hóa tên Ca (Sáng, Chiều, Đêm/Flexible)
    def clean_shift(s):
        s_str = str(s).strip()
        if "sáng" in s_str.lower(): return "Ca Sáng"
        if "chiều" in s_str.lower(): return "Ca Chiều"
        if "đêm" in s_str.lower() or "flexible" in s_str.lower() or "tối" in s_str.lower(): return "Ca Flexible/Đêm"
        return "Ca Flexible/Đêm"

    df_orders["SHIFT_CLEAN"] = df_orders["SHIFT"].apply(clean_shift)
    df_orders["PROVINCE"]    = df_orders["LOCATION"].apply(detect_province)

    # ------------------------------------------------------------------------
    # 📌 PHẦN 1: BẢNG LIỆT KÊ LẠI THÔNG TIN CÁC ĐƠN TỪ PHẦN ORDERS
    # ------------------------------------------------------------------------
    st.divider()
    st.markdown("### 📋 1. Bảng Tổng Hợp Chi Tiết Đơn Hàng (Đã phân loại vị trí)")
    
    # Hiển thị các chỉ số nhanh (KPI Cards)
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Tổng Số Đơn Hàng", f"{len(df_orders):,} đơn")
    kpi2.metric("Tổng Units", f"{df_orders['QUANTITY'].sum():,} sp")
    kpi3.metric("Tổng Thể Tích (m³)", f"{df_orders['TOTAL_VOLUME_M3'].sum():,.2f} m³")
    kpi4.metric("Tổng Trọng Lượng (kg)", f"{df_orders['TOTAL_WEIGHT_KG'].sum():,.1f} kg")

    display_cols = [
        "ORDER_ID", "CUSTOMER_NAME", "LOCATION", "PROVINCE", "SHIFT_CLEAN", 
        "PRODUCT_ID", "QUANTITY", "TOTAL_VOLUME_M3", "TOTAL_WEIGHT_KG", "TYPE"
    ]
    st.dataframe(
        df_orders[display_cols].rename(columns={
            "ORDER_ID": "Mã Đơn", "CUSTOMER_NAME": "Khách Hàng", "LOCATION": "Địa Chỉ Giao",
            "PROVINCE": "Tỉnh/Thành", "SHIFT_CLEAN": "Ca Giao", "PRODUCT_ID": "Mã SP",
            "QUANTITY": "Số Lượng", "TOTAL_VOLUME_M3": "Thể Tích (m³)", "TOTAL_WEIGHT_KG": "Trọng Lượng (kg)", "TYPE": "Loại Đơn"
        }),
        use_container_width=True
    )

    # ------------------------------------------------------------------------
    # 📌 PHẦN 2: PIE CHARTS THEO ĐƠN VỊ SỐ LƯỢNG ĐƠN HÀNG
    # ------------------------------------------------------------------------
    st.divider()
    st.markdown("### 📊 2. Phân Thống Kê Theo Đơn Vị: SỐ LƯỢNG ĐƠN HÀNG")
    col_p2_1, col_p2_2 = st.columns(2)

    with col_p2_1:
        st.markdown("##### 📍 Tỷ lệ đơn hàng theo Tỉnh/Thành")
        fig_qty_prov = px.pie(
            df_orders, names="PROVINCE", 
            title="Số Lượng Đơn Theo Vị Trí Địa Lý",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_qty_prov.update_traces(textinfo="percent+label+value")
        st.plotly_chart(fig_qty_prov, use_container_width=True)

    with col_p2_2:
        st.markdown("##### ⏰ Tỷ lệ đơn hàng theo Ca Giao Hàng")
        fig_qty_shift = px.pie(
            df_orders, names="SHIFT_CLEAN", 
            title="Số Lượng Đơn Theo Ca Giao Hàng",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_qty_shift.update_traces(textinfo="percent+label+value")
        st.plotly_chart(fig_qty_shift, use_container_width=True)

    # ------------------------------------------------------------------------
    # 📌 PHẦN 3: PIE CHARTS THEO ĐƠN VỊ THỂ TÍCH (TOTAL_VOLUME_M3)
    # ------------------------------------------------------------------------
    st.divider()
    st.markdown("### 📦 3. Phân Thống Kê Theo Đơn Vị: THỂ TÍCH (m³)")
    col_p3_1, col_p3_2 = st.columns(2)

    with col_p3_1:
        st.markdown("##### 📍 Tổng thể tích (m³) theo Tỉnh/Thành")
        fig_vol_prov = px.pie(
            df_orders, names="PROVINCE", values="TOTAL_VOLUME_M3",
            title="Tổng Thể Tích (m³) Theo Vị Trí Địa Lý",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_vol_prov.update_traces(textinfo="percent+label+value")
        st.plotly_chart(fig_vol_prov, use_container_width=True)

    with col_p3_2:
        st.markdown("##### ⏰ Tổng thể tích (m³) theo Ca Giao Hàng")
        fig_vol_shift = px.pie(
            df_orders, names="SHIFT_CLEAN", values="TOTAL_VOLUME_M3",
            title="Tổng Thể Tích (m³) Theo Ca Giao Hàng",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_vol_shift.update_traces(textinfo="percent+label+value")
        st.plotly_chart(fig_vol_shift, use_container_width=True)

    # ------------------------------------------------------------------------
    # 📌 PHẦN 4: PIE CHARTS THEO ĐƠN VỊ KHỐI LƯỢNG (TOTAL_WEIGHT_KG)
    # ------------------------------------------------------------------------
    st.divider()
    st.markdown("### ⚖️ 4. Phân Thống Kê Theo Đơn Vị: TRỌNG LƯỢNG (kg)")
    col_p4_1, col_p4_2 = st.columns(2)

    with col_p4_1:
        st.markdown("##### 📍 Tổng trọng lượng (kg) theo Tỉnh/Thành")
        fig_weight_prov = px.pie(
            df_orders, names="PROVINCE", values="TOTAL_WEIGHT_KG",
            title="Tổng Trọng Lượng (kg) Theo Vị Trí Địa Lý",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_weight_prov.update_traces(textinfo="percent+label+value")
        st.plotly_chart(fig_weight_prov, use_container_width=True)

    with col_p4_2:
        st.markdown("##### ⏰ Tổng trọng lượng (kg) theo Ca Giao Hàng")
        fig_weight_shift = px.pie(
            df_orders, names="SHIFT_CLEAN", values="TOTAL_WEIGHT_KG",
            title="Tổng Trọng Lượng (kg) Theo Ca Giao Hàng",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Vivid
        )
        fig_weight_shift.update_traces(textinfo="percent+label+value")
        st.plotly_chart(fig_weight_shift, use_container_width=True)
