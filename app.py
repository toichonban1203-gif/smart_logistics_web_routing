# -*- coding: utf-8 -*-
import os
import sys
import streamlit as st

# Thêm thư mục gốc vào hệ thống để Python nhận diện các gói modules & modules2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# ============================================================================
# ⚙️ 1. CẤU HÌNH TRANG STREAMLIT
# ============================================================================
st.set_page_config(
    page_title="Smart Logistics Dashboard",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 📦 2. IMPORT CÁC MODULE DỰ ÁN
# ============================================================================
# Các Module Nhập liệu & Tiền định tuyến (nằm trong thư mục modules)
from modules.fleet_master import render_fleet_input_section
from modules.warehouse_master import render_warehouse_input_section
from modules.product_master import render_product_input_section
from modules.orders_master import render_orders_input_section
from modules.pre_routing import render_pre_routing_tab

# Module Orders Solving (nằm trong thư mục modules2)
from modules2.orders_solving import render_orders_solving_tab


# ============================================================================
# 🖥️ 3. GIAO DIỆN CHÍNH CỦA ỨNG DỤNG
# ============================================================================
def main():
    st.title("🚚 Smart Logistics — Hệ Thống Chuẩn Hóa & Điều Phối Vận Tải")
    st.caption("Tác giả: Phạm Minh Thái | Hệ thống tối ưu hóa dữ liệu & định tuyến thông minh")

    # Thanh Sidebar quản lý nhanh
    with st.sidebar:
        st.header("⚙️ Quản Lý Hệ Thống")
        st.info(
            "💡 **Thứ tự thực hiện:**\n"
            "1. Nhập Master Data ở **Tab 1**.\n"
            "2. Phân tích trực quan ở **Tab 2**.\n"
            "3. Cấu hình vận tải ở **Tab 3**."
        )
        
        if st.button("🧹 Giải phóng RAM & Reset Bộ Nhớ", type="secondary", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # Khởi tạo 3 Tab chính của hệ thống
    tab_input, tab_solving, tab_prerouting = st.tabs([
        "📥 1. Nhập Dữ Liệu Khách Hàng",
        "🧩 2. Orders Solving",
        "⚙️ 3. Pre-Routing"
    ])

    # ------------------------------------------------------------------------
    # 📥 TAB 1: NHẬP & CHUẨN HÓA DỮ LIỆU KHÁCH HÀNG (MODULES)
    # ------------------------------------------------------------------------
    with tab_input:
        st.markdown("## 📋 CHƯƠNG TRÌNH NHẬP & CHUẨN HÓA MASTER DATA")
        st.info("Quét tự động Semantic Mapping, tối ưu dung lượng RAM và cho phép chỉnh sửa/kéo thả cột trực tiếp trước khi chốt file.")
        
        # 1. Hạm đội xe (xuất DIM_VEHICLE.xlsx)
        render_fleet_input_section()
        
        st.divider()
        
        # 2. Kho & Tọa độ ArcGIS (xuất WAREHOUSE_WITH_COORDINATES.xlsx)
        render_warehouse_input_section()
        
        st.divider()
        
        # 3. Sản phẩm quy đổi về đơn vị Mét (xuất DIM_PRODUCT.xlsx)
        render_product_input_section()
        
        st.divider()
        
        # 4. Đơn hàng & Liên kết Thể tích/Trọng lượng từ Sản phẩm (xuất DIM_ORDERS.xlsx)
        render_orders_input_section()

    # ------------------------------------------------------------------------
    # 🧩 TAB 2: ORDERS SOLVING — PHÂN TÍCH ĐƠN HÀNG (MODULES2)
    # ------------------------------------------------------------------------
    with tab_solving:
        render_orders_solving_tab()

    # ------------------------------------------------------------------------
    # ⚙️ TAB 3: PRE-ROUTING — CẤU HÌNH QUY ĐỊNH VẬN TẢI (MODULES)
    # ------------------------------------------------------------------------
    with tab_prerouting:
        render_pre_routing_tab()

if __name__ == "__main__":
    main()
