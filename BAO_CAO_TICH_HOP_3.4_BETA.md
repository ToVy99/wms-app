# Báo cáo chuyển Check Prod sang IntraCity 3.4 Native

**Trạng thái:** Mã nguồn thử nghiệm; **chưa build EXE, chưa đẩy GitHub, chưa chạy WMS thật**.

## Thay đổi

1. Không nhúng nguyên app Productivity hoặc dùng `QWebEngineView` nữa. Tạo giao diện **PySide6 Qt Widgets** trong `productivity_tab.py`, đồng bộ theme của IntraCity.
2. Logic tính toán dịch từ JavaScript gốc sang `prod_native_core.py`, dữ liệu mẫu và kết quả gốc lưu trong `prod_native_fixtures.json` để đối chiếu.
3. Luồng API WMS chuyển sang `prod_native_api.py`, dùng chung một `NativeBridge` tab Chrome đang đăng nhập, giữ Task type 41/42/43, dim_type, query_column, phân trang, cửa sổ Task theo mã nguồn gốc; chỉ 1 request tại một thời điểm để tránh quá tải.
4. Giữ một nút tab Check Prod cạnh Excel/Outbound; **không thêm lại nút trùng cạnh Tìm SKU**.
5. Build script loại Qt WebEngine/Qt WebChannel, không chép toàn bộ Productivity vào EXE; giữ phiên bản 3.4.

## Đã kiểm chứng

- Python `compileall` OK.
- JS Productivity `tests/test_core.js` 20/20 OK.
- Các bài test native parity + static 16/16 OK trên dữ liệu fixture tổng hợp.

## Chưa kiểm chứng

- Mở GUI PySide6 thật, điều khiển tab và đổi theme trên Windows.
- Endpoint WMS live, phân trang 429/503, phản hồi login đã hết hạn, dữ liệu năng suất nhiều nhân viên.
- Kết quả tương đương trên dữ liệu WMS sản xuất và kích thước EXE thực tế sau build.

**Không được phát hành hoặc coi là bản chính thức trước khi kiểm thử thực tế, đối chiếu dữ liệu và chủ dự án xác nhận.**
