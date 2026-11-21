# -*- coding: utf-8 -*-
import os
import sys
import streamlit as st

# Thêm thư mục gốc vào sys.path để Python nhận diện các gói modules & modules2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ============================================================================
# ⚙️ 1. CẤU HÌNH TRANG STREAMLIT (phải là lệnh Streamlit đầu tiên)
# ============================================================================
st.set_page_config(
    page_title="Smart Logistics Dashboard",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 📦 2. IMPORT CÁC MODULE DỰ ÁN
#    modules/  : nhập & chuẩn hóa Master Data (+ common_utils dùng chung)
#    modules2/ : phân tích đơn hàng & cấu hình tiền định tuyến
# ============================================================================
from modules.fleet_master import render_fleet_input_section
from modules.warehouse_master import render_warehouse_input_section
from modules.product_master import render_product_input_section
from modules.orders_master import render_orders_input_section

from modules2.orders_solving import render_orders_solving_tab
from modules2.pre_routing import render_pre_routing_tab


# ============================================================================
# 🖥️ 3. GIAO DIỆN CHÍNH CỦA ỨNG DỤNG
# ============================================================================
def main():
    st.title("🚚 Smart Logistics — Hệ Thống Chuẩn Hóa & Điều Phối Vận Tải")
    st.caption("Tác giả: Phạm Minh Thái | Hệ thống tối ưu hóa dữ liệu & định tuyến thông minh")

    with st.sidebar:
        st.header("⚙️ Quản Lý Hệ Thống")
        st.info(
            "💡 **Thứ tự thực hiện:**\n"
            "1. Nhập Master Data ở **Tab 1** (Xe → Kho → Sản phẩm → Đơn hàng).\n"
            "2. Phân tích trực quan ở **Tab 2**.\n"
            "3. Cấu hình vận tải ở **Tab 3**."
        )

        if st.button("🧹 Giải phóng RAM & Reset Bộ Nhớ", type="secondary", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    tab_input, tab_solving, tab_prerouting = st.tabs([
        "📥 1. Nhập Dữ Liệu Khách Hàng",
        "🧩 2. Orders Solving",
        "⚙️ 3. Pre-Routing"
    ])

    # TAB 1: NHẬP & CHUẨN HÓA MASTER DATA (modules/)
    with tab_input:
        st.markdown("## 📋 CHƯƠNG TRÌNH NHẬP & CHUẨN HÓA MASTER DATA")
        st.info("Quét tự động Semantic Mapping, tối ưu dung lượng RAM và cho phép chỉnh sửa/kéo thả cột trực tiếp trước khi chốt file.")

        # 1. Hạm đội xe -> output_fleet/DIM_VEHICLE.xlsx
        render_fleet_input_section()
        st.divider()

        # 2. Kho & tọa độ ArcGIS -> output_warehouse/WAREHOUSE_WITH_COORDINATES.xlsx
        render_warehouse_input_section()
        st.divider()

        # 3. Sản phẩm (thể tích, trọng lượng) -> output_product/DIM_PRODUCT.xlsx
        render_product_input_section()
        st.divider()

        # 4. Đơn hàng (tra cứu thể tích/trọng lượng từ Sản phẩm) -> output_orders/DIM_ORDERS.xlsx
        render_orders_input_section()

    # TAB 2: ORDERS SOLVING — PHÂN TÍCH ĐƠN HÀNG (modules2/)
    with tab_solving:
        render_orders_solving_tab()

    # TAB 3: PRE-ROUTING — MA TRẬN TẮC ĐƯỜNG, VẬN TỐC, CA (modules2/)
    with tab_prerouting:
        render_pre_routing_tab()


if __name__ == "__main__":
    main()
