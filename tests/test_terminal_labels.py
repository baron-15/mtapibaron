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
            for terminal, suffix in (('D42', ' & Brooklyn'), ('F01', ' & Queens'),
                                     ('A02', ''), ('401', ' & The Bronx' if direction == 'Uptown' else '')):
                with self.subTest(direction=direction, terminal=terminal):
                    labels = terminal_labels(STOPS['127'], STOPS[terminal], 'Terminal', direction)
                    self.assertEqual(labels, {'terminalPrimary': direction + suffix,
                                              'terminalSecondary': 'Terminal'})

    def test_borough_headings_stay_singular(self):
        for direction in ('Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'The Bronx'):
            for terminal in ('D42', 'F01', '401', 'A02'):
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
        name = 'Forest Hills-71 Av VIA 53 St'
        for direction, primary, secondary in (
            ('Queens', 'Queens', 'Forest Hills VIA 53 St'),
            ('Outbound', 'Forest Hills', '71 Av VIA 53 St'),
        ):
            self.assertEqual(terminal_labels({}, STOPS['G08'], name, direction, True),
                             {'terminalPrimary': primary, 'terminalSecondary': secondary})


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
        for route, direction, origin, terminal, display_name in (
            ('F', 'N', 'D20', 'F01', 'Jamaica-179 St'),
            ('F', 'S', 'G08', 'D43', 'Coney Island'),
            ('M', 'N', 'D20', 'G08', 'Forest Hills'),
            ('M', 'S', 'G08', 'M01', 'Middle Village-Metropolitan Av'),
            ('R', 'S', 'G08', 'R45', 'Bay Ridge'),
            ('E', 'N', 'D20', 'G05', 'Jamaica Center'),
        ):
            with self.subTest(route=route, direction=direction):
                api = self.process([(route, direction, [(origin, 1, 0), ('B06', 8, 0), (terminal, 20, 0)])])
                train = self.train_at(api, origin)
                terminal_name = STOPS[terminal]['stop_name']
                self.assertEqual(train['terminalSecondary'], display_name + ' via Roosevelt Island')
                self.assertEqual(train['terminalName'], terminal_name)
                self.assertEqual(train['terminal'], terminal + direction)
                self.assertEqual(train['directionLabel'], STOPS[origin][
                    'north_direction_label' if direction == 'N' else 'south_direction_label'])

    def test_user_borough_examples(self):
        for route, direction, origin, terminal, primary, secondary in (
            ('F', 'S', 'F04', 'D43', 'Manhattan', 'Coney Island'),
            ('R', 'N', 'R28', 'G08', 'Manhattan', 'Forest Hills'),
            ('R', 'S', 'G09', 'R45', 'Manhattan', 'Bay Ridge'),
            ('E', 'N', 'F12', 'G05', 'Queens', 'Jamaica Center'),
            ('7', 'S', '719', '726', 'Manhattan', '34 St'),
            ('7', 'S', '723', '726', '34 St', 'Hudson Yards'),
            ('7X', 'S', '725', '726', '34 St', 'Hudson Yards'),
            ('4', 'S', '401', '250', 'Manhattan', 'Crown Hts-Utica Av'),
            ('A', 'S', 'A38', 'H15', 'Brooklyn', 'Rockaway Park-Beach 116 St'),
            ('4', 'N', '626', '401', 'Uptown & The Bronx', 'Woodlawn'),
            ('4', 'N', '621', '401', 'The Bronx', 'Woodlawn')
        ):
            with self.subTest(route=route, origin=origin):
                api = self.process([(route, direction, [(origin, 1, 0), (terminal, 20, 0)])])
                train = self.train_at(api, origin)
                self.assertEqual(train['terminalPrimary'], primary)
                self.assertEqual(train['terminalSecondary'], secondary)
                self.assertEqual(train['terminalName'], STOPS[terminal]['stop_name'])
                self.assertEqual(train['terminal'], terminal + direction)

    def test_destination_labels_change_along_trip_without_changing_raw_fields(self):
        for route, direction, terminal, stops, expected in (
            ('R', 'N', 'G08', ['R28', 'R14', 'G09', 'G08'], [
                ('Manhattan', 'Forest Hills'), ('Uptown & Queens', 'Forest Hills'),
                ('Forest Hills', '71 Av'), ('Forest Hills', '71 Av')]),
            ('R', 'S', 'R45', ['G09', 'R14', 'R31', 'R45'], [
                ('Manhattan', 'Bay Ridge'), ('Downtown & Brooklyn', 'Bay Ridge'),
                ('Bay Ridge', '95 St'), ('Bay Ridge', '95 St')]),
            ('E', 'N', 'G05', ['D20', 'F12', 'G14', 'G05'], [
                ('Uptown & Queens', 'Jamaica Center'), ('Queens', 'Jamaica Center'),
                ('Jamaica Center', None), ('Jamaica Center', None)]),
            ('E', 'N', 'F01', ['G14', 'F01'], [
                ('Jamaica-179 St', None), ('Jamaica-179 St', None)]),
            ('F', 'N', 'G08', ['G14', 'G08'], [
                ('Forest Hills', '71 Av'), ('Forest Hills', '71 Av')]),
            ('F', 'S', 'D43', ['D20', 'F39', 'D43'], [
                ('Downtown & Brooklyn', 'Coney Island'),
                ('Coney Island', 'Stillwell Av'), ('Coney Island', 'Stillwell Av')]),
            ('Q', 'S', 'D43', ['R14', 'D42', 'D43'], [
                ('Downtown & Brooklyn', 'Coney Island'),
                ('Coney Island', 'Stillwell Av'), ('Coney Island', 'Stillwell Av')]),
            ('A', 'S', 'H11', ['A55', 'H04', 'H11'], [
                ('Queens', 'Far Rockaway'),
                ('Far Rockaway', 'Mott Av'), ('Far Rockaway', 'Mott Av')]),
        ):
            with self.subTest(route=route, terminal=terminal):
                api = self.process([(route, direction, [
                    (stop, index + 1, 0) for index, stop in enumerate(stops)])])
                for stop, (primary, secondary) in zip(stops, expected):
                    train = self.train_at(api, stop)
                    self.assertEqual(train['terminalPrimary'], primary)
                    self.assertEqual(train['terminalSecondary'], secondary)
                    self.assertEqual(train['terminal'], terminal + direction)
                    self.assertEqual(train['terminalName'], STOPS[terminal]['stop_name'])
                    self.assertEqual(train['directionLabel'], STOPS[stop][
                        'north_direction_label' if direction == 'N' else 'south_direction_label'])

    def test_via_qualifier_keeps_terminal_detail_and_disappears_after_island(self):
        for terminal, primary, detail in (
            ('G08', 'Forest Hills', '71 Av'),
            ('R45', 'Bay Ridge', '95 St'),
            ('G05', 'Jamaica Center', None),
            ('H11', 'Far Rockaway', 'Mott Av'),
            ('D43', 'Coney Island', 'Stillwell Av'),
        ):
            with self.subTest(terminal=terminal):
                api = self.process([('R', 'N', [
                    ('G09', 1, 0), ('B06', 8, 0), (terminal, 20, 0)])])
                before = self.train_at(api, 'G09')
                self.assertEqual(before['terminalPrimary'], primary)
                self.assertEqual(before['terminalSecondary'],
                                 (detail + ' ' if detail else '') + 'via Roosevelt Island')
                at_island = self.train_at(api, 'B06')
                self.assertEqual(at_island['terminalPrimary'], 'Queens')
                self.assertEqual(at_island['terminalSecondary'], primary)

    def test_e_jfk_labels_follow_upcoming_sutphin_stop(self):
        stops = ['A28', 'F12', 'G07', 'G06', 'G05']
        api = self.process([('E', 'N', [
            (stop, index + 1, 0) for index, stop in enumerate(stops)])])
        for stop, primary, secondary in (
            ('A28', 'Uptown & Queens', 'Jamaica Center/JFK'),
            ('F12', 'Queens', 'Jamaica Center/JFK'),
            ('G07', 'Jamaica Center', 'JFK'),
            ('G06', 'Jamaica Center', None),
            ('G05', 'Jamaica Center', None),
        ):
            with self.subTest(stop=stop):
                train = self.train_at(api, stop)
                self.assertEqual(train['terminalPrimary'], primary)
                self.assertEqual(train['terminalSecondary'], secondary)
                self.assertEqual(train['terminal'], 'G05N')
                self.assertEqual(train['terminalName'], 'Jamaica Center-Parsons/Archer')
                self.assertEqual(train['directionLabel'], STOPS[stop]['north_direction_label'])

    def test_jfk_requires_an_explicit_non_skipped_stop(self):
        for route, direction, stops in (
            ('E', 'N', [('A28', 1, 0), ('G05', 20, 0)]),
            ('E', 'N', [('A28', 1, 0), ('G06', 18, 1), ('G05', 20, 0)]),
            ('E', 'N', [('A28', 1, 0), ('F01', 20, 0)]),
            ('J', 'N', [('M23', 1, 0), ('G06', 18, 1), ('G05', 20, 0)]),
            ('Z', 'N', [('M23', 1, 0), ('G05', 20, 0)]),
            ('A', 'S', [('A28', 1, 0), ('H03', 18, 1), ('H11', 20, 0)]),
            ('A', 'S', [('A28', 1, 0), ('A65', 20, 0)]),
            ('A', 'S', [('A28', 1, 0), ('XXX', 18, 0), ('H11', 20, 0)]),
        ):
            with self.subTest(route=route, stops=stops):
                api = self.process([(route, direction, stops)])
                train = self.train_at(api, stops[0][0])
                self.assertNotIn('JFK', train['terminalPrimary'])
                self.assertNotIn('JFK', train['terminalSecondary'] or '')

    def test_jfk_follows_j_z_and_diverted_trains(self):
        for route, origin, next_stop, heading in (
            ('J', 'M23', 'J12', 'Brooklyn'),
            ('Z', 'M23', 'J12', 'Brooklyn'),
            ('F', 'A28', 'G07', 'Uptown & Queens'),
        ):
            with self.subTest(route=route):
                api = self.process([(route, 'N', [
                    (origin, 1, 0), (next_stop, 10, 0), ('G06', 18, 0), ('G05', 20, 0)])])
                train = self.train_at(api, origin)
                self.assertEqual(train['terminalPrimary'], heading)
                self.assertEqual(train['terminalSecondary'], 'Jamaica Center/JFK')
                self.assertEqual(train['terminalName'], 'Jamaica Center-Parsons/Archer')
                self.assertEqual(train['terminal'], 'G05N')
                self.assertEqual(self.train_at(api, next_stop)['terminalPrimary'], 'Jamaica Center')
                self.assertEqual(self.train_at(api, next_stop)['terminalSecondary'], 'JFK')
                self.assertIsNone(self.train_at(api, 'G06')['terminalSecondary'])

    def test_a_jfk_labels_follow_howard_beach_on_both_rockaway_branches(self):
        for terminal, destination, detail in (
            ('H11', 'Far Rockaway', 'Mott Av'),
            ('H15', 'Rockaway Park-Beach 116 St', None),
        ):
            with self.subTest(terminal=terminal):
                stops = ['A28', 'A55', 'H02', 'H03', 'H04', terminal]
                api = self.process([('A', 'S', [
                    (stop, index + 1, 0) for index, stop in enumerate(stops)])])
                for stop, primary, secondary in (
                    ('A28', 'Downtown & Queens', destination + '/JFK'),
                    ('A55', 'Queens', destination + '/JFK'),
                    ('H02', destination, (detail + '/' if detail else '') + 'JFK'),
                    ('H03', destination, detail),
                    ('H04', destination, detail),
                ):
                    train = self.train_at(api, stop)
                    self.assertEqual(train['terminalPrimary'], primary)
                    self.assertEqual(train['terminalSecondary'], secondary)
                    self.assertEqual(train['terminalName'], STOPS[terminal]['stop_name'])
                    self.assertEqual(train['terminal'], terminal + 'S')

    def test_jfk_handles_both_directions_and_airport_connection_terminals(self):
        api = self.process([('E', 'S', [
            ('G05', 1, 0), ('G06', 3, 0), ('G07', 5, 0), ('E01', 60, 0)])])
        self.assertEqual(self.train_at(api, 'G05')['terminalSecondary'], 'World Trade Center/JFK')
        for stop in ('G06', 'G07'):
            self.assertEqual(self.train_at(api, stop)['terminalSecondary'], 'World Trade Center')
        api = self.process([('E', 'N', [('A28', 1, 0), ('G06', 20, 0)])])
        self.assertEqual(self.train_at(api, 'A28')['terminalSecondary'],
                         'Sutphin Blvd-Archer Av-JFK Airport')
        api = self.process([('A', 'N', [
            ('H11', 1, 0), ('H03', 10, 0), ('H02', 12, 0), ('A02', 60, 0)])])
        self.assertEqual(self.train_at(api, 'H11')['terminalSecondary'], 'Inwood-207 St/JFK')
        for stop in ('H03', 'H02'):
            self.assertEqual(self.train_at(api, stop)['terminalSecondary'], 'Inwood-207 St')
        api = self.process([('A', 'S', [('A28', 1, 0), ('H03', 20, 0)])])
        self.assertEqual(self.train_at(api, 'A28')['terminalSecondary'], 'Howard Beach-JFK Airport')

    def test_jfk_is_per_trip_and_survives_prediction_and_arrival_limits(self):
        for sutphin_minutes in (None, 40):
            with self.subTest(sutphin_minutes=sutphin_minutes):
                api = self.process([
                    ('E', 'N', [('A28', 1, 0), ('G06', sutphin_minutes, 2), ('G05', 80, 0)]),
                    ('E', 'N', [('A28', 2, 0), ('F01', 81, 0)]),
                ], max_minutes=30)
                self.assertEqual(self.train_at(api, 'A28', 0)['terminalSecondary'], 'Jamaica Center/JFK')
                self.assertEqual(self.train_at(api, 'A28', 1)['terminalSecondary'], 'Jamaica-179 St')
        api = self.process([('E', 'N', [
            ('A28', 1, 0), ('G06', 40, 0), ('G05', 80, 0)])], max_minutes=30, max_trains=1)
        self.assertEqual(self.train_at(api, 'A28')['terminalSecondary'], 'Jamaica Center/JFK')

    def test_jfk_combines_with_roosevelt_island_and_keeps_query_aliases(self):
        api = self.process([('E', 'N', [
            ('D20', 1, 0), ('B06', 10, 0), ('G07', 20, 0), ('G06', 25, 0), ('G05', 30, 0)])])
        expected = self.train_at(api, 'D20')
        self.assertEqual(expected['terminalSecondary'], 'Jamaica Center/JFK via Roosevelt Island')
        self.assertEqual(self.train_at(api, 'B06')['terminalSecondary'], 'Jamaica Center/JFK')
        self.assertEqual(self.train_at(api, 'G07')['terminalSecondary'], 'JFK')
        self.assertEqual(self.train_at(api, 'A32'), expected)
        for station in (api.get_by_id(['D20'])[0],
                        next(s for s in api.get_by_route('E') if 'D20' in s['stops']),
                        next(s for s in api.get_by_point([40.732338, -74.000495], 10) if 'D20' in s['stops'])):
            self.assertEqual(station['N'][0], expected)
            self.assertEqual(station['alltrains'][0], expected)

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
