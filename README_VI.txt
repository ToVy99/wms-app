IntraCity 3.2 — giao diện cập nhật (mã nội bộ 3.2)

Các thay đổi:
- Sẵn sàng làm việc nằm cùng hàng Đăng nhập WMS.
- Các nút COT nằm trong một hàng, nút đang chọn sáng vàng.
- Tổng đơn, Outbound và tỷ lệ % có nền màu nổi bật, số lớn và thanh tiến độ.
- Khung trạng thái bên phải giữ vị trí cố định khi dữ liệu thay đổi.
- Ô tìm kiếm cạnh Picked có mã rổ: tìm OBVN, Order SN, Picking ID,
  Device ID, Basket ID, Area, Wave Type, thời gian và mọi giá trị của report.
  Không phân biệt hoa/thường hoặc dấu tiếng Việt. Nhiều từ được tìm cùng nhau
  trên một đơn. Tìm kiếm kết hợp với trạng thái/Area/Wave/mã rổ đang chọn.
  Xóa nội dung hoặc bấm nút X trong ô để bỏ tìm kiếm.
- Tìm kiếm dùng dữ liệu đã tải, không gọi thêm API WMS.
- Tỷ lệ % và các ô tổng vẫn tính trên toàn bộ dữ liệu COT, không đổi khi tìm kiếm.
- Đã kèm app.ico và sửa icon cửa sổ + icon EXE.

ĐÓNG GÓI TRÊN WINDOWS:
1. Cài Python 3.12 bản 64-bit và Google Chrome.
2. Giải nén toàn bộ bộ mã nguồn vào một thư mục mới.
   Giữ app.ico cùng thư mục với launcher.py và build_windows.ps1.
3. Mở PowerShell trong thư mục này, chạy:
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\build_windows.ps1"
4. Sau khi build và kiểm tra hoàn tất, file chạy nằm tại:
   dist\IntraCity 3.2.exe

Không chỉ đóng gói một file .py; giữ đầy đủ các file của bộ nguồn này.
Script dùng py -3.12, tạo .venv-build, cài các thư viện cần thiết,
chạy kiểm tra, rồi đóng gói và kiểm tra khởi động EXE.

SỬ DỤNG:
Bấm Đăng nhập WMS, đăng nhập và chọn kho trong Chrome.
Chọn nhóm, ngày, COT rồi bấm Tải dữ liệu.
Giữ Chrome mở trong khi sử dụng. Mỗi lần tải dùng một tác vụ Export
và một lượt tải report; không tự tải lại khi đổi COT, ngày hoặc nhóm.
Ảnh xem trước đi kèm dùng dữ liệu minh họa, không phải dữ liệu WMS thật.

CẬP NHẬT SKU / KHU / TỐC ĐỘ:
- Bảng COT có SKU Name, gộp đủ các SKU của cùng OBVN và giữ một đơn.
  Rê chuột để xem đầy đủ tên, tìm kiếm SKU dùng ô tìm kiếm hiện có.
- Area gộp theo toàn bộ phần chữ: A1/A2 -> A, LC1/LC2 -> LC, CF giữ CF.
  Dòng KHU VỰC hiện số đơn theo trạng thái/bộ lọc mã rổ đang chọn.
  Chọn khu trong Area để lọc đơn ngay, không phát sinh API.
  Một đơn nhiều khu tính một lần ở mỗi khu, tổng khu có thể lớn hơn tổng đơn.
- Report hiện không có Area. Area vẫn nạp bổ sung khi bấm trạng thái,
  chưa tự nạp tất cả. Giữ giới hạn hiện có 2000 đơn/trạng thái.
  Có Area / Chưa có Area cho biết dữ liệu đang đầy đủ tới đâu; số thiếu
  có thể là chưa nạp hoặc WMS không trả khu, không xem số thiếu là 0 đơn.
- Bổ sung python-calamine vào bộ cài/build. Dùng bộ đọc nhanh Calamine
  ở cả tab Excel và parser COT; OpenPyXL là dự phòng khi không đọc được.
- Ngày COT qua đêm vẫn là ngày bắt đầu, ví dụ 01:00 ngày 08/10
  muốn xem Intra COT2 đang chạy thì chọn 07/10, khung 07/10 23h -> 08/10 02h.

GIAO DIỆN v3.1:
- Góc trên bên phải: Giao diện -> Theo máy / Sáng / Tối.
- Mặc định Theo máy; tự theo chế độ giao diện của Windows nếu hệ điều hành
  cung cấp thông tin màu. Nếu không, dùng giao diện sáng.
- Chọn Sáng hoặc Tối để giữ cố định, không phụ thuộc Windows.
- Lựa chọn lưu trong cấu hình IntraCity, giữ khi mở lại app.
- Áp dụng cho cả COT, Excel/Outbound và các hộp thoại.
- Giữ màu KPI nổi bật, nút COT/trạng thái chọn màu vàng.
- Đổi giao diện không xóa dữ liệu, không đổi bộ lọc và không gọi WMS.
- Giữ SKU Name, thống kê khu Area và bộ đọc nhanh Calamine từ bản trước.
- Export lọc trước theo nhà vận chuyển và khung COT: Intra 50057/50021,
  AhaMove 50033/50044, SDD 50051, CK 50025. Vẫn lọc lại report sau tải.

THÔNG BÁO CẬP NHẬT KHI APP ĐANG MỞ:
- Kiểm tra version.json trên GitHub khi mở và mỗi 10 phút.
- Chỉ kiểm tra thông tin phiên bản, không gọi WMS và không tải lại đơn.
- Không chạy chồng nhiều lượt kiểm tra. Không có mạng thì bỏ qua lượt đó.
- Chỉ báo một lần cho mỗi phiên bản mới trong một lần mở app.
- Chỉ tải/cài bản mới sau khi bạn chọn Có trong thông báo.
- Cần nâng version trong version.json cao hơn 3.2, cập nhật changelog và
  download_url trỏ đúng file EXE của bản mới. Không chỉ thay file EXE mà giữ
  version bằng 3.2, vì app sẽ coi đó là cùng phiên bản.

SỬA MỞ DANH SÁCH 3PL / BUYER STATE:
- Không đặt lại bảng màu ứng dụng mỗi lần thay đổi focus.
- Danh sách có nền/chữ riêng theo Sáng/Tối từ lúc khởi động.
- Bấm phần chữ hoặc mũi tên của 3PL/Buyer State để mở danh sách.
- Giữ nguyên các lựa chọn lọc khi đổi giao diện.
