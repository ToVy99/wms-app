"""Desktop entry point; --smoke-test verifies the actual packaged executable."""
import json
import os
import sys
import intra_2_3_COT_Dashboard_loginfix as intra


def main():
    smoke = '--smoke-test' in sys.argv
    if smoke:
        # Startup verification is local only; it does not use WMS or user files.
        intra.AutoUpdaterThread.run = lambda self: None
        intra.WMSDashboard.start_folder_watcher = lambda self, path=None: None
    app = intra.QApplication(sys.argv)
    window = intra.WMSDashboard()
    window.show()

    if smoke:
        def verify():
            result = {'passed': False}
            try:
                assert window.mainTabs.count() == 2
                assert len(window.cot_definitions) == 13
                assert window.cotDashboardModel.rowCount() == 13
                with intra.sync_playwright() as playwright:
                    assert playwright.chromium.executable_path
                for _ in range(3):
                    window.set_banner_status(True, custom_msg='Startup verification')
                window.set_banner_status(False, custom_msg='Startup verified')
                assert intra.QApplication.overrideCursor() is None
                assert not window.anim_timer.isActive()
                window.grab().save('smoke-gui.png')
                result = {'passed': True, 'tabs': 2, 'cot_rows': 13,
                          'playwright_driver': 'started', 'spinner': 'stopped'}
            except Exception as exc:
                result['error'] = str(exc)
            finally:
                with open('smoke-test-result.json', 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                window.updater_thread.wait(2000)
                window.close()
                app.exit(0 if result['passed'] else 1)
        intra.QTimer.singleShot(800, verify)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
