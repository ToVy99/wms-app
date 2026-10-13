"""Bundled release notes. Opening this dialog never makes a network request."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QMessageBox

VERSION='3.3'
TITLE='IntraCity 3.3'
NOTES='''<h2>Có gì mới trong IntraCity 3.3?</h2>
<ul>
<li><b>Bảng đơn rộng hơn:</b> phần thống kê, COT và trạng thái được thu gọn. Kéo thanh phía trên bảng đơn lên để che dần phần thống kê, kéo xuống để hiện lại. Phần trên không co giãn khi kéo.</li>
<li><b>Thu gọn nhanh:</b> nút Thu gọn / Mở thống kê và ghi nhớ vị trí kéo cho lần mở sau.</li>
<li><b>Chọn và copy dễ hơn:</b> chọn ô hoặc bấm tiêu đề để chọn cả cột, kể cả Picking ID. Vùng chọn sáng vàng; nhấn Ctrl+C để sao chép. Hỗ trợ cả sáng và tối.</li>
<li><b>Picked có mã rổ:</b> mã rổ chỉ hiển thị cho đơn đang Picked; bỏ số tổng trên nút này. Các ô tổng đơn và tỷ lệ phía trên vẫn giữ.</li>
<li><b>Lưu report gốc:</b> lưu Excel/ZIP vừa tải mà không gọi lại API hay tạo Export mới. File gốc có thể chứa những đơn đã bị app lọc bỏ.</li>
<li><b>Đọc đủ report chia nhỏ:</b> đọc các file Excel trong ZIP và các sheet dữ liệu đơn, gộp trùng OBVN và gom SKU/Picking ID/mã rổ. Nếu có phần report lỗi, thông báo rõ thay vì trả kết quả thiếu.</li>
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
