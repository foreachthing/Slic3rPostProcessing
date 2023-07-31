"""
    _summary_
"""

# pylint: disable = line-too-long, missing-function-docstring


from enum import IntEnum


class MyRegex():
    """
        Class for REGEX
    """

    def __init__(self):
        self.find_number = r"-?\d*\.?\d+"
        self.find_layer_m117 = r"^M117 Layer (\d+)"
        self.find_layer_num = r";layer:\s*(\d+)"
        self.find_z = r"^;Z:(.*)"
        self.find_z_value = r"Z(-?\d*(?:\.\d+)?)"
        # self.pattern_safezone = r'G1.*(?:move to first perimeter point)'
        self.pattern_safezone = r'G1.*(?: move to first infill point)'

        # self.find_object = r"(next object)"


class SlicersArgParse(IntEnum):
    """
    Class for argparse 

    https://stackoverflow.com/a/55500795/827526

    Don't ever change this enum's order!
    """

    PRUSA = 0
    ORCA = 1

    # magic methods for argparse compatibility

    def __str__(self):
        return self.name.lower()

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(thistring):
        try:
            return SlicersArgParse[thistring.upper()]
        except KeyError:
            return thistring


class Slic3rs():
    """
        _summary_

    """

    str_config_start = [
        "; prusaslicer_config = begin",
        "; CONFIG_BLOCK_START"
    ]

    str_start_object = [
        "; move to origin position for next object",
        "; move to origin position for next object travel_to_xyz"
    ]

    str_foothead = [
        "; # # # # # # END Header",
        "; # # # # # # START Footer"
    ]


class PPSConfig(object):
    """
        Class instead of of global vars
    """

    def __init__(self):
        self.filecounter = 0
        self.counterdigits = 0
        self.iobh = 999
        self.configfile = None
