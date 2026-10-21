# Check Prod 3.4 — bảng nhân viên và dữ liệu riêng từng tab

Nhánh: `codex/intracity-34-native-ui-tests`. Mốc đối chiếu trước sửa: `07624ef`.

## Thay đổi

- STT và tên/email hai dòng được cố định khi cuộn ngang. Các dòng cao 56 px, có nền xen kẽ và đường phân cách; giữ tính năng bấm tên để tô sáng nhân viên.
- Cả Sort, Check, Check Station, Check&Pack, Pack có Item, Order, giờ công và các cột Item/Order/giờ công cho từng giờ.
- Hai ô giờ nhập tay HH:mm, không tự chọn ca hoặc “Hiện tại”. `07:00–18:59` bao gồm đến 18:59:59; hỗ trợ phút lẻ và qua đêm. Khung chưa nhập, sai định dạng hoặc ở tương lai được báo để người dùng sửa.
- Mỗi tab giữ bộ dữ liệu thành công gần nhất, KPI, khung giờ, đơn vị, bộ lọc, chiều sắp xếp, target đang nhập, độ rộng cột, vị trí cuộn và nhân viên tô sáng.
- Chỉ nút **Tải dữ liệu** bắt đầu yêu cầu mới. Đổi giờ hoặc đơn vị chỉ sửa lựa chọn cho lần tải tiếp theo; dòng trạng thái ghi khung/đơn vị của dữ liệu đang hiển thị.
- Tải lỗi giữ bộ dữ liệu cũ. Chuyển tab khi đang tải không đưa kết quả sang nhầm tab. Chỉ thay dữ liệu sau khi hoàn thành toàn bộ yêu cầu bắt buộc.
- Giữ KPI gọn, biểu tượng và Prod trung bình cho mọi tab; màu bảng đồng bộ sáng/tối.
- Xuất Excel theo bảng đang xem, cố định STT/nhân viên và hàng tiêu đề.

## Nguồn dữ liệu và giới hạn

- Số lượng mới hiển thị lấy `sum_count`, giờ lấy `man_hour` từ API productivity hiện có; không suy ngược Item/Order bằng Prod × giờ công. Không có trường số lượng thì hiển thị `—`; số 0 vẫn là 0.
- Hai đơn vị được truy vấn riêng, chia đúng các đoạn giờ nằm trong khung đã nhập. Cache chỉ dùng trong một lần tải để tránh gọi lại cùng truy vấn.
- Tab Station dùng `dim_type=station`; các số lượng đó thuộc Station, không phân bổ ngược cho người thao tác cuối. Tooltip ở tiêu đề làm rõ ý nghĩa này.
- Giữ nguyên `prod_native_core.py`, `prod_native_api.py`, công thức/xếp hạng Prod cũ, COT, SKU và bridge. KPI tổng sản lượng dùng tổng trường gốc; công thức Tổng Prod/Prod trung bình cũ, kể cả cách xử lý thiếu dữ liệu cũ, được bảo toàn.
- Mỗi giờ cần hai truy vấn Item/Order, có thể thêm phân trang; tải dài hơn so với chỉ lấy tổng. Cơ chế retry 429/503 cũ được giữ nguyên.
- Chưa kiểm tra với phiên WMS đang đăng nhập hoặc bản xuất thực tế. Kiểm thử dùng fixture, phản hồi giả lập và dữ liệu minh họa; không đọc thông tin xác thực.

## Kiểm thử trước build

84 kiểm thử thuộc các bộ sau đã được xác minh trên Windows local (Qt offscreen):

`test_prod_snapshots test_prod_time_range test_native_prod_parity test_checkprod_34_static test_native_ui_static test_prod_native_layout test_area_buttons_release34 test_native_cot test_theme test_release33 test_sku_finder test_bridge34`

Ba kiểm thử socket localhost của bridge bị sandbox chặn, sau đó cả bộ bridge 6 test chạy lại thành công ngoài sandbox. Các kiểm thử UI mới bao phủ giữ trạng thái cả 5 tab, bấm tên trên cột cố định, đồng bộ hàng/scroll, khung qua đêm/phút lẻ, dữ liệu gốc 0/thiếu, đơn vị đang sửa, tải lỗi và trả kết quả đúng tab nguồn.

Ảnh sáng/tối và cuộn ngang đã kiểm tra bằng dữ liệu minh họa. Workflow `test-native-ui.yml` chạy kiểm thử trên `windows-latest` khi push đúng nhánh. Workflow EXE thử nghiệm đã chuyển sang chỉ `workflow_dispatch`: chưa build EXE, chưa sửa/merge main.
