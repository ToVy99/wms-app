"""Bundled release notes. Opening this dialog never makes a network request."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QMessageBox

VERSION='3.3.1'
TITLE='IntraCity 3.3.1'
NOTES='''<h2>Có gì mới trong IntraCity 3.3.1?</h2>
<ul>
<li><b>Giữ dữ liệu cũ khi tải:</b> bảng đơn, tổng đơn, trạng thái và tỷ lệ vẫn giữ cho đến khi tải và đọc dữ liệu mới thành công. Nếu lỗi, dữ liệu cũ vẫn còn. Có ghi rõ khung giờ của dữ liệu đang hiển thị.</li>
<li><b>Biết app đang làm gì:</b> vòng xoay xanh nhỏ cạnh nút tải, kèm bước đang yêu cầu báo cáo, chờ WMS, tải file hoặc đọc dữ liệu. Hình động chạy tại máy, không gọi thêm API.</li>
<li><b>Nút tải nổi bật:</b> nền cam vàng, chữ đậm, sáng khi rê chuột. Khi đang tải, nút đổi thành “Đang tải…” và khóa bấm để tránh gọi trùng.</li>
</ul>
<p>Giữ nguyên khung giờ COT, điều kiện lọc đơn, loại Cancel và cách tính tổng/tỷ lệ Outbound.</p>
<p>Thông báo hiện khi mở phiên bản mới lần đầu. Bấm Đã hiểu để không hiện lại; dùng Xem thay đổi để mở lại khi cần.</p>'''

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
