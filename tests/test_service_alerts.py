import io
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from mtapi.service_alerts import ServiceAlerts, SUBWAY_ALERTS_URL, select_alerts

NOW = 10000

def translated(text):
    return {'translation': [{'language': 'en', 'text': text}, {'language': 'en-html', 'text': '<b>HTML</b>'}]}

def entity(identity, routes, **overrides):
    alert = {
        'active_period': [{'start': NOW - 60, 'end': NOW + 3600}],
        'informed_entity': [{'agency_id': 'MTASBWY', 'route_id': route} for route in routes],
        'header_text': translated('[A] trains are delayed.'),
        'transit_realtime.mercury_alert': {'alert_type': 'Delays', 'updated_at': NOW - 60}
    }
    alert.update(overrides)
    return {'id': identity, 'alert': alert}

def station(routes=('A', '6X'), **overrides):
    return {'alltrains': [{'route': route, 'terminal': 'A02N'} for route in routes],
            'stops': {'A27': {}, '127': {}}, 'last_update': None, **overrides}

class ImmediateThread:
    def __init__(self, target, **kwargs):
        self.target = target
    def start(self):
        self.target()

class SelectionTests(unittest.TestCase):
    def select(self, entities, target=None):
        return select_alerts({'entity': entities}, target or station(), NOW)

    def test_routes_express_variants_and_agency(self):
        items = [entity('a', ['A']), entity('6', ['6']), entity('6x', ['6X']), entity('b', ['B']),
                 entity('bus', ['A'], informed_entity=[{'agency_id': 'MTA NYCT', 'route_id': 'A'}])]
        self.assertEqual([a['id'] for a in self.select(items)], ['6', '6x', 'a'])
        self.assertEqual(self.select([entity('si', ['SIR'])], station(('SI',)))[0]['routes'], ['SI'])
        self.assertEqual(self.select([entity('shuttle', ['FS'])], station(('GS',))), [])

    def test_station_notices_and_line_notices_elsewhere(self):
        items = [entity('here', [], informed_entity=[{'stop_id': 'A27N'}]),
                 entity('away', [], informed_entity=[{'stop_id': 'A03'}]),
                 entity('line', [], informed_entity=[{'route_id': 'A', 'stop_id': 'A03'}])]
        result = self.select(items)
        self.assertEqual([a['id'] for a in result], ['here', 'line'])
        self.assertTrue(result[0]['stationWide'])
        self.assertEqual(result[1]['routes'], ['A'])

    def test_empty_arrivals_and_terminating_trains_are_excluded(self):
        items = [entity('a', ['A'])]
        self.assertEqual(self.select(items, station(())), [])
        self.assertEqual(self.select(items, station(alltrains=[{'route': 'A', 'terminal': 'A27N'}])), [])

    def test_active_windows_and_advance_notices(self):
        items = [entity('current', ['A']),
                 entity('future', ['A'], active_period=[{'start': NOW + 1}]),
                 entity('ended', ['A'], active_period=[{'end': NOW}]),
                 entity('gap', ['A'], active_period=[{'end': NOW - 1}, {'start': NOW + 1}])]
        result = self.select(items)
        self.assertEqual([a['id'] for a in result], ['current'])
        self.assertEqual(result[0]['activeUntil'], NOW + 3600)

    def test_plain_text_metadata_priority_and_deduplication(self):
        planned = entity('lmm:planned_work:1', ['A'], **{'transit_realtime.mercury_alert': {
            'alert_type': 'Planned - Stops Skipped', 'updated_at': NOW,
            'human_readable_active_period': translated('This weekend')}})
        delay = entity('delay', ['A'])
        result = self.select([planned, delay, delay, {**entity('deleted', ['A']), 'is_deleted': True}])
        self.assertEqual([a['id'] for a in result], ['delay', 'lmm:planned_work:1'])
        self.assertEqual(result[0]['text'], '[A] trains are delayed.')
        self.assertEqual(result[1]['schedule'], 'This weekend')
        self.assertTrue(result[1]['planned'])

    def test_camel_case_and_malformed_entries(self):
        camel = {'id': 'camel', 'alert': {'activePeriod': [{'start': NOW}],
                 'informedEntity': [{'agencyId': 'MTASBWY', 'routeId': 'A'}],
                 'descriptionText': translated('Details'), '.mercuryAlert': {'alertType': 'Boarding Change'}}}
        malformed = [None, {}, {'alert': []}, entity('period', ['A'], active_period=[{'start': 'bad'}]),
                     entity('translation', ['A'], header_text={'translation': [None]}),
                     entity('selector', ['A'], informed_entity=[None])]
        result = self.select(malformed + [camel])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'Boarding Change')
        self.assertEqual(result[0]['text'], 'Details')

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.feed = {'header': {'timestamp': NOW - 1800}, 'entity': [entity('a', ['A'])]}
        self.opener = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(json.dumps(self.feed).encode()))
        self.cache = ServiceAlerts(opener=self.opener, clock=lambda: self.now, thread_factory=ImmediateThread)

    def test_successful_old_publication_timestamp_is_not_rejected(self):
        result = self.cache.attach([station()])[0]['serviceAlerts']
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['updatedAt'], NOW - 1800)
        self.assertEqual(len(result['alerts']), 1)
        self.assertEqual(result['expiresAt'], NOW + 300)

    def test_one_refresh_serves_multiple_stations_and_requests(self):
        original = station()
        result = self.cache.attach([original, station(('B',))])
        self.assertEqual(len(result[0]['serviceAlerts']['alerts']), 1)
        self.assertEqual(result[1]['serviceAlerts']['alerts'], [])
        self.assertNotIn('serviceAlerts', original, 'Never mutate the arrivals cache')
        self.now += 59
        self.cache.attach([station()])
        self.opener.assert_called_once_with(SUBWAY_ALERTS_URL, timeout=5)
        self.now += 1
        self.cache.attach([station()])
        self.assertEqual(self.opener.call_count, 2)

    def test_failure_uses_bounded_cache_and_retries_without_request_storm(self):
        self.cache.attach([station()])
        self.now += 60
        self.opener.side_effect = OSError('offline')
        self.assertEqual(self.cache.attach([station()])[0]['serviceAlerts']['status'], 'stale')
        self.now += 1
        self.cache.attach([station()])
        self.assertEqual(self.opener.call_count, 2)
        self.now = NOW + 301
        result = self.cache.attach([station()])[0]['serviceAlerts']
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['alerts'], [])

    def test_invalid_feed_never_becomes_an_empty_success(self):
        for feed in [[], {}, {'entity': None}, {'header': {'timestamp': -1}, 'entity': []},
                     {'header': {'timestamp': NOW + 120}, 'entity': []}]:
            self.feed = feed
            cache = ServiceAlerts(opener=self.opener, clock=lambda: self.now, thread_factory=ImmediateThread)
            self.assertEqual(cache.snapshot()['status'], 'unavailable')

    def test_empty_valid_feed_is_success_and_no_stations_do_not_fetch(self):
        self.assertEqual(self.cache.attach([]), [])
        self.opener.assert_not_called()
        self.feed['entity'] = []
        result = self.cache.attach([station()])[0]['serviceAlerts']
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['alerts'], [])

    def test_pending_refresh_does_not_block_station_requests_or_start_duplicate_threads(self):
        started, release, completed = threading.Event(), threading.Event(), threading.Event()
        def opener(*args, **kwargs):
            started.set()
            release.wait(2)
            return io.BytesIO(json.dumps(self.feed).encode())
        def thread_factory(target, **kwargs):
            def run():
                try:
                    target()
                finally:
                    completed.set()
            return threading.Thread(target=run, **kwargs)
        cache = ServiceAlerts(opener=opener, clock=lambda: self.now, thread_factory=thread_factory)
        try:
            result = cache.attach([station()])[0]
            self.assertTrue(started.wait(1))
            self.assertEqual(result['serviceAlerts']['status'], 'loading')
            self.assertTrue(result['alltrains'])
            with patch.object(cache, '_thread_factory') as factory:
                cache.attach([station()])
                factory.assert_not_called()
        finally:
            release.set()
            self.assertTrue(completed.wait(2))
        self.assertEqual(cache.snapshot()['status'], 'ok')

