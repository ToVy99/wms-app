IntraCity 2.3.1 - sửa nhận diện đăng nhập WMS

EXE Windows x64 đã build và kiểm tra khởi động thành công trên GitHub Actions.
Lần build: https://github.com/ToVy99/wms-app/actions/runs/37189063039?pr=1
Tải artifact IntraCity_2.3.1_Windows_x64 rồi giải nén IntraCity_2.3.1.exe.

Đã sửa:
- Xác nhận bằng đúng hostname WMS và menu hiển thị, không dựa vào SPC_EC.
- Theo dõi cả tab WMS do SSO mở thêm.
- Bỏ API probe khỏi bước đăng nhập. API kiểm tra phiên khi tải dữ liệu COT.
- Lấy cookie áp dụng cho URL API, bao gồm domain cha và path /api.
- Đóng trình duyệt trước khi báo đăng nhập thành công.
- Hết thời gian chờ thì đóng trình duyệt, báo lỗi và dừng spinner.
- Cập nhật tiến độ không chồng thêm con trỏ chờ; giữ thông báo đúng bước.
- Bản EXE lưu cấu hình ở %LOCALAPPDATA%\IntraCity\wms_config.json.
- Giữ hai tab COT Dashboard / Excel, các mốc COT và phân trang danh sách đơn.

Kiểm thử: compile, GUI PySide6 offscreen, mô phỏng SSO và timeout đã qua.
EXE đã kiểm tra trên Windows: 2 tab, 13 dòng COT, Playwright driver khởi động,
spinner dừng đúng. Chưa kiểm thử đăng nhập bằng tài khoản WMS thật.

BUILD KHÔNG CẦN MÁY CÁ NHÂN:
1. Đưa nội dung thư mục IntraCity vào gốc repository GitHub do bạn chọn.
   Giữ cả thư mục .github/workflows.
2. Trong GitHub, mở Actions -> Build IntraCity Windows EXE -> Run workflow.
3. Khi job xanh, tải artifact IntraCity_2.3.1_Windows_x64 rồi giải nén EXE.
Workflow dùng máy Windows trên cloud, chỉ có quyền đọc repository.

BUILD TRÊN WINDOWS:
Cần Python 3.12 64-bit trên máy build. Mở PowerShell trong thư mục này rồi chạy:
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
Đầu ra: dist\IntraCity_2.3.1.exe

CHẠY EXE SAU KHI BUILD:
Windows 10/11 64-bit, có Google Chrome (như máy trong video).
Người chạy không cần cài Python. Playwright driver được đóng gói trong EXE.
Chromium không được đóng gói trong gói build này; app ưu tiên Chrome có sẵn.
Mở EXE -> Đăng nhập WMS -> chờ giao diện WMS hiện menu.
App nhận phiên, đóng cửa sổ Chrome -> bấm Tải COT Dashboard.
Nếu cookie không dùng được cho API, app sẽ báo lỗi phiên để đăng nhập lại.
