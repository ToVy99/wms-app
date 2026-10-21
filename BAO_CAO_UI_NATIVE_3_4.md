# IntraCity 3.4 Beta — kiểm tra giao diện Native Check Prod (chưa build EXE)

## Thay đổi theo yêu cầu
- Thanh điều hướng COT / Excel-Outbound / Check Prod được chuyển thành hàng riêng, tab có chiều rộng ổn định và không hiện nút cuộn trái/phải; chỉ một tab Check Prod.
- Khu vực làm việc Sort / Check / Check Station / Check&Pack / Pack cũng ở hàng riêng, có chiều rộng cố định; Target Prod và nút tải dữ liệu ở hàng khác, tránh chen lấn.
- Bỏ chữ dài `Items/h hoặc Orders/h` cạnh Target. Chế độ Item / Order vẫn hiển thị ở đầu màn hình và quy tắc tính Target không thay đổi.
- Sáu nút BAU / CP / Item / Order / Ca 1 / Ca 2 có kích thước cố định 72 × 34 px; trạng thái chọn có nền màu nhấn, trạng thái thường tối/sáng theo giao diện chung.
- 5 thẻ KPI có biểu tượng riêng, nền bo góc, màu nhấn và chữ lớn. Các thành phần được dựng bằng PySide6, không nhúng WebEngine.

## Bảo toàn logic
So sánh cú pháp AST với bản `IntraCity_3.4_Beta_CheckProd_Native_Source_Trial.zip` cho thấy chỉ có:
- `WMSDashboard.build_ui` — bố cục tab chính.
- `CheckProdTab._build` — widget/bố cục Check Prod.
- `CheckProdTab.set_theme` — CSS Qt theo theme.

Không sửa `prod_native_core.py`, `prod_native_api.py`, `chrome_cot.py`, `cot_logic.py`, `sku_search_engine.py` và các công thức/API khác.

## Kết quả đã chạy ở môi trường hiện tại
- `python -m py_compile`: **đạt**.
- Python parity + static tests: **16/16 đạt** trước bổ sung bộ test bố cục.
- JavaScript original Productivity `tests/test_core.js`: **20/20 đạt**.
- Các bài test giao diện Qt `test_prod_native_layout.py`: **đã viết nhưng chưa thực thi được trên máy hiện tại vì thiếu PySide6**.
- Test Github Actions: **chưa chạy**. Kết nối GitHub trả `403 Resource not accessible by integration` khi tạo nhánh thử nghiệm dù đã đọc được repository.
- Build Windows EXE: **chưa chạy**, đúng yêu cầu.

## Kiểm thử Windows (chỉ test, không build)
Tại thư mục source, chạy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TEST_NATIVE_ONLY.ps1
```

Yêu cầu Python 3.12 và PySide6, ưu tiên môi trường `.venv-build` có sẵn. Workflow `.github/workflows/test-native-ui.yml` chỉ chạy unit/UI tests khi đẩy lên nhánh `codex/intracity-34-native-ui-tests`, **không tạo EXE**. Không tạo PR vì workflow build hiện tại có trigger `pull_request`.
