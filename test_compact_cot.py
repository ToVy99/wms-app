"""Offline checks for COT boundaries, pagination, caching, and rapid switching."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
import intra_2_3_COT_Dashboard_loginfix as m


class CompactCOTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = m.QApplication.instance() or m.QApplication([])

    def setUp(self):
        self.patches = [patch.object(m.AutoUpdaterThread, 'run', lambda self: None),
                        patch.object(m.WMSDashboard, 'start_folder_watcher', lambda self, path=None: None),
                        patch.object(m, 'load_config', return_value={})]
        for p in self.patches:
            p.start()
        self.api_patch = patch.object(m, '_wms_post_retry', side_effect=AssertionError('Unexpected WMS request'))
        self.api = self.api_patch.start()
        self.window = m.WMSDashboard()
        self.window.cotDate.setDate(m.QDate(2026, 10, 4))
        self.window.config['wms_cookie'] = 'offline-test'
        self.assertFalse(self.api.called)

    def tearDown(self):
        self.window.updater_thread.wait(1000)
        self.window.cot_list_thread = None
        self.window.close()
        self.app.processEvents()
        self.api_patch.stop()
        for p in reversed(self.patches):
            p.stop()

    def stamp(self, hour, minute=0, day=4):
        return int(datetime(2026, 10, day, hour, minute, tzinfo=m.VN_TZ).timestamp())

    def test_pick_windows_and_calendar_rollover(self):
        w = self.window
        w.cotService.setCurrentText('SDD')
        d = [w.cot_definition_map[k] for k in w.cot_buttons]
        self.assertEqual([(x['beg'].hour, x['beg'].minute, x['end'].hour, x['end'].minute) for x in d],
                         [(18, 0, 4, 0), (4, 0, 9, 0), (9, 0, 13, 30), (13, 30, 18, 0)])
        self.assertEqual(d[0]['beg'].day, 3)
        self.assertEqual(d[0]['channels'], ['50051'])
        for first, second in zip(d, d[1:]):
            self.assertEqual(first['end'], second['beg'])
        w.cotDate.setDate(m.QDate(2027, 1, 1))
        w.cotService.setCurrentText('Intra City')
        d = [w.cot_definition_map[k] for k in w.cot_buttons]
        self.assertEqual(d[0]['purchase_beg'].date().isoformat(), '2026-12-31')
        self.assertEqual(d[1]['purchase_end'].date().isoformat(), '2027-01-01')
        for first, second in zip(d, d[1:]):
            self.assertEqual(first['purchase_end'], second['purchase_beg'])
        self.assertEqual(d[-1]['purchase_end'] - d[0]['purchase_beg'], timedelta(days=1))
        self.assertFalse(self.api.called)

    def test_only_selected_cot_pages_and_local_filters(self):
        w = self.window
        rows = [dict(order_number=f'TEST-{i}', order_status=st, purchase_time=self.stamp(h, minute), ctime=self.stamp(h, minute))
                for i, (h, minute, st) in enumerate([(1, 59, 0), (2, 0, 0), (5, 0, 3), (15, 59, 8), (16, 0, 6)])]
        payloads = []
        def response(cookie, payload):
            payloads.append(payload.copy())
            start = (payload['pageno'] - 1) * payload['count']
            return dict(total=len(rows), list=rows[start:start + payload['count']])
        self.api.side_effect = response
        # Run the real worker synchronously to make API scope assertions deterministic.
        with patch.object(m.COTOrderListThread, 'start', lambda thread: thread.run()):
            original = m.COTOrderListThread.__init__
            def small_pages(thread, *args, **kwargs):
                kwargs['page_size'] = 2
                original(thread, *args, **kwargs)
            with patch.object(m.COTOrderListThread, '__init__', small_pages):
                w.cot_buttons['intra20'].click()
        self.assertEqual([p['pageno'] for p in payloads], [1, 2, 3])
        self.assertTrue(all(p['order_status_list'] == m.COT_STATUS_GROUPS['total'] for p in payloads))
        self.assertTrue(all(p['beg_cut_off_time'] == self.stamp(19, 59) for p in payloads))
        self.assertEqual(len(w.cot_current_rows), 3)
        self.assertEqual(w.cot_metric_buttons['pending'].text(), 'Chưa Outbound: 2')
        self.assertEqual(w.cot_metric_buttons['total'].text(), 'Tổng đơn: 3')
        w._select_cot_metric('pick')
        self.assertEqual(len(w.cot_order_model._data), 1)
        w._select_cot_slot(1)
        self.assertEqual(len(w.cot_order_model._data), 0)
        w._select_cot_metric('total')
        self.assertEqual(len(w.cot_order_model._data), 2)
        self.assertEqual(w.cot_order_model._data['WMS Order No'].tolist(), ['TEST-2', 'TEST-3'])
        w.searchCotBox.setText('TEST-3')
        self.assertEqual(len(w.cot_order_model._data), 1)
        w.request_cot_order_list('intra20', 'total')
        self.assertEqual(len(payloads), 3)  # cache, slot, status, and search make no API requests

    def test_half_open_boundaries_and_missing_purchase_time(self):
        w = self.window
        d = [w.cot_definition_map[k] for k in w.cot_buttons]
        for first, second in zip(d, d[1:]):
            boundary = first['purchase_end'].timestamp()
            row = {'purchase_time': boundary}
            self.assertEqual(m._filter_purchase_window([row], first['purchase_beg'], first['purchase_end']), [])
            self.assertEqual(m._filter_purchase_window([row], second['purchase_beg'], second['purchase_end']), [row])
            row_ms = {'purchase_time': boundary * 1000}
            self.assertEqual(m._filter_purchase_window([row_ms], second['purchase_beg'], second['purchase_end']), [row_ms])
        with self.assertRaisesRegex(RuntimeError, 'Purchase Time'):
            m._filter_purchase_window([{'ctime': self.stamp(3)}], d[2]['purchase_beg'], d[2]['purchase_end'])
        self.assertEqual(m._filter_created_window([{'ctime': self.stamp(9)}],
                        datetime(2026, 10, 4, 4, tzinfo=m.VN_TZ), datetime(2026, 10, 4, 9, tzinfo=m.VN_TZ)), [])

    def test_stale_response_cannot_replace_cached_selection(self):
        w = self.window
        class OldWorker:
            stopped = False
            def isRunning(self): return True
            def requestInterruption(self): self.stopped = True
        old = OldWorker()
        w.cot_list_thread = old
        w._active_cot_request_id = 'old'
        cot = w.cot_definition_map['intra03']
        row = dict(order_number='CURRENT', order_status=0, purchase_time=self.stamp(21, day=3))
        w.cot_cache[w._cot_cache_key(cot, 'total')] = ([row], 1)
        w.request_cot_order_list('intra03', 'total')
        self.assertTrue(old.stopped)
        with patch.object(w, '_invalidate_wms_cookie') as invalidate:
            w._on_cot_list_ready('old', [dict(order_number='STALE')], 1)
            w._on_cot_list_error('old', 'stale error')
            w._on_cot_list_auth_error('old', 'stale expired session')
            invalidate.assert_not_called()
        self.assertEqual(w.cot_order_model._data['WMS Order No'].tolist(), ['CURRENT'])
        self.assertIsNone(w._pending_cot_list_request)
        self.assertFalse(self.api.called)

    def test_rapid_switch_only_starts_latest_selection(self):
        w = self.window
        class OldWorker:
            running = True
            def isRunning(self): return self.running
            def requestInterruption(self): pass
        old = OldWorker()
        w.cot_list_thread = old
        w.request_cot_order_list('intra03', 'total')
        w.request_cot_order_list('intra06', 'total')
        self.assertEqual(w._pending_cot_list_request[0], 'intra06')
        old.running = False
        with patch.object(w, '_start_cot_order_thread') as start:
            w._on_cot_list_thread_finished()
            self.app.processEvents()
            self.assertEqual(start.call_count, 1)
            self.assertEqual(start.call_args.args[0]['key'], 'intra06')
        self.assertFalse(self.api.called)


if __name__ == '__main__':
    unittest.main(verbosity=2)
