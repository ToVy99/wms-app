"""Bundled release notes. Opening this dialog never makes a network request."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QMessageBox

VERSION='3.4'
RELEASE_ID='3.4-checkprod-native-area-ui-notes-20261021'
TITLE='IntraCity 3.4'
NOTES='''<h2>Có gì mới trong IntraCity 3.4?</h2>
<p><b>Bổ sung Check Prod trong bản thử nghiệm 3.4:</b></p>
<ul>
<li><b>Check Prod:</b> Một tab chức năng cạnh Excel / Outbound, mở bảng năng suất Sort, Check, Check Station, Check&amp;Pack, Pack.</li>
<li><b>Một phiên Chrome/WMS:</b> Check Prod dùng cầu nối (tiện ích) Chrome đã đăng nhập, không yêu cầu đăng nhập riêng. Bổ sung kết nối lại sau khi tab WMS tải lại nếu phiên còn hợp lệ.</li>
<li><b>Lọc Area bằng nút:</b> Nhấn khu A để chỉ xem đơn thuộc khu A của trạng thái đang chọn, kể cả Picked. Đổi trạng thái giữ lựa chọn khu.</li>
</ul>
<p><b>Bổ sung ngày 17/10:</b></p>
<ul>
<li>Hoạt ảnh tải nằm gọn bên phải nút ⋯, cùng hàng với Lưu Excel gốc.</li>
<li>Nới rộng Wave Type, thu gọn ô tìm đơn; rê chuột để xem đầy đủ nội dung.</li>
<li>Đồng bộ trạng thái kết nối; ngắt khi đóng tab WMS, thử tự khôi phục sau khi tab tải lại nếu phiên còn hợp lệ. Thêm nút Ngắt kết nối trong app.</li>
<li>Thêm nút Lưu tiện ích (.zip) ngay trong cửa sổ kết nối.</li>
</ul>
<p><b>Các thay đổi của bản 3.4:</b></p>
<ul>
<li><b>Giao diện gọn hơn:</b> Chuyển COT / Excel–Outbound lên giữa thanh trên cùng, tăng diện tích bảng đơn.</li>
<li><b>Thu gọn thao tác:</b> Gom các nút chọn đơn, bỏ chọn, Copy OBVN và Picking ID / BSK vào menu Thao tác. Đưa “Lưu Excel gốc” gần nút tải dữ liệu.</li>
<li><b>Giữ thống kê khu vực:</b> Bỏ ô lọc Area, vẫn giữ cột Area và số lượng đơn từng khu để dễ so sánh.</li>
<li><b>Trạng thái dễ nhìn hơn:</b> Ẩn các ô Pick Fail, Pre Sorting và Pre Sorted. Các đơn này vẫn được tính trong tổng.</li>
<li><b>Picked có mã rổ — tự loại trùng:</b> Chỉ lấy mã rổ của đơn đang Picked, mỗi mã rổ hiển thị một lần.</li>
<li><b>Hai cách kết nối WMS:</b> Bấm “Đăng nhập WMS” để chọn mở Chrome riêng như trước hoặc dùng Chrome đang mở qua tiện ích kết nối. Mỗi lần tải chỉ sử dụng kết nối đang chọn.</li>
<li><b>Thống kê nhỏ gọn:</b> Giảm chiều cao các ô.</li>
<li><b>Tìm Task theo SKU nhanh hơn:</b> Kết hợp tool tìm mã rổ (WMS SKU Task Finder) với app.</li>
<li><b>Dừng tìm khi cần:</b> Nút Dừng hủy các yêu cầu tìm SKU đang chạy, không tiếp tục gửi lượt mới.</li>
</ul>
<p><b>Giữ nguyên logic. Các thay đổi giao diện không làm thay đổi dữ liệu gốc.</b></p>
<p><i>Thông báo hiện lần đầu khi mở phiên bản mới. Bấm “Đã hiểu” để đóng; mở lại bằng “Xem thay đổi”.</i></p>
<p><b>Đỗ Rê Mon♥!</b></p>'''

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
