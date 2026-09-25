> Adapted from [MTAPI's endpoint documentation](https://github.com/jonthornton/MTAPI/blob/master/docs/endpoints.md) by Jon Thornton (MIT). Response shapes may differ where this fork changed them (for example `serviceAlerts`).

## Endpoints

- **/by-location?lat=[latitude]&lon=[longitude]**  
Returns the 5 stations nearest the provided lat/lon pair.
```javascript
{
    "data": [
        {
            "N": [
                {
                    "route": "6",
                    "time": "2014-08-29T14:00:55-04:00"
                },
                {
                    "route": "6X",
                    "time": "2014-08-29T14:10:30-04:00"
                },
                ...
            ],
            "S": [
                {
                    "route": "6",
                    "time": "2014-08-29T14:04:14-04:00"
                },
                {
                    "route": "6",
                    "time": "2014-08-29T14:11:07-04:00"
                },
                ...
            ],
            "hasData": true,
            "id": 123,
            "location": [
                40.725606,
                -73.9954315
            ],
            "name": "Broadway-Lafayette St / Bleecker St",
            "routes": [
                "6X",
                "6"
            ],
            "stops": {
                "637": [
                    40.725915,
                    -73.994659
                ],
                "D21": [
                    40.725297,
                    -73.996204
                ]
            }
        },
        {
            "N": [
                {
                    "route": "6X",
                    "time": "2014-08-29T14:09:30-04:00"
                },
                {
                    "route": "6",
                    "time": "2014-08-29T14:13:30-04:00"
                },
                ...
            ],
            "S": [
                {
                    "route": "6",
                    "time": "2014-08-29T14:05:14-04:00"
                },
                {
                    "route": "6",
                    "time": "2014-08-29T14:12:07-04:00"
                },
                ...
            ],
            "hasData": true,
            "id": 124,
            "location": [
                40.723315,
                -73.9974215
            ],
            "name": "Spring St / Prince St",
            "routes": [
                "6X",
                "6"
            ],
            "stops": {
                "638": [
                    40.722301,
                    -73.997141
                ],
                "R22": [
                    40.724329,
                    -73.997702
                ]
            }
        },
        ...
    ],
    "updated": "2014-08-29T15:27:27-04:00"
}
```

- **/by-route/[route]**  
Returns all stations on the provided train route.  
```javascript
{
    "data": [
        {
            "N": [
                {
                    "route": "6X",
                    "time": "2014-08-29T14:01:54-04:00"
                },
                {
                    "route": "5",
                    "time": "2014-08-29T14:04:35-04:00"
                },
                {
                    "route": "4",
                    "time": "2014-08-29T14:07:00-04:00"
                },
                ...
            ],
            "S": [
                {
                    "route": "6",
                    "time": "2014-08-29T14:01:53-04:00"
                },
                {
                    "route": "4",
                    "time": "2014-08-29T14:04:52-04:00"
                },
                ...
            ],
            "hasData": true,
            "id": 12,
            "location": [
                40.804138,
                -73.937594
            ],
            "name": "125 St",
            "routes": [
                "6X",
                "5",
                "4",
                "6"
            ],
            "stops": {
                "621": [
                    40.804138,
                    -73.937594
                ]
            }
        },
        {
            "N": [
                {
                    "route": "5",
                    "time": "2014-08-29T14:07:05-04:00"
                },
                {
                    "route": "4",
                    "time": "2014-08-29T14:09:30-04:00"
                },
                ...
            ],
            "S": [
                {
                    "route": "4",
                    "time": "2014-08-29T14:02:22-04:00"
                },
                {
                    "route": "5",
                    "time": "2014-08-29T14:03:36-04:00"
                },
                ...
            ],
            "hasData": true,
            "id": 123,
            "location": [
                40.813224,
                -73.929849
            ],
            "name": "138 St - Grand Concourse",
            "routes": [
                "5",
                "4"
            ],
            "stops": {
                "416": [
                    40.813224,
                    -73.929849
                ]
            }
        },
        ...
    ],
    "updated": "2014-08-29T15:25:27-04:00"
}
```

- **/by-id/[id],[id],[id]...**  
Returns the stations with the provided IDs, in the order provided. IDs should be comma separated with no space characters.

- **/routes**  
Lists available routes.  
```javascript
{
    "data": [
        "S",
        "L",
        "1",
        "3",
        "2",
        "5",
        "4",
        "6",
        "6X"
    ],
    "updated": "2014-08-29T15:09:57-04:00"
}
```

## Terminal display fields

Station responses from `/by-id`, `/by-route`, and `/by-location` include these
fields on each train in `N`, `S`, and `alltrains`:

```json
{
    "route": "M",
    "direction": "N",
    "trip": "example-trip",
    "terminal": "G08N",
    "terminalName": "Forest Hills-71 Av",
    "directionLabel": "Uptown",
    "terminalPrimary": "Uptown & Queens",
    "terminalSecondary": "Forest Hills via Roosevelt Island"
}
```

This example describes a train at W 4 St whose trip update includes Roosevelt
Island before Forest Hills. The same trip has different labels at later stops.

- `terminalPrimary`: the V2 headline. Recognized borough direction labels stay
  singular (for example, `Manhattan` for a Brooklyn train entering Manhattan
  before Queens). At Manhattan stops, Uptown/Downtown can add a Brooklyn or Queens
  terminal borough; Uptown can add `The Bronx`. Otherwise the terminal display
  name is the fallback for an unrecognized direction label.
- `terminalSecondary`: the terminal display name under a recognized direction
  heading, or the station detail listed below when the terminal is the headline.
  A `via Roosevelt Island` qualifier is appended to any subtitle, or becomes the
  subtitle when there is no other text. Clients hide a null/empty subtitle.
- `terminalName`, `terminal`, and `directionLabel`: existing destination/direction
  fields, retained without display qualifiers for older clients and audio.

Display names use these exceptions, keyed by the actual terminal stop ID rather
than the route. All other terminals retain their full station names.

| Terminal stop | Terminal as headline | Subtitle under terminal headline | Subtitle under borough/direction heading |
| --- | --- | --- | --- |
| `G08` | Forest Hills | 71 Av | Forest Hills |
| `R45` | Bay Ridge | 95 St | Bay Ridge |
| `G05` | Jamaica Center | `null` | Jamaica Center |
| `726` | 34 St | Hudson Yards | 34 St |
| `H11` | Far Rockaway | Mott Av | Far Rockaway |
| `D43` | Coney Island | Stillwell Av | Coney Island |

For example, a southbound R train in Queens displays `Manhattan` / `Bay Ridge`;
in Brooklyn, with a terminal-based heading, it displays `Bay Ridge` / `95 St`.
`Parsons/Archer` is omitted from V2 display labels, while `terminalName` keeps
`Jamaica Center-Parsons/Archer`. Jamaica-179 St remains one complete display name.

For any route, an upcoming, non-skipped stop whose station name contains `JFK`
(case-insensitive) adds a JFK connection label. The current station data includes
Sutphin Blvd-Archer Av-JFK Airport (`G06`) and Howard Beach-JFK Airport (`H03`):

| Train | Current station | Primary | Secondary |
| --- | --- | --- | --- |
| E to Jamaica Center | 34 St-Penn Station | Uptown & Queens | Jamaica Center/JFK |
| E to Jamaica Center | 5 Av/53 St | Queens | Jamaica Center/JFK |
| E to Jamaica Center | Jamaica-Van Wyck | Jamaica Center | JFK |
| E to Jamaica Center | Sutphin Blvd-Archer Av-JFK Airport | Jamaica Center | `null` |
| J/Z to Jamaica Center | Broad St | Brooklyn | Jamaica Center/JFK |
| J/Z to Jamaica Center | 121 St | Jamaica Center | JFK |
| A to Far Rockaway | Euclid Av | Queens | Far Rockaway/JFK |
| A to Far Rockaway | Aqueduct-N Conduit Av | Far Rockaway | Mott Av/JFK |
| A to Far Rockaway | Broad Channel | Far Rockaway | Mott Av |

The rule uses the actual destination and works in either direction on any route,
including rerouted trains; no route list or fixed airport-stop list is used. It
appends `/JFK` to an existing subtitle or uses `JFK` alone when the subtitle was
empty. A destination already naming JFK, such as Howard Beach, gets no duplicate.
The stop must be strictly ahead of the current stop in the supplied trip
updates; missing/skipped stops do not qualify. An explicit stop without a time
prediction still qualifies, and arrival-window/train-count limits do not hide
it. The extra label is removed when no JFK stop remains ahead. A trains to
Lefferts Blvd do not get it unless their actual supplied stop sequence includes
a JFK stop. No additional feed request is needed.
Roosevelt Island text follows the JFK label when applicable, for example
`Jamaica Center/JFK via Roosevelt Island`. Raw destination/audio fields stay intact.

The Roosevelt Island qualifier uses stop `B06` in the ordered stop updates for
that specific trip. It must be ahead of the current stop, strictly before the
terminal, and not marked `SKIPPED`. It is not added at/after Roosevelt Island,
for a Roosevelt Island terminal, or when the stop is absent from the supplied
sequence. This works for either direction and any route; it does not assume
that every F or M train uses that station. The check precedes arrival-window
and train-count limits and needs no additional feed requests. Existing `via`
text in a terminal name is left intact. Skipped stops do not receive arrivals.
