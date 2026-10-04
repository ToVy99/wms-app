IntraCity 2.3.3 - COT gọn, tải theo lựa chọn

CHẠY: Windows 10/11 64-bit có Google Chrome. Không cần Python.
Mở IntraCity_2.3.3.exe -> Đăng nhập WMS -> có 5 giây đổi kho.
Chọn nhóm, ngày và nút COT. Chỉ COT đó được gọi API và tải đủ trang.
Chưa Pick / Check / Pack / WIS / Chưa Outbound / Tổng đơn lọc ngay dữ liệu đã tải.
Tải lại COT cập nhật dữ liệu của COT đang chọn. Copy / Export theo danh sách đang xem.
Không tải toàn bộ COT; không gọi WMS khi mở app, đổi nhóm hoặc đổi ngày.

KHUNG THEO GIỜ VIỆT NAM:
SDD: 18:00 ngày trước–04:00, 04:00–09:00, 09:00–13:30, 13:30–18:00.
AhaMove: 18:00 ngày trước–08:00, 08:00–13:00, 13:00–18:00.
SPX Cồng kềnh: 17:00 ngày trước–17:00 (kênh 50025).
Intra City theo Purchase Time:
- COT 1: 20:00–23:00 ngày trước.
- COT 2: 23:00 ngày trước–02:00.
- COT 3: 02:00–16:00; có nút khung nhỏ 02–05 / 05–16.
- COT 4: 16:00–20:00; có nút khung nhỏ 16–18 / 18–20.
Ngày chọn là ngày kết thúc chu kỳ. App hiện ngày/giờ đầy đủ của khung đang chọn.
Mốc bàn giao Pick / Check / Pack / WIS lấy từ bảng người dùng gửi.
Đơn ở đúng ranh giới giờ thuộc khung tiếp theo, tránh trùng giữa hai COT.
GHN Tổng / Cồng kềnh / Normal vẫn có trong nhóm GHN.

KIỂM TRA: mô phỏng phân trang, chỉ tải COT chọn, cache, chuyển COT nhanh,
ranh giới khung giờ, qua ngày/tháng/năm. Windows build còn kiểm tra EXE thực,
giao diện nút COT, Playwright driver và spinner. Không dùng tài khoản WMS thật.

BUILD: Python 3.12 64-bit trên Windows, chạy build_windows.ps1.
GitHub Actions build trên máy Windows cloud và xuất artifact IntraCity_Windows_x64.
File EXE lưu cấu hình ở %LOCALAPPDATA%\IntraCity\wms_config.json.