class EndpointTests(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg') as config:
            config.write("MTA_KEY = ''\nSTATIONS_FILE = ''\nSTOPS_FILE = ''\nCROSS_ORIGIN = '*'\nTHREADED = False\n")
            config.flush()
            with patch.dict(os.environ, {'MTAPI_SETTINGS': config.name}), patch('mtapi.mtapi.Mtapi'):
                sys.modules.pop('main', None)
                import main
        self.main = main
        self.client = main.app.test_client()
        self.feed = {'header': {'timestamp': NOW - 1800}, 'entity': [entity('a', ['A'])]}
        self.opener = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(json.dumps(self.feed).encode()))
        main.service_alerts = ServiceAlerts(opener=self.opener, clock=lambda: NOW, thread_factory=ImmediateThread)
        for method in ('get_by_id', 'get_by_route', 'get_by_point'):
            getattr(main.mta, method).return_value = [station()]

    def test_all_station_endpoints_embed_processed_alerts(self):
        for url in ('/by-id/A27', '/by-route/A', '/by-location?lat=40&lon=-73'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
            self.assertEqual(response.json['data'][0]['serviceAlerts']['alerts'][0]['id'], 'a')
            self.assertNotIn('feed', response.json['data'][0]['serviceAlerts'])
        self.assertEqual(self.opener.call_count, 1)
        self.assertEqual(self.client.get('/service-alerts').status_code, 404)

    def test_alert_outage_preserves_successful_arrivals(self):
        self.opener.side_effect = OSError('offline')
        response = self.client.get('/by-id/A27')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['data'][0]['alltrains'])
        self.assertEqual(response.json['data'][0]['serviceAlerts']['status'], 'unavailable')

if __name__ == '__main__':
    unittest.main()
