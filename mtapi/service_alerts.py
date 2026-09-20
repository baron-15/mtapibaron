"""Cache the public MTA subway alert feed separately from train arrivals."""
import json
import logging
import threading
import time
from urllib.request import urlopen


logger = logging.getLogger(__name__)
SUBWAY_ALERTS_URL = 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json'


class AlertsUnavailable(Exception):
    pass


class ServiceAlerts:
    def __init__(self, cache_seconds=60, max_stale_seconds=300, opener=urlopen, clock=time.time):
        self.cache_seconds = cache_seconds
        self.max_stale_seconds = max_stale_seconds
        self._open = opener
        self._clock = clock
        self._lock = threading.Lock()
        self._feed = None
        self._fetched_at = 0
        self._retry_at = 0

    def get(self):
        # The dedicated lock prevents simultaneous browser requests from starting
        # duplicate upstream fetches. Arrival endpoints never acquire this lock.
        with self._lock:
            now = self._clock()
            if now >= self._retry_at:
                try:
                    with self._open(SUBWAY_ALERTS_URL, timeout=5) as response:
                        feed = json.load(response)
                    if not isinstance(feed, dict) or not isinstance(feed.get('entity'), list):
                        raise ValueError('Invalid MTA alert feed')
                    header = feed.get('header')
                    if not isinstance(header, dict):
                        raise ValueError('Invalid MTA alert header')
                    timestamp = float(header.get('timestamp', 0))
                    if not 0 < timestamp <= now + 60 or now - timestamp > self.max_stale_seconds:
                        raise ValueError('MTA alert feed is out of date')
                    self._feed = feed
                    self._fetched_at = now
                    self._retry_at = now + self.cache_seconds
                except (OSError, ValueError, TypeError) as error:
                    logger.warning('Could not refresh subway alerts: %s', error)
                    self._retry_at = now + min(30, self.cache_seconds)
            if self._feed is None or now - self._fetched_at > self.max_stale_seconds:
                raise AlertsUnavailable('Service alerts are temporarily unavailable')
            # Preserve GTFS and Mercury selectors/timestamps for the display to
            # match routes and active periods without interpreting HTML content.
            return {
                'feed': self._feed,
                'fetchedAt': self._fetched_at,
                'stale': now - self._fetched_at >= self.cache_seconds
            }
