IntraCity 2.4.0 — Web v1.4 trong app, gọi WMS qua Chrome

CHẠY: Windows 10/11 64-bit có Google Chrome. Không cần Python.
1. Mở IntraCity_2.4.0.exe, bấm Đăng nhập WMS.
2. Đăng nhập và chọn kho trong Chrome vừa mở. Chrome được giữ chạy.
3. Trong app chọn ngày, nhóm và COT, rồi bấm Tải dữ liệu.
4. App tạo một Export WMS, kiểm tra tiến độ mỗi 3 giây trong tối đa 3 phút,
   tải Excel và đọc toàn bộ đơn từ file; không tải lại danh sách đơn theo trang.
5. Bấm trạng thái để xem đơn; Wave Type/OBVN/Picking ID/BSK lấy từ Excel.
   Như web v1.4, bấm trạng thái còn nạp Area qua search_order, 200 đơn/trang,
   tối đa 10 trang. Area được lưu trong lượt dữ liệu hiện tại, không tự cập nhật.
   Các trang Area cách nhau 1 giây. Nếu trên 2000 đơn, app báo Area giới hạn.
6. Copy OBVN, chọn đơn, xem/copy Picking ID và BSK như trên web v1.4.
7. Cài đặt COT cho phép sửa tên/giờ, lưu trên máy.

Mở app/đổi ngày/đổi nhóm/đổi COT không tự gọi API.
Khi đổi khung, dữ liệu cũ được xóa để tránh hiện nhầm COT.
Lỗi HTTP 429 dừng tác vụ, không tự thử lại.
Tất cả API và tải report thực hiện bằng fetch trong tab Chrome WMS,
credentials: include; không sao chép cookie để gửi request Python.
Chrome mở không đồng nghĩa đã đăng nhập: cần đăng nhập và chọn kho trước.
Nếu đóng Chrome, bấm Đăng nhập WMS để mở phiên mới và đăng nhập lại.
App không lưu cookie WMS mới; chỉ lưu cài đặt. Đóng app sẽ đóng Chrome do app mở.

LOGIC WEB V1.4:
- Intra: SPX Express / SPX Express NDD - Trong Ngày và Hà Nội / Thành phố Hà Nội.
- AhaMove: Ahamove / Ahamove SBS, nhận hậu tố - Trong Ngày; không lọc tỉnh.
- SDD: SPX Express SBS Trong Ngày (kể cả biến thể dấu gạch); không lọc tỉnh.
- SPX CK: SPX - Hàng Cồng Kềnh; không lọc tỉnh. Không còn GHN.
- Gom theo WMS Order No, gom SN/Picking ID/Device ID/Basket ID, loại Cancel.
- Bộ lọc Export theo Create Time và extra_data giống web v1.4.
- Ngày chọn là ngày bắt đầu khung; khung qua đêm kết thúc hôm sau.
  Riêng SPX CK: 17h hôm trước đến 17h ngày chọn.
- Intra: 20–23, 23–02 (+1), 02–16, 16–20.
- AhaMove: 08–13, 13–18, 18–08 (+1).
- SDD: 18–04 (+1), 04–09, 09–13:30, 13:30–18.
- Status theo web: 0 Created, 1 Pending Pick, 2 Picking, 3 Picked, 4 Pick Fail,
  5 Checking, 6 Checked, 7 Pre Sorting, 8 Pre Sorted, 9 Sorting, 10 Sorted,
  11 Packing, 12 Packed, 13 Shipping, 14 Outbound, 15 Cancel.
- Tiến độ và Wave Type % giữ như web v1.4; Outbound / tổng OBVN sau loại Cancel.

Tab Excel / Outbound của app cũ vẫn dùng được.
Cấu hình ở %LOCALAPPDATA%\IntraCity\wms_config.json.
BUILD: Python 3.12 Windows 64-bit, chạy build_windows.ps1.
KIỂM TRA: renderer thật đọc XLSX, 2112 đơn qua một Export, lọc New 3PL/tỉnh,
Cancel, dedupe, Wave Type, Picking/BSK, cài đặt/copy; EXE kiểm tra Chrome fetch
và cookie với dữ liệu giả lập, không dùng tài khoản WMS thực tế.
