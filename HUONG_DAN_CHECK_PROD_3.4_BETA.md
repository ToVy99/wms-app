# IntraCity 3.4 Beta — Check Prod (Native PySide6)

**Đây là mã nguồn thử nghiệm, chưa build EXE và chưa xác nhận chạy trên Windows/WMS thật.** Phiên bản vẫn là **3.4**, không tạo 3.5.

## Thiết kế tích hợp

- Check Prod chỉ xuất hiện một lần, ở cụm tab chính, cạnh Excel / Outbound. Nút trùng cạnh Tìm SKU đã được loại bỏ.
- Giao diện **PySide6 Widgets gốc** của IntraCity, đồng bộ chế độ sáng/tối. Không khởi tạo QWebEngineView, Electron hay Chrome thứ hai.
- Tận dụng **đúng phiên tab Chrome WMS hiện tại** của IntraCity (Chrome riêng hoặc tiện ích). Các request đến WMS đi qua `NativeBridge`/worker đang hoạt động; không đọc/copy Cookie.
- Lấy thuật toán gốc từ `WMS-Productivity-1.0-Office-UI-source.zip`, chuyển đổi sang Python tại `prod_native_core.py` (time, station, ghép nhân viên, giờ công, xếp hạng, tổng kết). `prod_native_api.py` chuyển đổi quy tắc phân trang và các đường dẫn/param API. Bản JavaScript gốc được giữ trong mã nguồn để đối chiếu, **không đóng gói vào EXE**.
- 5 phần: Sort, Check, Check Station, Check&Pack, Pack; BAU/CP (mỗi loại 2 ca chỉnh giờ), Item/Order, Target, Station mapping, lọc dưới Target, xuất Excel, cao/thấp Prod.
- COT, SKU, Area và các file nghiệp vụ gốc không bị sửa trong lượt chuyển đổi native này.

## Tại sao EXE cũ tăng 270 MB?

Bản trước dùng Qt WebEngine (Chromium nằm trong PySide6), đóng gói thêm QtWebEngineProcess và bộ thư viện nặng. Bản source này loại bỏ `PySide6.QtWebEngineWidgets` và `PySide6.QtWebChannel` khỏi màn hình Check Prod. `build_windows.ps1` thêm cờ loại trừ WebEngine và chỉ chép `productivity/stations.js` vào EXE. **Chưa đo dung lượng EXE thực tế trên Windows**; không cam kết chính xác 100 MB trước khi build.

## Kiểm chứng

- `python -m unittest test_checkprod_34_static test_native_prod_parity` — 16 bài kiểm tra nguồn, phân trang API và kịch bản so sánh JS/Python từ dữ liệu mẫu.
- `node tests/test_core.js` của ZIP Productivity gốc: 20 test logic gốc đạt.
- Các fixture được sinh bằng `productivity/core.js` gốc; fixture `prod_native_fixtures.json` cho phép kiểm thử bản Python ngay cả khi máy build Windows không cài Node.
- Các hàm xử lý API phải được kiểm thử trên WMS thực tế (quyền truy cập, giới hạn phân trang, retry 429/503). Công thức thuần được kiểm theo fixture, **không thể bảo đảm 100% mọi dữ liệu sản xuất cho đến khi kiểm thử chéo trên cùng dữ liệu thật**.
- Chưa chạy được GUI PySide6 tại đây vì môi trường hiện tại không có thư viện PySide6 và không tải được từ mạng. Chưa build EXE theo yêu cầu của chủ dự án.

## Thử nghiệm trên máy Windows (không build)

Nếu đã cài dependencies Python của bản 3.4, từ thư mục source chạy:

```powershell
.\.venv-build\Scripts\python.exe launcher.py
```

Chỉ kiểm tra tab UI và request khi đã có Chrome WMS hợp lệ. Cần so sánh cùng kho, cùng ngày/giờ, Task Type, Item/Order và Target với Productivity độc lập trước khi cấp phép phát hành.

Khi chủ dự án cho phép build: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1`.
