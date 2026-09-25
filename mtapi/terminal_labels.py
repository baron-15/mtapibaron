"""Station-relative display text; raw destination fields remain available for audio."""

import re


DIRECTIONS = {'Uptown', 'Downtown'}
BOROUGHS = {'Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'The Bronx'}
BOROUGH_NAMES = {'Bk': 'Brooklyn', 'Q': 'Queens'}
# Key by the actual terminal so rerouted trains receive the same display names.
TERMINAL_DISPLAY_NAMES = {
    'G08': ('Forest Hills', '71 Av'),
    'R45': ('Bay Ridge', '95 St'),
    'G05': ('Jamaica Center', None),
    '726': ('34 St', 'Hudson Yards'),
    'H11': ('Far Rockaway', 'Mott Av'),
    'D43': ('Coney Island', 'Stillwell Av'),
}


def terminal_labels(current_stop, terminal_stop, terminal_name, direction_label,
                    via_roosevelt_island=False, jfk_ahead=False):
    override = TERMINAL_DISPLAY_NAMES.get(terminal_stop.get('gtfs_stop_id'))
    destination, detail = override or (terminal_name, None)
    uses_direction = direction_label in DIRECTIONS | BOROUGHS
    primary = direction_label if uses_direction else destination
    secondary = destination if uses_direction else detail
    # Airport-connection terminals already identify JFK in their station names.
    if jfk_ahead and not re.search(r'\bJFK\b', destination or '', re.I):
        secondary = '/'.join(part for part in (secondary, 'JFK') if part)

    if direction_label in DIRECTIONS and current_stop.get('borough') == 'M':
        terminal_borough = terminal_stop.get('borough')
        if direction_label == 'Uptown' and terminal_borough == 'Bx':
            primary += ' & The Bronx'
        elif terminal_borough in BOROUGH_NAMES:
            primary += ' & ' + BOROUGH_NAMES[terminal_borough]

    existing_via = re.search(r'\bvia\b.*', terminal_name or '', re.I)
    qualifier = None
    if override and existing_via:
        qualifier = existing_via.group()
    elif via_roosevelt_island and terminal_name and not existing_via:
        qualifier = 'via Roosevelt Island'
    if qualifier:
        secondary = ' '.join(part for part in (secondary, qualifier) if part)

    return {'terminalPrimary': primary, 'terminalSecondary': secondary}
