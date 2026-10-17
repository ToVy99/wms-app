"""Bundled release notes. Opening this dialog never makes a network request."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QMessageBox

VERSION='3.4'
RELEASE_ID='3.4-compact-bridge-fix-20261017'
TITLE='IntraCity 3.4'
NOTES='''<h2>Có gì mới trong IntraCity 3.4?</h2>
<p><b>Bổ sung ngày 17/10:</b></p>
<ul>
<li>Hoạt ảnh tải nằm gọn bên phải nút ⋯, cùng hàng với Lưu Excel gốc.</li>
<li>Nới rộng Wave Type, thu gọn ô tìm đơn; rê chuột để xem đầy đủ nội dung.</li>
<li>Đồng bộ trạng thái kết nối; ngắt cầu nối khi đóng hoặc tải lại tab WMS. Thêm nút Ngắt kết nối trong app.</li>
<li>Thêm nút Lưu tiện ích (.zip) ngay trong cửa sổ kết nối. Chỉ cần gửi EXE cho người dùng.</li>
</ul>
<p><b>Các thay đổi của bản 3.4:</b></p>
<ul>
<li><b>Giao diện gọn hơn:</b> chuyển COT / Excel–Outbound lên giữa thanh trên cùng, tăng diện tích bảng đơn.</li>
<li><b>Thu gọn thao tác:</b> gom các nút chọn đơn, bỏ chọn, Copy OBVN và Picking ID / BSK vào menu Thao tác. Đưa “Lưu Excel gốc” gần nút Tải dữ liệu.</li>
<li><b>Giữ thống kê khu vực:</b> bỏ ô lọc Area, vẫn giữ cột Area và số lượng đơn từng khu để dễ so sánh.</li>
<li><b>Trạng thái dễ nhìn hơn:</b> ẩn các ô Pick Fail, Pre Sorting và Pre Sorted. Các đơn này vẫn được tính trong tổng.</li>
<li><b>Picked có mã rổ — tự loại trùng:</b> chỉ lấy mã rổ của đơn đang Picked, mỗi mã rổ hiển thị một lần.</li>
<li><b>Hai cách kết nối WMS:</b> bấm “Đăng nhập WMS” để chọn mở Chrome riêng như trước hoặc dùng Chrome đang mở qua tiện ích kết nối. Mỗi lần tải chỉ sử dụng kết nối đang chọn.</li>
<li><b>Thống kê nhỏ gọn:</b> giảm chiều cao các ô Tổng đơn, Outbound và Tỷ lệ, giữ số lớn và màu nổi bật.</li>
<li><b>Tìm Task theo SKU nhanh hơn:</b> Kết hợp tool tìm mã rổ (WMS_SKU_Task_Finder) vs app.</li>
<li><b>Dừng tìm khi cần:</b> nút Dừng hủy các yêu cầu tìm SKU đang chạy, không tiếp tục gửi lượt mới.</li>
</ul>
<p>Giữ nguyên logic . Các thay đổi giao diện không làm thay đổi dữ liệu gốc.</p>
<p><i>Thông báo hiện lần đầu khi mở phiên bản mới. Bấm “Đã hiểu” để đóng; mở lại bằng “Xem thay đổi”.</i></p>
<p><b>Đỗ Rê Mon♥</b></p>'''

def show_changes(window,save_config,automatic=False):
    if automatic and window.config.get('seen_release_id')==RELEASE_ID:return
    existing=getattr(window,'_whats_new_dialog',None)
    if existing is not None and existing.isVisible():existing.raise_();return
    dialog=QDialog(window);window._whats_new_dialog=dialog
    dialog.setWindowTitle('Có gì mới? — '+TITLE);dialog.resize(650,510)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    layout=QVBoxLayout(dialog);text=QTextBrowser();text.setHtml(NOTES);layout.addWidget(text)
    button=QPushButton('Đã hiểu');layout.addWidget(button);button.clicked.connect(dialog.accept)
    def acknowledge():
        previous=window.config.get('seen_release')
        previous_id=window.config.get('seen_release_id')
        window.config['seen_release']=VERSION
        window.config['seen_release_id']=RELEASE_ID
        if not save_config(window.config):
            if previous_id is None:window.config.pop('seen_release_id',None)
            else:window.config['seen_release_id']=previous_id
            if previous is None:window.config.pop('seen_release',None)
            else:window.config['seen_release']=previous
            QMessageBox.warning(window,'Chưa lưu được','Lần mở sau thông báo có thể xuất hiện lại vì chưa lưu được cấu hình.')
    dialog.accepted.connect(acknowledge)
    dialog.finished.connect(lambda _:dialog.deleteLater())
    dialog.finished.connect(lambda _:setattr(window,'_whats_new_dialog',None))
    if hasattr(window,'theme_controller'):window.theme_controller.apply()
    dialog.open()
