import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from mtapi.service_alerts import ServiceAlerts, AlertsUnavailable, SUBWAY_ALERTS_URL


class ServiceAlertsTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.feed = {'header': {'timestamp': 1000}, 'entity': [{'id': 'test', 'alert': {}}]}
        self.opener = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(json.dumps(self.feed).encode()))
        self.cache = ServiceAlerts(opener=self.opener, clock=lambda: self.now)

    def test_fetches_once_per_cache_period_and_preserves_gtfs_fields(self):
        self.assertEqual(self.cache.get()['feed'], self.feed)
        self.now += 59
        self.assertFalse(self.cache.get()['stale'])
        self.opener.assert_called_once_with(SUBWAY_ALERTS_URL, timeout=5)
        self.now += 1
        self.cache.get()
        self.assertEqual(self.opener.call_count, 2)

    def test_failure_uses_bounded_stale_cache_and_retries_without_a_request_storm(self):
        self.cache.get()
        self.now += 60
        self.opener.side_effect = OSError('offline')
        result = self.cache.get()
        self.assertTrue(result['stale'])
        self.assertEqual(result['fetchedAt'], 1000)
        self.now += 1
        self.cache.get()
        self.assertEqual(self.opener.call_count, 2)
        self.now = 1301
        with self.assertRaises(AlertsUnavailable):
            self.cache.get()

    def test_first_failure_does_not_pretend_there_are_no_alerts(self):
        self.opener.side_effect = OSError('offline')
        with self.assertRaises(AlertsUnavailable):
            self.cache.get()

    def test_invalid_and_expired_upstream_responses_are_rejected(self):
        for feed in [[], {}, {'entity': None}, {'header': {'timestamp': 1}, 'entity': []}]:
            cache = ServiceAlerts(opener=lambda *args, **kwargs: io.BytesIO(json.dumps(feed).encode()), clock=lambda: 1000)
            with self.assertRaises(AlertsUnavailable):
                cache.get()

    def test_current_empty_feed_is_a_success(self):
        self.feed['entity'] = []
        self.assertEqual(self.cache.get()['feed']['entity'], [])

    def test_endpoint_returns_cors_for_success_and_failure_without_loading_arrivals(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg') as config:
            config.write("MTA_KEY = ''\nSTATIONS_FILE = ''\nSTOPS_FILE = ''\nCROSS_ORIGIN = '*'\nTHREADED = False\n")
            config.flush()
            with patch.dict(os.environ, {'MTAPI_SETTINGS': config.name}), patch('mtapi.mtapi.Mtapi'):
                sys.modules.pop('main', None)
                import main
            client = main.app.test_client()
            with patch.object(main.service_alerts, 'get', return_value=self.cache.get()):
                response = client.get('/service-alerts')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
                self.assertEqual(response.json['feed'], self.feed)
            with patch.object(main.service_alerts, 'get', side_effect=AlertsUnavailable):
                response = client.get('/service-alerts')
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
            main.mta.get_by_id.assert_not_called()


if __name__ == '__main__':
    unittest.main()
