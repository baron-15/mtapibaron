#How to deploy updated API: use 'gcloud app deploy'... that's it.

import urllib, contextlib, copy, datetime as dt
from datetime import time
from collections import defaultdict
from itertools import islice
from operator import itemgetter
import csv, math, json
import threading
import logging
import google.protobuf.message
from mtaproto.feedresponse import FeedResponse, Trip, TripStop, TZ
from mtapi._mtapithreader import _MtapiThreader
from mtapi.terminal_labels import terminal_labels

logger = logging.getLogger(__name__)

def distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def timeDifference(time_str1, time_str2, format='%Y-%m-%d %H:%M:%S%z'):
    time1 = dt.datetime.strptime(str(time_str1), format)
    time2 = dt.datetime.strptime(str(time_str2), format)
    time_difference = time2 - time1
    seconds_difference = time_difference.total_seconds()
    minutes_difference = int(seconds_difference // 60)
    if minutes_difference > 99:
        return "99+"
    elif minutes_difference == -1:
        return "0"
    elif minutes_difference <= -2:
        return "ERR"
    else:
        return minutes_difference
    
def isLateNight(time_str1, begin_time = time(0,0), end_time = time(6,0),format='%Y-%m-%d %H:%M:%S%z'):
    time = dt.datetime.strptime(str(time_str1), format)
    if begin_time < end_time:
        return time_str1 >= begin_time and time_str1 <= end_time
    else: # crosses midnight
        return time_str1 >= begin_time or time_str1 <= end_time

class Mtapi(object):

    class _Station(object):
        last_update = None

        def __init__(self, json):
            self.json = json
            self.trains = {}
            self.clear_train_data()

        def __getitem__(self, key):
            return self.json[key]

        def add_train(self, route_id, trip_id, terminal_id, direction, train_time, feed_time, stop_id=None,
                      via_roosevelt_island=False, jfk_ahead=False):
            # currentTime = dt.datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S%z')
            # etaTime = timeDifference(currentTime, train_time)
            # etaTime = 1
            try:
                terminal_name = stopJSON[terminal_id[:3]]['stop_name']
            except:
                terminal_name = "ERR"

            # Get direction label from stop data
            direction_label = None
            if stop_id and stop_id in stopJSON:
                stop_data = stopJSON[stop_id]
                if direction == 'N' and 'north_direction_label' in stop_data:
                    direction_label = stop_data['north_direction_label']
                elif direction == 'S' and 'south_direction_label' in stop_data:
                    direction_label = stop_data['south_direction_label']

            expressDiamondChars = ["X"]
            expressNonDiamondChars = ["A", "2", "3", "4", "5", "B", "D", "N", "Q"]
            skipStopChars = ["J", "Z"]
            service = "local"
            if route_id[-1] in expressDiamondChars:
                service = "expressDiamond"
            elif route_id[-1] in expressNonDiamondChars:
                service = "express"

            self.routes.add(route_id)

            train_data = {
                'route': route_id,
                'direction': direction,
                'service': service,
                'time': train_time,
                'trip': trip_id,
                #'eta': etaTime,
                'terminal': terminal_id,
                'terminalName': terminal_name
            }

            # Add direction label if available
            if direction_label:
                train_data['directionLabel'] = direction_label

            train_data.update(terminal_labels(
                stopJSON.get(stop_id, {}), stopJSON.get(terminal_id[:3], {}),
                terminal_name, direction_label, via_roosevelt_island, jfk_ahead))

            self.trains[direction].append(train_data)
            self.last_update = feed_time

        def clear_train_data(self):
            self.trains['N'] = []
            self.trains['S'] = []
            self.alltrains = []
            self.routes = set()
            self.last_update = None

        def sort_trains(self, max_trains):
            self.alltrains = self.trains['S'] + self.trains['N']
            self.trains['S'] = sorted(self.trains['S'], key=itemgetter('time'))[:max_trains]
            self.trains['N'] = sorted(self.trains['N'], key=itemgetter('time'))[:max_trains]
            self.alltrains = sorted(self.alltrains, key=itemgetter('time'))[:max_trains]

        def serialize(self, requested_stop_id=None, stop_id_to_name=None):
            out = {
                'N': self.trains['N'],
                'S': self.trains['S'],
                'alltrains': self.alltrains,
                'routes': self.routes,
                'last_update': self.last_update
            }
            out.update(self.json)

            # If a specific stop_id was requested, customize the name
            if requested_stop_id and stop_id_to_name:
                requested_stop_id_upper = requested_stop_id.upper()
                if requested_stop_id_upper in self.json.get('stops', {}):
                    # Get all stop names for this station
                    stop_names = []
                    requested_name = None

                    for stop_id in self.json['stops'].keys():
                        if stop_id in stop_id_to_name:
                            name = stop_id_to_name[stop_id]
                            if stop_id == requested_stop_id_upper:
                                requested_name = name
                            else:
                                stop_names.append(name)

                    # Put requested stop's name first, then join others
                    if requested_name:
                        # Remove duplicates while preserving order
                        unique_other_names = []
                        seen = set([requested_name])
                        for name in stop_names:
                            if name not in seen:
                                unique_other_names.append(name)
                                seen.add(name)

                        if unique_other_names:
                            out['stationName'] = requested_name + ' | ' + ' | '.join(unique_other_names)
                        else:
                            out['stationName'] = requested_name

            return out
        

    _FEED_URLS = [
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs',  # 1234567S
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l',  # L
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw', # NRQW
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm', # BDFM
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace', # ACE
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si', # (SIR)
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz', # JZ
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g'  # G
    ]

    def __init__(self, key, stations_file, stops_file, expires_seconds=60, max_trains=10, max_minutes=30, threaded=False):
        self._KEY = key
        self._MAX_TRAINS = max_trains
        self._MAX_MINUTES = max_minutes
        self._EXPIRES_SECONDS = expires_seconds
        self._THREADED = threaded
        self._stations = {}
        self._stops = {}
        self._stops_to_stations = {}
        self._stop_id_to_name = {}
        self._routes = {}
        self._read_lock = threading.RLock()

        # initialize the stations database
        try:
            with open(stations_file, 'r') as f:
                self._stations = json.load(f)
                global stationJSON
                stationJSON = self._stations.copy()
                for id in self._stations:
                    self._stations[id] = self._Station(self._stations[id])
                self._stops_to_stations = self._build_stops_index(self._stations)

        except IOError as e:
            print('Couldn\'t load stations file '+stations_file)
            exit()

        try:
            with open(stops_file, 'r') as f:
                self._stops = json.load(f)
                global stopJSON
                stopJSON = self._stops.copy()
                # Build stop_id to name mapping
                for stop_id, stop_data in self._stops.items():
                    if 'stop_name' in stop_data:
                        self._stop_id_to_name[stop_id] = stop_data['stop_name']

        except IOError as e:
            print('Couldn\'t load stops file '+ stops_file)
            exit()

        self._update()

        if threaded:
            self.threader = _MtapiThreader(self, expires_seconds)
            self.threader.start_timer()

    @staticmethod
    def _build_stops_index(stations):
        stops = {}
        for station_id in stations:
            for stop_id in stations[station_id]['stops'].keys():
                stops[stop_id] = station_id

        return stops

    def _load_mta_feed(self, feed_url):
        try:
            request = urllib.request.Request(feed_url)
            request.add_header('x-api-key', self._KEY)
            with contextlib.closing(urllib.request.urlopen(request)) as r:
                data = r.read()
                return FeedResponse(data)

        except (urllib.error.URLError, google.protobuf.message.DecodeError, ConnectionResetError) as e:
            logger.error('Couldn\'t connect to MTA server: ' + str(e))
            return False

    def _update(self):
        logger.info('updating...')
        self._last_update = dt.datetime.now(TZ)

        # create working copy for thread safety
        stations = copy.deepcopy(self._stations)

        # clear old times
        for id in stations:
            stations[id].clear_train_data()

        routes = defaultdict(set)

        for i, feed_url in enumerate(self._FEED_URLS):
            mta_data = self._load_mta_feed(feed_url)

            if not mta_data:
                continue

            max_time = self._last_update + dt.timedelta(minutes = self._MAX_MINUTES)

            for entity in mta_data.entity:
                trip = Trip(entity)

                if not trip.is_valid():
                    continue

                direction = trip.direction[0]
                route_id = trip.route_id.upper()
                trip_id = trip.trip_id
                terminal_id = trip.terminal_id

                stop_updates = entity.trip_update.stop_time_update
                # Inspect the whole supplied sequence before MAX_MINUTES/MAX_TRAINS
                # remove arrivals. This applies to any line and either direction.
                roosevelt_island_positions = [
                    index for index, update in enumerate(stop_updates)
                    if update.stop_id[:3] == 'B06' and update.schedule_relationship != update.SKIPPED
                ]
                jfk_positions = [
                    index for index, update in enumerate(stop_updates)
                    if update.schedule_relationship != update.SKIPPED
                    and 'JFK' in self._stop_id_to_name.get(update.stop_id[:3], '').upper()
                ]
                terminal_index = len(stop_updates) - 1

                for index, update in enumerate(stop_updates):
                    if update.schedule_relationship == update.SKIPPED:
                        continue
                    trip_stop = TripStop(update)

                    if trip_stop.time < self._last_update or trip_stop.time > max_time:
                        continue

                    stop_id = trip_stop.stop_id

                    if stop_id not in self._stops_to_stations:
                        logger.info('Stop %s not found', stop_id)
                        continue

                    station_id = self._stops_to_stations[stop_id]
                    stations[station_id].add_train(route_id,
                                                   trip_id,
                                                   terminal_id,
                                                   direction,
                                                   trip_stop.time,
                                                   mta_data.timestamp,
                                                   stop_id,
                                                   via_roosevelt_island=any(
                                                       index < via_index < terminal_index
                                                       for via_index in roosevelt_island_positions),
                                                   jfk_ahead=any(index < jfk_index for jfk_index in jfk_positions))

                    routes[route_id].add(stop_id)


        # sort by time
        for id in stations:
            stations[id].sort_trains(self._MAX_TRAINS)

        with self._read_lock:
            self._routes = routes
            self._stations = stations

    def last_update(self):
        return self._last_update

    def get_by_point(self, point, limit=5):
        if self.is_expired():
            self._update()

        with self._read_lock:
            sortable_stations = copy.deepcopy(self._stations).values()

        sorted_stations = sorted(sortable_stations, key=lambda s: distance(s['location'], point))
        serialized_stations = map(lambda s: s.serialize(), sorted_stations)

        return list(islice(serialized_stations, limit))

    def get_routes(self):
        return self._routes.keys()

    def get_by_route(self, route):
        route = route.upper()

        if self.is_expired():
            self._update()

        with self._read_lock:
            out = [ self._stations[self._stops_to_stations[k]].serialize() for k in self._routes[route] ]

        out.sort(key=lambda x: x['name'])
        return out

    def get_by_id(self, ids):
        if self.is_expired():
            self._update()

        with self._read_lock:
            out = []
            for requested_id in ids:
                requested_id_upper = requested_id.upper()

                # Check if it's a stop ID first (even if it's also a parent station ID)
                if requested_id_upper in self._stops_to_stations:
                    parent_id = self._stops_to_stations[requested_id_upper]
                    out.append(self._stations[parent_id].serialize(
                        requested_stop_id=requested_id_upper,
                        stop_id_to_name=self._stop_id_to_name
                    ))
                # Check if it's only a parent station ID (not also a stop)
                elif requested_id_upper in self._stations:
                    out.append(self._stations[requested_id_upper].serialize())
                else:
                    # ID not found - this will cause a KeyError to be caught by the caller
                    raise KeyError(f"Station or stop ID '{requested_id}' not found")

        return out

    def is_expired(self):
        if self._THREADED and self.threader and self.threader.restart_if_dead():
            return False
        elif self._EXPIRES_SECONDS:
            age = dt.datetime.now(TZ) - self._last_update
            return age.total_seconds() > self._EXPIRES_SECONDS
        else:
            return False
