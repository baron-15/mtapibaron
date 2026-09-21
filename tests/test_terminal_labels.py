import datetime as dt
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch

from mtapi import mtapi as api_module
from mtapi.mtapi import Mtapi
from mtapi.terminal_labels import terminal_labels
from mtaproto import nyct_subway_pb2
from mtaproto.feedresponse import FeedResponse, TZ


ROOT = Path(__file__).resolve().parents[1]
STOPS = json.loads((ROOT / 'data/stationsv2.json').read_text())
STATIONS = json.loads((ROOT / 'data/stations.json').read_text())


class LabelTests(unittest.TestCase):
    def test_manhattan_uptown_and_downtown(self):
        for direction in ('Uptown', 'Downtown'):
            for terminal, suffix in (('R45', ' & Brooklyn'), ('G08', ' & Queens'),
                                     ('A02', ''), ('401', ' & The Bronx' if direction == 'Uptown' else '')):
                with self.subTest(direction=direction, terminal=terminal):
                    labels = terminal_labels(STOPS['127'], STOPS[terminal], 'Terminal', direction)
                    self.assertEqual(labels, {'terminalPrimary': direction + suffix,
                                              'terminalSecondary': 'Terminal'})

    def test_borough_headings_stay_singular(self):
        for direction in ('Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'The Bronx'):
            for terminal in ('R45', 'G08', '401', 'A02'):
                self.assertEqual(terminal_labels(STOPS['127'], STOPS[terminal], 'Terminal', direction),
                                 {'terminalPrimary': direction, 'terminalSecondary': 'Terminal'})

    def test_missing_metadata_and_non_manhattan_do_not_add_borough(self):
        for current in ({}, STOPS['R31'], STOPS['R01'], STOPS['414']):
            for terminal in (STOPS['G08'], STOPS['401'], {}):
                self.assertEqual(terminal_labels(current, terminal, 'Terminal', 'Uptown')['terminalPrimary'],
                                 'Uptown')

    def test_unrecognized_direction_uses_terminal_without_duplicate_subtitle(self):
        for direction in (None, '', 'Last Stop', 'Southbound', 'Flushing-Main St'):
            self.assertEqual(terminal_labels({}, {}, 'Terminal', direction),
                             {'terminalPrimary': 'Terminal', 'terminalSecondary': None})
        self.assertEqual(terminal_labels({}, {}, 'Terminal', None, True),
                         {'terminalPrimary': 'Terminal', 'terminalSecondary': 'via Roosevelt Island'})

    def test_existing_via_text_is_preserved(self):
        for name in ('Jamaica-179 St via Roosevelt Island', 'Jamaica-179 St VIA 53 St'):
            self.assertEqual(terminal_labels({}, {}, name, 'Uptown', True)['terminalSecondary'], name)


class TripLabelTests(unittest.TestCase):
    def process(self, trips, max_minutes=90, max_trains=10):
        """Run actual protobuf decoding and station processing without network or timers.

        Each stop is (parent ID, minutes ahead, schedule relationship).
        """
        now = dt.datetime.now(TZ)
        feed = nyct_subway_pb2.gtfs__realtime__pb2.FeedMessage()
        feed.header.gtfs_realtime_version = '2.0'
        feed.header.timestamp = int(now.timestamp())
        for number, (route, direction, stops) in enumerate(trips):
            entity = feed.entity.add()
            entity.id = str(number)
            trip = entity.trip_update.trip
            trip.trip_id = 'trip-' + str(number)
            trip.route_id = route
            trip.Extensions[nyct_subway_pb2.nyct_trip_descriptor].direction = (
                nyct_subway_pb2.NyctTripDescriptor.NORTH if direction == 'N'
                else nyct_subway_pb2.NyctTripDescriptor.SOUTH)
            for sequence, (stop_id, minutes, relationship) in enumerate(stops, 1):
                update = entity.trip_update.stop_time_update.add()
                update.stop_id = stop_id + direction
                update.stop_sequence = sequence
                update.schedule_relationship = relationship
                if minutes is not None:
                    update.arrival.time = int((now + dt.timedelta(minutes=minutes)).timestamp())

        api = Mtapi.__new__(Mtapi)
        api._stations = {key: Mtapi._Station(value) for key, value in STATIONS.items()}
        api._stops_to_stations = api._build_stops_index(api._stations)
        api._stop_id_to_name = {key: value['stop_name'] for key, value in STOPS.items()}
        api._FEED_URLS = ['test-feed']
        api._load_mta_feed = Mock(return_value=FeedResponse(feed.SerializeToString()))
        api._MAX_MINUTES = max_minutes
        api._MAX_TRAINS = max_trains
        api._THREADED = False
        api._EXPIRES_SECONDS = None
        api._read_lock = threading.RLock()
        with patch.object(api_module, 'stopJSON', STOPS, create=True):
            api._update()
        api._load_mta_feed.assert_called_once_with('test-feed')
        return api

    def train_at(self, api, stop_id, trip_index=0):
        trains = api.get_by_id([stop_id])[0]['alltrains']
        return next(train for train in trains if train['trip'] == 'trip-' + str(trip_index))

    def test_any_line_and_both_directions_use_the_actual_trip(self):
        for route, direction, origin, terminal in (
            ('F', 'N', 'D20', 'F01'), ('F', 'S', 'G08', 'D43'),
            ('M', 'N', 'D20', 'G08'), ('M', 'S', 'G08', 'M01'),
            ('R', 'S', 'G08', 'R45')
        ):
            with self.subTest(route=route, direction=direction):
                api = self.process([(route, direction, [(origin, 1, 0), ('B06', 8, 0), (terminal, 20, 0)])])
                train = self.train_at(api, origin)
                terminal_name = STOPS[terminal]['stop_name']
                self.assertEqual(train['terminalSecondary'], terminal_name + ' via Roosevelt Island')
                self.assertEqual(train['terminalName'], terminal_name)
                self.assertEqual(train['terminal'], terminal + direction)
                self.assertEqual(train['directionLabel'], STOPS[origin][
                    'north_direction_label' if direction == 'N' else 'south_direction_label'])

    def test_user_borough_examples(self):
        for route, direction, origin, terminal, primary in (
            ('F', 'S', 'F04', 'D43', 'Manhattan'),
            ('R', 'N', 'R28', 'G08', 'Manhattan'),
            ('4', 'S', '401', '250', 'Manhattan'),
            ('A', 'S', 'A38', 'H15', 'Brooklyn'),
            ('4', 'N', '626', '401', 'Uptown & The Bronx'),
            ('4', 'N', '621', '401', 'The Bronx')
        ):
            with self.subTest(route=route, origin=origin):
                api = self.process([(route, direction, [(origin, 1, 0), (terminal, 20, 0)])])
                train = self.train_at(api, origin)
                self.assertEqual(train['terminalPrimary'], primary)
                self.assertEqual(train['terminalSecondary'], STOPS[terminal]['stop_name'])

    def test_label_changes_at_and_after_roosevelt_island(self):
        for direction, stops in (
            ('N', ['D20', 'B06', 'G21', 'F01']),
            ('S', ['G08', 'B06', 'B08', 'D43'])
        ):
            api = self.process([('F', direction, [(stop, index + 1, 0) for index, stop in enumerate(stops)])])
            for index, stop in enumerate(stops):
                train = self.train_at(api, stop)
                self.assertEqual('via Roosevelt Island' in (train['terminalSecondary'] or ''), index == 0)

    def test_terminal_at_or_before_roosevelt_island_has_no_via(self):
        for stops in (['D20', 'B06'], ['D20', 'B08']):
            api = self.process([('F', 'N', [(stop, index + 1, 0) for index, stop in enumerate(stops)])])
            self.assertNotIn('via', self.train_at(api, 'D20')['terminalSecondary'])

    def test_skipped_roosevelt_island_has_no_via_or_arrival(self):
        api = self.process([('M', 'N', [('D20', 1, 0), ('B06', 8, 1), ('G08', 20, 0)])])
        self.assertNotIn('via', self.train_at(api, 'D20')['terminalSecondary'])
        self.assertEqual(api.get_by_id(['B06'])[0]['alltrains'], [])

    def test_explicit_stop_without_prediction_still_supplies_route(self):
        api = self.process([('F', 'N', [('D20', 1, 0), ('B06', None, 2), ('F01', 20, 0)])])
        self.assertIn('via Roosevelt Island', self.train_at(api, 'D20')['terminalSecondary'])

    def test_two_trips_on_same_line_can_have_different_subtitles(self):
        api = self.process([
            ('F', 'N', [('D20', 1, 0), ('B06', 8, 0), ('F01', 20, 0)]),
            ('F', 'N', [('D20', 2, 0), ('F12', 8, 0), ('F01', 21, 0)])
        ])
        self.assertIn('via Roosevelt Island', self.train_at(api, 'D20', 0)['terminalSecondary'])
        self.assertNotIn('via', self.train_at(api, 'D20', 1)['terminalSecondary'])

    def test_arrival_limits_do_not_hide_later_route_information(self):
        api = self.process([
            ('F', 'N', [('D20', 1, 0), ('B06', 40, 0), ('F01', 80, 0)]),
            ('M', 'S', [('B06', 1, 0), ('D43', 20, 0)])
        ], max_minutes=30, max_trains=1)
        self.assertIn('via Roosevelt Island', self.train_at(api, 'D20')['terminalSecondary'])
        island = api.get_by_id(['B06'])[0]
        self.assertEqual(island['N'], [])
        self.assertEqual(len(island['alltrains']), 1)

    def test_complex_aliases_and_all_station_queries_keep_labels(self):
        api = self.process([('M', 'N', [('D20', 1, 0), ('B06', 8, 0), ('G08', 20, 0)])])
        expected = self.train_at(api, 'D20')
        self.assertEqual(self.train_at(api, 'A32'), expected)
        for station in (api.get_by_id(['D20'])[0],
                        next(s for s in api.get_by_route('M') if 'D20' in s['stops']),
                        next(s for s in api.get_by_point([40.732338, -74.000495], 10) if 'D20' in s['stops'])):
            self.assertEqual(station['N'][0], expected)
            self.assertEqual(station['alltrains'][0], expected)


if __name__ == '__main__':
    unittest.main()
