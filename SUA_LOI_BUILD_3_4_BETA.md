# Khắc phục build IntraCity 3.4 Beta — 21/10/2026

## Lỗi nhận được
Build Windows dừng tại bài test Python: 46/48 đạt; 2 bài không đạt.
- `test_native_cot.NativeTests.test_picked_basket_filter_is_local_and_counts_stay_global`: bài test cũ giả định bộ lọc Area bị xoá khi bật Picked có mã rổ. IntraCity 3.4 mới giữ lựa chọn Area theo yêu cầu. Đã cập nhật bài test để kiểm tra việc bảo toàn Area, lọc rỗng khi Area không khớp, sau đó bỏ Area và xác minh việc nhóm mã rổ.
- `test_theme.ThemeTests.test_filter_popups_open_on_first_click_and_after_theme_switch`: kiểm tra cũ đòi popup hiển thị bằng `isVisible()` khi chạy Qt `offscreen`, môi trường không bảo đảm việc hiển thị popup. Bài test mới kiểm tra tương tác chuột có gọi `showPopup()` và kiểm tra hiển thị thực sự khi chạy bằng Qt desktop; các điều kiện nội dung, trạng thái checkbox và theme giữ nguyên.

## Phạm vi chỉnh sửa
Chỉ thay đổi `test_native_cot.py` và `test_theme.py`; **không sửa** `chrome_cot.py`, `cot_logic.py`, giao diện, `productivity`, `extension_bridge`, phần tìm SKU hay các công thức nghiệp vụ. Không thay đổi số phiên bản (3.4).

## Build lại
Giải nén ZIP mới vào thư mục mới, tránh ghi đè thư mục cũ.
Mở PowerShell ở thư mục chứa `build_windows.ps1`, chạy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1
```

Nếu bạn đã có thư mục `.venv-build`, có thể sử dụng lại nhưng script hiện tại sẽ tạo/cập nhật môi trường theo yêu cầu.

## Trạng thái xác minh
- Python `compileall` đã đạt.
- `python -m unittest -v test_checkprod_34_static`: 5/5 đạt.
- Chưa thể chạy toàn bộ 48 test Qt và build EXE Windows trong môi trường này, vì thiếu PySide6 và không có Windows.
- Vui lòng kiểm tra cửa sổ popup 3PL/Buyer State thủ công trên Windows sau khi build thành công.
