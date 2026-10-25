# -*- coding: utf-8 -*-
import streamlit as st

# ============================================================================
# ⚙️ 1. KHỞI TẠO GIÁ TRỊ MẶC ĐỊNH TRONG SESSION STATE
# ============================================================================
def init_pre_routing_state():
    if "shift_count" not in st.session_state:
        st.session_state["shift_count"] = 2

    # Giá trị ca mặc định
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
# 🖥️ 2. GIAO DIỆN PRE-ROUTING (CẤU HÌNH THAM SỐ VẬN TẢI & THỜI GIAN)
# ============================================================================
def render_pre_routing_tab():
    init_pre_routing_state()

    st.header("⚙️ Tab 3: Pre-Routing — Quy Định Vận Tải & Tham Số Đầu Vào")
    st.caption("🛠️ *Thiết lập các quy định về hàng hóa, ca làm việc, thời điểm kiểm tra xe và hệ số tắc đường trước khi định tuyến.*")

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

    # Tiêu đề bảng ca
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
    # 🚦 PHẦN 4: HỆ SỐ TẮC ĐƯỜNG THEO VÙNG & KHUNG GIỜ (GÁN CỐ ĐỊNH + NÚT +/-)
    # ------------------------------------------------------------------------
    st.markdown("### 🚦 4. Hệ Số Tắc Đường Theo Vùng & Khung Giờ")
    st.info("💡 Giá trị hệ số tắc đường được tự động gán mặc định chuẩn xác. Cậu có thể tinh chỉnh lại bằng nút (+/-) nếu muốn.")

    tf_c1, tf_c2, tf_c3 = st.columns(3)
    
    with tf_c1:
        st.markdown("##### 🏙️ Vùng Nội Đô")
        f_urban_peak = st.number_input(
            "1. Nội đô - Giờ cao điểm:",
            value=2.0, min_value=1.0, max_value=5.0, step=0.05, format="%.2f",
            key="tf_urban_peak"
        )
        f_urban_normal = st.number_input(
            "2. Nội đô - Giờ bình thường:",
            value=1.25, min_value=1.0, max_value=5.0, step=0.05, format="%.2f",
            key="tf_urban_normal"
        )

    with tf_c2:
        st.markdown("##### 🏡 Vùng Ngoại Thành")
        f_suburban_peak = st.number_input(
            "3. Ngoại thành - Giờ cao điểm:",
            value=1.40, min_value=1.0, max_value=5.0, step=0.05, format="%.2f",
            key="tf_suburban_peak"
        )
        f_suburban_normal = st.number_input(
            "4. Ngoại thành - Giờ bình thường:",
            value=1.10, min_value=1.0, max_value=5.0, step=0.05, format="%.2f",
            key="tf_suburban_normal"
        )

    with tf_c3:
        st.markdown("##### 🌾 Tỉnh Lẻ & Vùng Xa")
        f_provincial = st.number_input(
            "5. Tỉnh lẻ:",
            value=1.15, min_value=1.0, max_value=5.0, step=0.05, format="%.2f",
            key="tf_provincial"
        )
        f_remote = st.number_input(
            "6. Vùng sâu vùng xa:",
            value=1.50, min_value=1.0, max_value=5.0, step=0.05, format="%.2f",
            key="tf_remote"
        )

    # ------------------------------------------------------------------------
    # 🔑 ĐÓNG GÓI LƯU CẤU HÌNH VÀO SESSION STATE CỦA HỆ THỐNG
    # ------------------------------------------------------------------------
    st.session_state["pre_routing_config"] = {
        "constraint_mode": constraint_mode,
        "shifts": shifts_data,
        "split_time": split_time,
        "traffic_factors": {
            "urban_peak": f_urban_peak,
            "urban_normal": f_urban_normal,
            "suburban_peak": f_suburban_peak,
            "suburban_normal": f_suburban_normal,
            "provincial": f_provincial,
            "remote": f_remote
        }
    }

    st.divider()
    st.success("✅ Toàn bộ cấu hình Pre-Routing đã được ghi nhận và sẵn sàng làm đầu vào cho thuật toán Routing!")
