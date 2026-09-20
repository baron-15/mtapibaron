# Notices

## Origin

This repository is a derivative of **MTAPI** by Jon Thornton
(<https://github.com/jonthornton/MTAPI>), a JSON proxy for the MTA's realtime
New York City subway feed. MTAPI is made available under the MIT license, as
declared in its README (the upstream project ships no separate LICENSE file).

The code was copied on 2023-12-25 from upstream commit
[`1e8df9d`](https://github.com/jonthornton/MTAPI/tree/1e8df9d381461ebd2308dbb9df8e50835cda6fad)
and has been modified independently since then: ETA-accuracy changes,
per-station service alerts, train counts, a realtime arrival-display UI, and
deployment configuration. It is not kept in sync with upstream. Issues with this
repository belong at <https://github.com/baron-15/mtapibaron/issues>, not with
the upstream project.

The full license text, including both copyright notices, is in [LICENSE](LICENSE).

## Files derived from MTAPI

- `main.py` (upstream `app.py`)
- `mtapi/__init__.py`, `mtapi/mtapi.py`, `mtapi/_mtapithreader.py`
- `mtaproto/feedresponse.py`, plus the `.proto` schemas and generated `*_pb2.py`
  modules as vendored upstream
- `scripts/make_stations_csv.py`, `scripts/make_stations_json.py`
- `tests/test_mtapi.py`
- `docs/endpoints.md`
- The sections of `README.md` from "MTA Realtime API JSON Proxy" onward

## Files original to this repository

- `mtapi/service_alerts.py`, `tests/test_service_alerts.py`
- `templates/` (the arrival-display frontend)
- `scripts/make_stationsv2_json.py`, `scripts/make_stops_json_retired.py`,
  `scripts/stationsv2.*`
- `app.yaml`, `.gcloudignore`

## Note on the `main.py` header

The module docstring in `main.py` reads `:license: BSD, see LICENSE for more
details.` That header is inherited verbatim from upstream `app.py`, whose
project license is declared as MIT. The header has been left unmodified. This
file and `LICENSE` are authoritative for the licensing of this repository.

## Third-party components

- `mtaproto/gtfs-realtime.proto`: Copyright 2015 The GTFS Specifications
  Authors. Licensed under the Apache License, Version 2.0 (see the header in
  that file).
- `mtaproto/nyct-subway.proto`, `scripts/gtfs_subway/`, `scripts/stops.txt`,
  `scripts/transfers.txt`, `scripts/trips.txt`, `data/stops.txt`: the MTA's
  GTFS-realtime extension schema and static GTFS data, published by the
  Metropolitan Transportation Authority and subject to its developer terms.
  The `stations*.csv` and `stations*.json` files under `data/` and `scripts/`
  are generated from that data with the station scripts.
- `scripts/make_stationsv2_json.py` and `scripts/make_stops_json_retired.py`
  include a snippet adapted from GeeksforGeeks (author khushali_verma),
  credited in-file.
