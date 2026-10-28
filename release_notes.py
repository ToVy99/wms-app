"""Bundled release notes. Opening this dialog never makes a network request."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QMessageBox

VERSION='3.4'
RELEASE_ID='3.4-sku-tab-persistent-wms-20261029'
TITLE='IntraCity 3.4'
NOTES='''<h2>Có gì mới trong IntraCity 3.4?</h2>
<ul>
<li><b>Tìm SKU thành tab chính:</b> COT / Excel–Outbound / Tìm SKU cùng một thanh chức năng, không mở cửa sổ riêng.</li>
<li><b>Gọn ứng dụng:</b> Gỡ phần năng suất không còn sử dụng và thành phần phụ thuộc.</li>
<li><b>Ghi nhớ WMS:</b> Chrome Profile riêng trên máy giữ phiên đăng nhập nếu Shopee còn cho phép. Hết hạn vẫn cần đăng nhập lại.</li>
<li><b>Một phiên Chrome/WMS:</b> COT và Tìm SKU cùng dùng một tab đã đăng nhập, không lưu mật khẩu trong file cấu hình.</li>
<li><b>Lọc Area bằng nút:</b> Chọn khu của trạng thái hiện tại, kể cả Picked.</li>
<li><b>Tra SKU:</b> Kết hợp tool tìm mã rổ, cho phép dừng tìm và giữ kết quả gần nhất.</li>
<li><b>Hai cách kết nối WMS:</b> Chrome riêng ghi nhớ phiên hoặc Chrome đang mở qua tiện ích.</li>
<li><b>Thống kê nhỏ gọn:</b> Giảm chiều cao các ô.</li>
<li><b>Excel / Outbound:</b> Giữ nguyên logic COT, lọc, thống kê và xuất dữ liệu.</li>
</ul>
<p><b>Chrome quản lý phiên trong hồ sơ người dùng trên máy, không ghi thông tin xác thực vào mã nguồn.</b></p>
<p><i>Thông báo hiện lần đầu. Bấm “Đã hiểu” để đóng, hoặc chọn “Xem thay đổi”.</i></p>
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
