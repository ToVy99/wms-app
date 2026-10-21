BỔ SUNG 17/10 — INTRACITY 3.4
- Hoạt ảnh tải nằm cùng hàng, bên phải nút ⋯.
- Wave Type rộng hơn; rê chuột để xem đủ nội dung.
- Cửa sổ kết nối hiển thị đúng trạng thái và có nút Ngắt kết nối.
- Khi tab WMS tải lại, tiện ích thử tự kết nối lại vào đúng tab nếu phiên còn hợp lệ; đóng tab/đăng xuất vẫn ngắt.
- Trong app chọn Đăng nhập WMS > Dùng Chrome đang mở qua tiện ích > Lưu tiện ích (.zip). Không cần tải ZIP riêng.
- Nếu đã cài tiện ích từ bản trước: mở cửa sổ kết nối trong app để cập nhật thư mục, sau đó vào chrome://extensions và bấm Tải lại tiện ích. Nếu cài từ thư mục tự giải nén, lưu ZIP mới và cập nhật đúng thư mục đó.

INTRACITY 3.4 — HAI CÁCH KẾT NỐI WMS

1. MỞ CHROME RIÊNG (CÁCH CŨ)
- Chạy IntraCity 3.4.exe.
- Bấm Đăng nhập WMS > Mở Chrome riêng / Đăng nhập WMS.
- Đăng nhập, chọn đúng kho rồi bấm Tải dữ liệu hoặc mở Tìm SKU.
- Không cần cài tiện ích.

2. DÙNG CHROME ĐANG MỞ
Thiết lập lần đầu, bằng chính tài khoản Windows đang dùng Chrome:
- Đặt EXE vào thư mục cố định (không chạy ngay bên trong ZIP).
- Trong app: Đăng nhập WMS > Dùng Chrome đang mở qua tiện ích.
- App chuẩn bị cầu nối và hiển thị đường dẫn thư mục tiện ích.
- Mở chrome://extensions trong Chrome, bật Chế độ dành cho nhà phát triển.
- Chọn Tải tiện ích đã giải nén (Load unpacked), chọn đúng thư mục app vừa mở.
- Trong Chrome, mở tiện ích IntraCity (biểu tượng mảnh ghép), chọn tab WMS đã
  đăng nhập đúng kho rồi bấm Kết nối tab đã chọn.
- Khi app báo Tiện ích Chrome đã kết nối, bấm Tải dữ liệu hoặc Tìm SKU như cũ.

Những lần sau:
- Mở app > Đăng nhập WMS > Dùng Chrome đang mở qua tiện ích.
- Trong tiện ích, chọn tab WMS và bấm Kết nối. Không phải đăng nhập lại nếu
  phiên WMS của tab đó còn hiệu lực.
- Sau khi tab WMS tải lại, app thử tự khôi phục vào cùng tab; nếu đăng xuất, đóng tab hoặc chọn kho khác thất bại thì kết nối lại thủ công.
- Nếu đổi vị trí file EXE, chọn lại cách kết nối tiện ích trong app để cập nhật
  đường dẫn cầu nối. Nếu cập nhật tiện ích, bấm nút Tải lại trên chrome://extensions.
- Nếu máy công ty chặn cài tiện ích, cách Mở Chrome riêng vẫn dùng như trước.

Mỗi tác vụ chỉ chạy trên một kết nối. Không đổi kết nối giữa khi đang tải COT
hoặc tìm SKU. Có thể giữ Chrome riêng mở khi chuyển sang dùng tiện ích.
Tiện ích chỉ được truy cập website WMS. Không chuyển cookie hoặc mật khẩu về app.
Không tự tải đơn khi mở app. Thông tin trạng thái kết nối trao đổi trên máy.
Dừng tìm SKU sẽ hủy các yêu cầu đang chạy và không gửi lượt tiếp theo.

PICKED CÓ MÃ RỔ
- Mỗi mã rổ là một dòng, gom đủ OBVN, SN, Picking ID, SKU và khu vực liên quan.
- Một đơn có nhiều mã rổ sẽ góp vào từng mã rổ đó; dữ liệu đơn gốc không bị xóa.
- Copy OBVN / xem Picking ID qua menu Thao tác lấy đủ đơn của các dòng đang chọn.
- Tổng đơn, tỷ lệ và thống kê khu vực vẫn đếm theo đơn, không chuyển thành số rổ.

