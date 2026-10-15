"""Window sizing uses the available desktop, excluding the Windows taskbar."""
from PySide6.QtWidgets import QVBoxLayout

class ViewportLayout(QVBoxLayout):
    # Hidden Excel charts otherwise inflate heightForWidth for the whole window.
    # Each local row still lays out and wraps its own labels normally.
    def hasHeightForWidth(self):return False
    def heightForWidth(self,width):return -1

def fit_window(window,width=1180,height=720,available=None):
    available=available or window.screen().availableGeometry()
    window.resize(min(width,max(240,available.width()-48)),min(height,max(200,available.height()-70)))
    # Include title bar and borders when centering a visible window.
    frame=window.frameGeometry();frame.moveCenter(available.center());window.move(frame.topLeft())
