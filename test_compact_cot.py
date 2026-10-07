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
            batch = rows[:2] if payload['beg_cut_off_time'] == self.stamp(5, 59) else rows[2:]
            start = (payload['pageno'] - 1) * payload['count']
            return dict(total=len(batch), list=batch[start:start + payload['count']])
        self.api.side_effect = response
        # Run the real worker synchronously to make API scope assertions deterministic.
        with patch.object(m.COTOrderListThread, 'start', lambda thread: thread.run()):
            original = m.COTOrderListThread.__init__
            def small_pages(thread, *args, **kwargs):
                kwargs['page_size'] = 2
                original(thread, *args, **kwargs)
            with patch.object(m.COTOrderListThread, '__init__', small_pages):
                w.cot_buttons['intra20'].click()
        self.assertEqual([p['pageno'] for p in payloads], [1, 1, 2])
        self.assertTrue(all(p['order_status_list'] == '' for p in payloads))
        self.assertEqual([p['beg_cut_off_time'] for p in payloads], [self.stamp(5, 59), self.stamp(19, 59), self.stamp(19, 59)])
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

    def test_http_429_stops_without_retry_or_next_page(self):
        cot = self.window.cot_definition_map['intra_end']
        self.assertEqual([int(b.timestamp()) for b, e in cot['cutoff_ranges']],
                         [self.stamp(19, 59), self.stamp(23, 49)])
        worker = m.COTOrderListThread('test', 'offline', cot, 'total')
        errors = []
        worker.error.connect(lambda rid, message: errors.append(message))
        self.api_patch.stop()
        with patch.object(m, '_wms_post', side_effect=RuntimeError('HTTP 429: overloaded')) as api:
            worker.run()
            self.assertEqual(api.call_count, 1)
        self.api_patch.start()
        self.assertEqual(errors, ['HTTP 429: overloaded (trang 1, yêu cầu 200 đơn/trang)'])

    def test_450_orders_use_three_200_order_requests(self):
        w = self.window
        w.cotService.setCurrentText('SDD')
        rows = [dict(order_number=f'ORDER-{i}', order_status=0, ctime=self.stamp(6)) for i in range(450)]
        payloads = []
        request_times = []
        def response(cookie, payload):
            payloads.append(payload.copy())
            request_times.append(m.time.monotonic())
            start = (payload['pageno'] - 1) * payload['count']
            return dict(total=len(rows), list=rows[start:start + payload['count']])
        self.api.side_effect = response
        with patch.object(m.COTOrderListThread, 'start', lambda thread: thread.run()):
            w.cot_buttons['sdd04_09'].click()
        self.assertEqual([(p['pageno'], p['count'], p['is_get_total']) for p in payloads],
                         [(1, 200, 1), (2, 200, 0), (3, 200, 0)])
        self.assertTrue(all(b-a >= m.WMS_PAGE_INTERVAL_SECONDS for a,b in zip(request_times, request_times[1:])))
        self.assertEqual([r['order_number'] for r in w.cot_current_rows], [r['order_number'] for r in rows])
        w.cot_buttons['sdd04_09'].click()
        self.assertEqual(len(payloads), 3)

    def test_server_clamped_page_is_not_shown_as_complete(self):
        w = self.window
        w.cotService.setCurrentText('SDD')
        self.api.side_effect = lambda cookie, payload: dict(total=450, list=[dict(ctime=self.stamp(6))]*20)
        with patch.object(m.COTOrderListThread, 'start', lambda thread: thread.run()):
            w.cot_buttons['sdd04_09'].click()
        self.assertEqual(self.api.call_count, 1)
        self.assertIn('20/200', w.lblCotOrderCount.text())
        self.assertFalse(w._cot_data_ready)
        self.assertEqual(w.cot_cache, {})

    def test_picked_seven_and_intra_percent_exclude_cancel_and_duplicates(self):
        w = self.window
        cot = w.cot_definition_map['intra03']
        rows = [dict(order_number=f'P-{i}', order_status=3, purchase_time=self.stamp(21, day=3)) for i in range(7)]
        rows += [dict(order_number=f'O-{i}', order_status=8, purchase_time=self.stamp(21, day=3)) for i in range(3)]
        rows += [dict(order_number='C-1', status_name='Cancelled', purchase_time=self.stamp(21, day=3)), rows[0].copy()]
        w.cot_cache[w._cot_cache_key(cot, 'total')] = (rows, len(rows))
        w.cot_buttons['intra03'].click()
        self.assertIn('Tổng hợp lệ: 10', w.lblCotPercent.text())
        self.assertIn('Tỷ lệ: 30.00%', w.lblCotPercent.text())
        i = w.cotStatusFilter.findData('Picked')
        self.assertEqual(w.cotStatusFilter.itemText(i), 'Picked: 7 đơn (70.00%)')
        w.cotStatusFilter.setCurrentIndex(i)
        self.assertEqual(w.cot_order_model._data['WMS Order No'].tolist(), [f'P-{i}' for i in range(7)])
        self.assertEqual(set(w.cot_order_model._data['Status']), {'Picked'})
        self.assertIn('Tỷ lệ: 30.00%', w.lblCotPercent.text())
        w.cotStatusFilter.setCurrentIndex(w.cotStatusFilter.findData('Cancel'))
        self.assertEqual(w.cot_order_model._data['WMS Order No'].tolist(), ['C-1'])
        self.assertFalse(self.api.called)
        w.cotService.setCurrentText('SDD')
        self.assertTrue(w.lblCotPercent.isHidden())

    def test_exact_two_am_boundary_and_subslot_statistics(self):
        w = self.window
        before, after = w.cot_definition_map['intra06'], w.cot_definition_map['intra20']
        rows = [dict(order_number=str(i), order_status=3, purchase_time=t)
                for i,t in enumerate([self.stamp(2)-1, self.stamp(2), self.stamp(2,59), self.stamp(5)])]
        self.assertEqual([r['order_number'] for r in m._filter_purchase_window(rows, before['purchase_beg'], before['purchase_end'])], ['0'])
        selected = m._filter_purchase_window(rows, after['purchase_beg'], after['purchase_end'])
        self.assertEqual([r['order_number'] for r in selected], ['1','2','3'])
        w.cot_cache[w._cot_cache_key(after, 'total')] = (selected, 3)
        w.cot_buttons['intra20'].click()
        w._select_cot_slot(0)
        self.assertIn('Tổng hợp lệ: 2', w.lblCotPercent.text())
        w.cotStatusFilter.setCurrentIndex(w.cotStatusFilter.findData('Picked'))
        self.assertEqual(w.cot_order_model._data['WMS Order No'].tolist(), ['1','2'])
        self.assertFalse(self.api.called)

    def test_unknown_numeric_status_does_not_guess_cancel_or_percentage(self):
        w = self.window
        cot = w.cot_definition_map['intra03']
        rows = [dict(order_number='UNKNOWN', order_status=999, purchase_time=self.stamp(21, day=3))]
        w.cot_cache[w._cot_cache_key(cot, 'total')] = (rows, 1)
        w.cot_buttons['intra03'].click()
        self.assertIn('Chưa tính %', w.lblCotPercent.text())
        w.cotStatusFilter.setCurrentIndex(w.cotStatusFilter.findData('Mã trạng thái 999'))
        self.assertEqual(w.cot_order_model._data['WMS Order No'].tolist(), ['UNKNOWN'])
        self.assertEqual(m._order_status_name(dict(order_status=999, status_name='Cancel')), 'Cancel')

    def test_repeat_click_does_not_restart_active_request(self):
        w = self.window
        class Worker:
            def isRunning(self): return True
            def requestInterruption(self): raise AssertionError('Repeated click canceled active load')
        w.cot_list_thread = Worker()
        w.cot_current_selection = ('intra03', 'total')
        w._active_cot_request_id = 'intra03|1'
        with patch.object(w, '_start_cot_order_thread') as start:
            w.cot_buttons['intra03'].click()
            w.reload_cot_order_list()
            start.assert_not_called()
        self.assertIsNone(w._pending_cot_list_request)
        self.assertFalse(self.api.called)

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
