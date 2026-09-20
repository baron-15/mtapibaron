"""Fetch MTA alerts once per interval and attach relevant notices to stations."""
import json
import logging
import math
import threading
import time
from urllib.request import urlopen

logger = logging.getLogger(__name__)
SUBWAY_ALERTS_URL = 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json'


def field(value, snake, camel):
    return value.get(snake, value.get(camel)) if isinstance(value, dict) else None


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def normalize_route(value):
    route = str(value or '').upper().removesuffix('X')
    return 'SI' if route == 'SIR' else route


def english_text(value):
    translations = value.get('translation', []) if isinstance(value, dict) else []
    if not isinstance(translations, list):
        return ''
    translations = [item for item in translations if isinstance(item, dict)]
    for language in ('en', ''):
        for item in translations:
            if str(item.get('language') or '').lower() == language and isinstance(item.get('text'), str):
                return item['text'].strip()
    return ''


def active_window(alert, now):
    periods = field(alert, 'active_period', 'activePeriod')
    if periods is None or periods == []:
        return True, None
    if not isinstance(periods, list):
        return False, None
    ends = []
    for period in periods:
        if not isinstance(period, dict):
            continue
        start, end = number(period.get('start')), number(period.get('end'))
        if period.get('start') is not None and start is None or period.get('end') is not None and end is None:
            continue
        if (start is None or start <= now) and (end is None or now < end):
            ends.append(end)
    return bool(ends), None if None in ends or not ends else max(ends)


def select_alerts(feed, station, now):
    stops = {str(stop).rstrip('NS') for stop in station.get('stops', {})}
    routes = {normalize_route(train.get('route')) for train in station.get('alltrains', [])
              if isinstance(train, dict) and str(train.get('terminal', '')).rstrip('NS') not in stops}
    routes.discard('')
    if not routes:
        return []
    selected, seen = [], set()
    for entity in feed.get('entity', []):
        if not isinstance(entity, dict) or entity.get('is_deleted') or entity.get('isDeleted'):
            continue
        alert = entity.get('alert')
        if not isinstance(alert, dict):
            continue
        active, active_until = active_window(alert, now)
        if not active:
            continue
        selectors = field(alert, 'informed_entity', 'informedEntity')
        matched, station_match = set(), False
        for selector in selectors if isinstance(selectors, list) else []:
            if not isinstance(selector, dict):
                continue
            agency = field(selector, 'agency_id', 'agencyId')
            if agency and agency != 'MTASBWY':
                continue
            route = normalize_route(field(selector, 'route_id', 'routeId') or field(selector.get('trip'), 'route_id', 'routeId'))
            stop = field(selector, 'stop_id', 'stopId')
            if route in routes:
                matched.add(route)
            elif not route and stop and str(stop).rstrip('NS') in stops:
                station_match = True
        if not matched and not station_match:
            continue
        text = english_text(field(alert, 'header_text', 'headerText')) or english_text(field(alert, 'description_text', 'descriptionText'))
        if not text:
            continue
        mercury = alert.get('transit_realtime.mercury_alert') or alert.get('.mercuryAlert') or {}
        alert_type = str(field(mercury, 'alert_type', 'alertType') or 'Service change')
        identity = str(entity.get('id') or json.dumps([alert_type, text, sorted(matched)]))
        if identity in seen:
            continue
        seen.add(identity)
        planned = 'planned_work' in identity or alert_type.startswith('Planned -')
        selected.append({
            'id': identity, 'routes': sorted(matched), 'stationWide': station_match,
            'text': text, 'type': alert_type, 'planned': planned,
            'updatedAt': number(field(mercury, 'updated_at', 'updatedAt')),
            'schedule': english_text(field(mercury, 'human_readable_active_period', 'humanReadableActivePeriod')),
            'activeUntil': active_until
        })
    return sorted(selected, key=lambda item: (item['planned'], -(item['updatedAt'] or 0), item['id']))


class ServiceAlerts:
    def __init__(self, cache_seconds=60, max_stale_seconds=300, opener=urlopen, clock=time.time,
                 thread_factory=threading.Thread):
        self.cache_seconds = cache_seconds
        self.max_stale_seconds = max_stale_seconds
        self._open, self._clock, self._thread_factory = opener, clock, thread_factory
        self._lock = threading.Lock()
        self._feed = None
        self._fetched_at = self._retry_at = 0
        self._refreshing = self._failed = False

    def _refresh(self):
        try:
            with self._open(SUBWAY_ALERTS_URL, timeout=5) as response:
                feed = json.load(response)
            if not isinstance(feed, dict) or not isinstance(feed.get('entity'), list):
                raise ValueError('Invalid MTA alert feed')
            timestamp = number(field(feed.get('header'), 'timestamp', 'timestamp'))
            if timestamp is None or timestamp <= 0 or timestamp > self._clock() + 60:
                raise ValueError('Invalid MTA alert publication timestamp')
            # MTA can return a current feed whose publication timestamp has not
            # changed for many minutes. Freshness follows successful retrieval;
            # individual active periods determine whether notices apply now.
            with self._lock:
                self._feed, self._fetched_at = feed, self._clock()
                self._retry_at = self._fetched_at + self.cache_seconds
                self._failed = False
        except (OSError, ValueError, TypeError) as error:
            logger.warning('Could not refresh subway alerts: %s', error)
            with self._lock:
                self._failed = True
                self._retry_at = self._clock() + min(30, self.cache_seconds)
        finally:
            with self._lock:
                self._refreshing = False

    def snapshot(self):
        start = False
        with self._lock:
            now = self._clock()
            if now >= self._retry_at and not self._refreshing:
                self._refreshing = True
                start = True
        if start:
            # Never make a station/arrival response wait for MTA's alerts server.
            self._thread_factory(target=self._refresh, daemon=True).start()
        with self._lock:
            now = self._clock()
            usable = self._feed is not None and now - self._fetched_at <= self.max_stale_seconds
            return {
                'status': ('stale' if self._failed else 'ok') if usable else ('unavailable' if self._failed or self._feed else 'loading'),
                'updatedAt': number(self._feed['header']['timestamp']) if self._feed else None,
                'expiresAt': self._fetched_at + self.max_stale_seconds if usable else None,
                'feed': self._feed if usable else None
            }

    def attach(self, stations):
        if not stations:
            return []
        snapshot = self.snapshot()
        metadata = {key: value for key, value in snapshot.items() if key != 'feed'}
        now = self._clock()
        return [{**station, 'serviceAlerts': {
            **metadata,
            'alerts': select_alerts(snapshot['feed'], station, now) if snapshot['feed'] else []
        }} for station in stations]