MÃ NGUỒN VÀ TỰ BUILD
- Windows 10/11 64-bit, Python 3.12; chạy build_windows.ps1 trong thư mục nguồn.
- Cần giữ đủ các file .py, app.ico và các file wms_bridge_* khi build.
- Script build chạy kiểm thử, đóng gói EXE, mở thử app và kiểm thử tiện ích
  với dữ liệu giả lập. Không sử dụng tài khoản hoặc gọi WMS thật.


--- HƯỚNG DẪN CÁC TÍNH NĂNG ĐÃ CÓ ---
IntraCity 3.4.2 — giao diện cập nhật (mã nội bộ 3.4.2)

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
   dist\IntraCity 3.4.2.exe

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

CẬP NHẬT 3.3:
- Đọc mọi XLSX trong ZIP (kể cả thư mục con), mọi sheet dữ liệu đơn.
- Gom OBVN xuyên file/sheet, giữ nguyên lọc và tính %; báo lỗi nếu file hỏng.
- Thu gọn thống kê, bảng đơn trượt phủ phần trên, lưu vị trí kéo.
- Chọn ô/cột màu vàng và Ctrl+C, thêm cột Picking ID và bảng Picking ID/BSK.
- Mã rổ chỉ hiện cho Picked, bỏ tổng trên nút Picked có mã rổ.
- Lưu Excel gốc lưu nguyên bytes lần tải gần nhất (XLSX/ZIP), không gọi WMS.
- Có gì mới hiện lần đầu phiên bản; Đã hiểu để lưu, Xem thay đổi để đọc lại.

CẬP NHẬT 3.3.1:
- Giữ dữ liệu cũ và bộ lọc đến khi đọc report mới thành công; lỗi vẫn giữ bảng cũ.
- Ghi rõ khung giờ dữ liệu đang hiển thị, kể cả khi chọn COT khác.
- Vòng xoay xanh và giai đoạn tải cạnh nút Tải dữ liệu; không thêm API.
- Nút tải nền cam vàng, có hover và khóa khi đang xử lý.

CẬP NHẬT 3.4:
- Cửa sổ mở vừa vùng màn hình, có thể phóng to. Màn nhỏ có thanh cuộn dự phòng.
- Nút Tìm Task theo SKU ở góc phải thanh tab, dùng chung phiên Chrome WMS.
- Nhập/quét SKU/UPC rồi Enter: tìm đơn Picked -> SN -> Picking Task 7 ngày giờ VN.
- Hiện Task ID, Order Structure, BSK, SKU Qty, Item Qty và số SN khớp.
- Copy BSK từng task hoặc tất cả không trùng. Chọn ô/cột rồi Ctrl+C.
- API chạy tuần tự, nghỉ 300ms giữa yêu cầu; thử lại tối đa 2 lần khi lỗi như tiện ích gốc. Nút Dừng ngừng
  các yêu cầu tiếp theo, yêu cầu đã gửi sẽ chờ phản hồi. Kết quả cũ giữ khi lỗi.
- Giữ giới hạn của tiện ích: 2000 đơn, tối đa 100 task/SN; hiện cảnh báo nếu thiếu.
- Không áp dụng bộ lọc COT vào tìm SKU; tra kho đang chọn trong Chrome như tiện ích.

CẬP NHẬT 3.4.2 (chỉ công cụ tìm Task theo SKU):
- list thiếu/null được coi là rỗng như tiện ích.
- Thử lại tối đa 2 lần, chờ 200/400ms; lỗi đăng nhập dừng ngay.
- SN lỗi sau các lần thử được ghi cảnh báo; vẫn hiện task của SN thành công.
- Không áp giới hạn 25 giây cho SKU; thời gian chờ COT giữ nguyên.
- API vẫn chạy tuần tự để hạn chế tải server; chỉ bắt đầu khi bấm tìm.

CẬP NHẬT 3.4.2: Tìm SKU chạy thực sự song song trong Chrome: tối đa 5 trang đơn/lượt và 6 SN tra Task; bỏ nghỉ 300ms. Giữ thử lại 2 lần, lỗi SN riêng và giới hạn dữ liệu của tiện ích. Nút Dừng hủy fetch SKU đang chạy. COT/Excel không đổi.
