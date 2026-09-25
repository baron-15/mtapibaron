# Jan 5th 2025 update
Hello from Baron! This is just a refresher to myself on how I built this website (and its API)!

## Origin and credits

This project is derived from [MTAPI](https://github.com/jonthornton/MTAPI) by Jon Thornton, released under the MIT license. The core JSON proxy (`main.py`, `mtapi/`, `mtaproto/`, the station scripts and the endpoint docs) is his work. Everything since December 2023 (ETA accuracy, service alerts, train counts, the arrival-display UI in `templates/`, deploy config) is mine. See [NOTICE.md](NOTICE.md) for the file-by-file breakdown and [LICENSE](LICENSE) for the license text. Please report issues with this fork [here](https://github.com/baron-15/mtapibaron/issues) rather than to upstream.

# THANKS
https://www.youtube.com/watch?v=Nle8PcBSXrk and https://certbot.eff.org/instructions?ws=apache&os=debianbuster for HTTPS certificate.

# Running the index.html after running the server
Trying to create a UI to replicate the MTA realtime arrival screen on New York subway platforms

# MTA Realtime API JSON Proxy (adapted from MTAPI)

_The sections below are adapted from the upstream [MTAPI](https://github.com/jonthornton/MTAPI) README by Jon Thornton._

MTAPI is a small HTTP server that converts the [MTA's realtime subway feed](https://api.mta.info/#/landing) from [Protocol Buffers/GTFS](https://developers.google.com/transit/gtfs/) to JSON. The app also adds caching and makes it possible to retrieve information by location and train line. 

## Active Development

This project is under active development and any part of the API may change. Feedback is very welcome.

## Running the server

MTAPI is a Flask app designed to run under Python 3.3+.

1. Review `settings.cfg`. It is committed with working defaults; `settings.cfg.sample` is a pristine copy to start from if you change it.
2. Set up your environment and install dependencies.  
`$ python3 -m venv .venv`  
`$ source .venv/bin/activate`  
`$ python3 -m pip install -r requirements.txt`
3. Run the server  
`$ python main.py`

If your configuration is named something other than `settings.cfg`, set the `MTAPI_SETTINGS` env variable to your configuration path.

This app makes use of Python threads. If running under uWSGI include the --enable-threads flag.

## Endpoints

[Endpoints to retrieve train data and sample input and output are listed here.](docs/endpoints.md)

### Subway service alerts

Every station in `/by-id`, `/by-route`, and `/by-location` includes `serviceAlerts`:

```json
{"status":"ok","updatedAt":1789921498,"expiresAt":1789923340,"alerts":[{"id":"lmm:alert:example","routes":["B"],"stationWide":false,"type":"Delays","planned":false,"text":"Northbound [B] trains are delayed.","updatedAt":1789921497,"schedule":"","activeUntil":null}]}
```

The backend fetches the public [MTA subway alerts feed](https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json) at most once every 60 seconds per worker while station requests are active. One background refresh serves all stations; station requests never wait for that fetch. Failed refreshes retry after 30 seconds and reuse cached alerts for at most five minutes. `status` is `loading`, `ok`, `stale`, or `unavailable`; errors never suppress train arrivals.

The server selects active alerts for the station's arriving routes and stop-only station notices, excludes terminating trains, removes duplicates, and orders unplanned notices first. It returns plain English and preserves bracketed route tokens for the display. The frontend only applies its local hidden-route preference and rotates the results, with no separate alert requests or direct MTA calls.

`updatedAt` is the feed's publication timestamp, which may remain unchanged between successful MTA responses. Cache freshness uses successful retrieval time; `active_period` determines whether work is happening now. See the [MTA alert specification](https://www.mta.info/document/90881). `expiresAt` bounds client reuse when station requests fail, and `activeUntil` lets the display remove an ending alert between station updates.

Deploy the backend on Render before the frontend; the frontend uses only the Render API host. Older responses without `serviceAlerts` display an unavailable message instead of starting browser-side MTA polling.

### V2 terminal labels

Every train in `N`, `S`, and `alltrains` includes `terminalPrimary` and
`terminalSecondary` (a string or `null`). The frontend renders these directly;
`terminalName`, `terminal`, and `directionLabel` remain unchanged for V1 and audio.
See the [train field contract](docs/endpoints.md#terminal-display-fields).

Terminal headlines split Forest Hills / 71 Av, Bay Ridge / 95 St,
34 St / Hudson Yards, Far Rockaway / Mott Av, and Coney Island / Stillwell Av,
while Jamaica Center omits Parsons/Archer.
Under a borough or direction headline,
only the short destination name appears in the subtitle (for example,
Manhattan / Bay Ridge). Exceptions follow the actual terminal stop ID on any
route; Jamaica-179 St stays intact.

Labels are calculated per actual stop within the station complex. Borough
headings stay singular. At Manhattan stops, Uptown/Downtown can add the terminal
borough, including `Uptown & The Bronx` for a Bronx terminal. Roosevelt Island
is a subtitle qualifier only when the trip's supplied stop sequence includes
it ahead of the current stop and strictly before the terminal. This applies
to any line and either direction, excludes skipped stops, and runs before
`MAX_MINUTES` and `MAX_TRAINS` trim arrivals. An explicitly listed stop without
a time prediction still supplies routing information; absent stops are not
inferred from a line's usual route. Existing `via` text is preserved.

Any train identifies JFK when its supplied stop sequence includes an upcoming,
non-skipped station whose name contains `JFK` (case-insensitive). This covers
Sutphin Blvd-Archer Av-JFK Airport and Howard Beach-JFK Airport. Under a direction
headline, the subtitle adds `/JFK` (for example, `Jamaica Center/JFK`); under a
terminal headline, an empty subtitle becomes `JFK`. This follows the actual trip
in either direction, clears when no JFK stop remains ahead, and preserves
Roosevelt Island text. Trains without an upcoming JFK stop, including A trains
to Lefferts Blvd, keep their existing labels.

Deploy this backend on Render before the frontend that consumes these fields.
An older backend remains usable via the frontend's plain `terminalName` fallback.

Run focused backend checks with
`python -m unittest discover -s tests -p 'test_terminal_labels.py'` and
`python -m unittest discover -s tests -p 'test_service_alerts.py'`.

## Settings

- **MTA_KEY** (required)  
The API key provided at hhttps://api.mta.info/#/signup
*default: None*

- **STATIONS_FILE** (required)  
Path to the JSON file containing station information. See [Generating a Stations File](#generating-a-stations-file) for more info.  
*default: None*

- **CROSS_ORIGIN**    
Add [CORS](http://enable-cors.org/) headers to the HTTP output.  
*default: "&#42;" when in debug mode, None otherwise*

- **MAX_TRAINS**  
Limits the number of trains that will be listed for each station.  
*default: 10*

- **MAX_MINUTES**  
Limits how far in advance train information will be listed.  
*default: 30*

- **CACHE_SECONDS**  
How frequently the app will request fresh data from the MTA API.  
*default: 60*

- **THREADED**  
Enable background data refresh. This will prevent requests from hanging while new data is retreived from the MTA API.  
*default: True*

- **DEBUG**  
Standard Flask option. Will enabled enhanced logging and wildcard CORS headers.  
*default: False*

## Generating a Stations File

The MTA provides several static data files about the subway system but none include canonical information about each station. MTAPI includes a script that will parse the `stops.txt` and `transfers.txt` datasets provided by the MTA and attempt to group the different train stops into subway stations. MTAPI will use this JSON file for station names and locations. The grouping is not perfect and editing the resulting files is encouraged.

Usage: 
```
$ python make_stations_csv.py stops.txt transfers.txt > stations.csv
# edit groupings in stations.csv
$ python make_stations_json.py stations.csv > stations.json
# edit names in stations.json
```

## Help

Submit a [GitHub Issues request](https://github.com/baron-15/mtapibaron/issues) for this fork. For the original project, see [jonthornton/MTAPI](https://github.com/jonthornton/MTAPI).

## Projects

Here are some projects that use MTAPI.

* http://wheresthefuckingtrain.com

## License

This project is made available under the MIT license. See [LICENSE](LICENSE).

- Copyright (c) 2014 Jon Thornton, original [MTAPI](https://github.com/jonthornton/MTAPI) code
- Copyright (c) 2023-2026 Baron C, modifications in this repository

See [NOTICE.md](NOTICE.md) for which files come from upstream and for third-party notices.
