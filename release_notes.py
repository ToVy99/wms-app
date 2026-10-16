"""Bundled release notes. Opening this dialog never makes a network request."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QMessageBox

VERSION='3.4.2'
TITLE='IntraCity 3.4.2'
NOTES='''<h2>Có gì mới trong IntraCity 3.4.2?</h2>
<ul>
<li><b>Tìm SKU nhanh như tiện ích web:</b> tối đa 5 trang đơn và 6 SN tra Task đồng thời; bỏ khoảng nghỉ 300ms. Nút Dừng hủy các yêu cầu SKU đang chạy.</li>
<li><b>Sửa tìm Task theo SKU:</b> xử lý danh sách rỗng, thử lại tối đa 2 lần và tiếp tục các SN còn lại khi lỗi như tiện ích web. Bỏ giới hạn 25 giây riêng cho tìm SKU; lỗi đăng nhập dừng ngay.</li>
<li><b>Vừa màn hình laptop:</b> cửa sổ mở gọn theo vùng màn hình làm việc, không che góc phải hoặc góc dưới. Có thể phóng to khi cần; màn hình nhỏ có thanh cuộn để tới đầy đủ các mục.</li>
<li><b>Tìm Task theo SKU:</b> nút ở góc phải thanh tab. Quét hoặc nhập SKU/UPC, bấm Enter để tìm đơn Picked và Picking Task trong 7 ngày gần nhất theo giờ Việt Nam.</li>
<li><b>Copy mã rổ:</b> xem Task ID, Order Structure, Device ID/BSK, SKU Qty, Item Qty và số SN khớp. Copy từng task hoặc toàn bộ BSK không trùng.</li>
<li><b>Giao diện đồng bộ:</b> công cụ mới theo chế độ sáng/tối. Chỉ gọi WMS khi tìm, chạy song song có giới hạn; có nút Dừng; thử lại có giới hạn như tiện ích web.</li>
</ul>
<p>Giữ nguyên mọi điều kiện hiện tại.</p>
<p>Thông báo hiện khi mở phiên bản mới lần đầu. Bấm Đã hiểu để không hiện lại; dùng Xem thay đổi để mở lại khi cần.</p><p>Đỗ Rê Mon♥</p>'''

def show_changes(window,save_config,automatic=False):
    if automatic and window.config.get('seen_release')==VERSION:return
    existing=getattr(window,'_whats_new_dialog',None)
    if existing is not None and existing.isVisible():existing.raise_();return
    dialog=QDialog(window);window._whats_new_dialog=dialog
    dialog.setWindowTitle('Có gì mới? — '+TITLE);dialog.resize(650,510)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    layout=QVBoxLayout(dialog);text=QTextBrowser();text.setHtml(NOTES);layout.addWidget(text)
    button=QPushButton('Đã hiểu');layout.addWidget(button);button.clicked.connect(dialog.accept)
    def acknowledge():
        previous=window.config.get('seen_release')
        window.config['seen_release']=VERSION
        if not save_config(window.config):
            if previous is None:window.config.pop('seen_release',None)
            else:window.config['seen_release']=previous
            QMessageBox.warning(window,'Chưa lưu được','Lần mở sau thông báo có thể xuất hiện lại vì chưa lưu được cấu hình.')
    dialog.accepted.connect(acknowledge)
    dialog.finished.connect(lambda _:dialog.deleteLater())
    dialog.finished.connect(lambda _:setattr(window,'_whats_new_dialog',None))
    if hasattr(window,'theme_controller'):window.theme_controller.apply()
    dialog.open()
