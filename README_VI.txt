INTRACITY 2.4.3 — APP GỌN, LOGIC COT WEB 1.4

Chạy IntraCity_2.4.3.exe trên Windows 10/11 64-bit có Google Chrome.
Không cần cài Python. Đăng nhập WMS → đăng nhập và chọn kho trong Chrome → trở lại app chọn nhóm, ngày và nút COT → Tải dữ liệu.
Chrome giữ mở để đổi kho. Khi đổi kho, bấm Tải dữ liệu để thay bộ đơn.

Giao diện COT dùng điều khiển app trực tiếp; bỏ QtWebEngine và bản sao giao diện web để giảm dung lượng EXE.
Giữ tab Excel/Outbound cũ. Giữ logic và luồng API web 1.4:
- Một Export cho khung COT đang chọn; tải report một lần, gom WMS Order No, loại Cancel.
- API chạy trong tab Chrome WMS đã đăng nhập. Không lấy cookie ra Python.
- Không mở Chrome hoặc gọi WMS khi khởi động, đổi ngày, đổi COT, nhóm.
- Không tự tải lại, không thử lại lỗi 429. Chỉ kiểm tra tiến độ Export sau lượt tải do người dùng bấm: mỗi 3 giây, tối đa 60 lần.
- Bấm trạng thái hiện đúng các đơn trong trạng thái, nạp thêm Area 200 đơn/trang, cách nhau 1 giây, tối đa 10 trang theo giới hạn WMS. Cache Area trong bộ đơn; số lượng toàn bộ đơn vẫn lấy từ Export.
- Lọc Area/Wave và Copy OBVN/Picking ID/BSK thực hiện trên dữ liệu đã tải.
- Chọn các đơn đang hiện hoặc chọn từng đơn để Copy/Picking; nếu chưa chọn, dùng toàn bộ các đơn đang hiện.
- Outbound % = Outbound / tổng đơn hợp lệ. Wave % = số đơn Wave / số đơn trạng thái đang chọn, giống web 1.4.
- Có nút Khung giờ để sửa tên, giờ và khôi phục mặc định. Cài đặt cũ của bản 2.4.0 được giữ.

GIỜ MẶC ĐỊNH — GIỜ CHÍNH XÁC, KHÔNG CỘNG 59 PHÚT
Intra: 20–23; 23–02 hôm sau; 02–16; 16–20.
AhaMove: 08–13; 13–18; 18–08 hôm sau.
SDD: 18–04 hôm sau; 04–09; 09–13:30; 13:30–18.
SPX CK: 17h ngày trước → 17h ngày đang chọn.
Ngày được hiểu như web 1.4: ngày bắt đầu với khung qua đêm, ngày kết thúc với SPX CK. Sử dụng múi giờ Windows; tại Việt Nam cần đặt giờ Việt Nam.

BỘ LỌC REPORT — NEW 3PL
Intra: SPX Express / SPX Express NDD - Trong Ngày, Buyer State Hà Nội hoặc Thành phố Hà Nội.
AhaMove: Ahamove / Ahamove SBS, nhận hậu tố sau dấu gạch, không giới hạn tỉnh.
SDD: SPX Express SBS Trong Ngày và biến thể dấu gạch/hậu tố, không giới hạn tỉnh.
SPX CK: SPX - Hàng Cồng Kềnh, không giới hạn tỉnh.

BUILD
Python 3.12 64-bit trên Windows → chạy build_windows.ps1.
11 kiểm thử logic/UI trước khi build; kiểm tra EXE thật với Chrome và API giả lập sau build, không gọi WMS thật trong kiểm thử.
Đăng nhập/kho WMS thực tế cần kiểm tra bằng tài khoản của người dùng.


SỬA 2.4.3: Đọc toàn bộ dữ liệu thật trong XLSX khi WMS ghi sai vùng dữ liệu A1. Không thay luồng API, không tải lại report.


GIAO DIỆN 2.4.3
- Trạng thái nằm ở khung bên phải, số đơn lớn.
- Tổng đơn, số Outbound và % Outbound là ba thẻ nổi bật.
- Nút Picked có mã rổ lọc toàn bộ đơn Picked có Device ID/Basket ID hợp lệ trong report đang tải; bấm lại hiện tất cả Picked. Không gọi API thêm.
- Bảng có cột Mã rổ / BSK để xem trực tiếp. Khi bấm bộ lọc mã rổ, bỏ các đơn đã chọn trước đó để Copy đúng các đơn đang lọc.
