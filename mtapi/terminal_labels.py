"""Station-relative display text; raw destination fields remain available for audio."""

import re


DIRECTIONS = {'Uptown', 'Downtown'}
BOROUGHS = {'Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'The Bronx'}
BOROUGH_NAMES = {'Bk': 'Brooklyn', 'Q': 'Queens'}


def terminal_labels(current_stop, terminal_stop, terminal_name, direction_label,
                    via_roosevelt_island=False):
    uses_direction = direction_label in DIRECTIONS | BOROUGHS
    primary = direction_label if uses_direction else terminal_name
    secondary = terminal_name if uses_direction else None

    if direction_label in DIRECTIONS and current_stop.get('borough') == 'M':
        terminal_borough = terminal_stop.get('borough')
        if direction_label == 'Uptown' and terminal_borough == 'Bx':
            primary += ' & The Bronx'
        elif terminal_borough in BOROUGH_NAMES:
            primary += ' & ' + BOROUGH_NAMES[terminal_borough]

    if via_roosevelt_island and terminal_name and not re.search(r'\bvia\b', terminal_name, re.I):
        secondary = terminal_name + ' via Roosevelt Island' if uses_direction else 'via Roosevelt Island'

    return {'terminalPrimary': primary, 'terminalSecondary': secondary}
