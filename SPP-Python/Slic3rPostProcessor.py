# /usr/bin/python3
""" Post Processing Script for Slic3r, PrusaSlicer and SuperSlicer.
    This will make the curent start behaviour more like Curas'.1

    New behaviour:
    - Heat up, down nozzle and ooze at your discretion.
    - Move to the first entry point on XYZ simultaneously.
    - Or, move to the first entry point on XY first, then Z!

    Features:
    - Obscure configuration at end of file
    - Remove comments except configuration
    - Remove _all_ comments of any kind!
    - Set digits for counter
    - Reset counter
    - Reverse counter
    - use with non PrusaSlicer Slicer
    - Add sort-of progressbar as M117 command
    - Option to disable Cura-move with '--nomove' parameter
    - Option for coloring output to be viewed in CraftWare
    - Option to add total number of layers to slice-info block

    Current behaviour:
    1. Heat up, down nozzle and ooze at your discretion.
    2. Lower nozzle to first layer height and then move to
       first entry point in only X and Y.
       (This move can and will collide with the clips on the Ultimaker 2!)

    Usage:
    - Add this line the the post processing script section of the slicer's
      Configuration (make sure the paths are valid on your system):
      "C:/Program Files/Python39/python.exe" "c:/dev/Slic3rPostProcessing/
        SPP-Python/Slic3rPostProcessor.py" --xy --backup --rk --filecounter;
    - Open a console / command line and type "Slic3rPostProcessor.py -h" for help.

"""

# Script based on:
# http://projects.ttlexceeded.com/3dprinting_prusaslicer_post-processing.html

# got issues?
# Please complain/explain here: https://github.com/foreachthing/Slic3rPostProcessing/issues

#
# "cheat" pylint, because it can be annoying
# pylint: disable = line-too-long, invalid-name, broad-except
#

import decimal
import sys
import re
import argparse
import configparser
import ntpath
from shutil import ReadError, copy2
from os import path, remove, getenv
from decimal import Decimal
import pymsgbox


def argumentparser():
    """
        ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog=path.basename(__file__),
        description='** Slicer Post Processing Script ** \n\r'
        'Do the Cura move, for us with an Ultimaker 2 or similar'
        ' and/or clips on the build plate.'
        ' Since the default PrusaSlicer code tends to move'
        ' right through them - ouch!',
        epilog='Result: An Ultimaker 2 (and up) friedly GCode file.')

    parser.error = myerror

    # get values from config file
    conf = configparser.ConfigParser()
    if path.exists(ppsc.configfile):
        conf.read(ppsc.configfile)
        ppsc.fileincrement = conf.getint(
            'DEFAULT', 'FileIncrement', fallback=0)
        ppsc.counterdigits = conf.getint(
            'DEFAULT', 'CounterDigits', fallback=6)
    ##

    parser.add_argument('input_file', metavar='gcode-files', type=str, nargs='+',
                        help='One or more GCode file(s) to be processed '
                        '- at least one is required.')

    parser.add_argument('--backup', action='store_true', default=False,
                        help='Create a backup file, if True is passed. '
                        '(Default: %(default)s)')

    parser.add_argument('--notprusaslicer', action='store_true', default=False,
                        help='Pass argument for any other slicer (based on Slic3r) than '
                        'PrusaSlicer.')

    parser.add_argument('--craftwaretypes', action='store_true', default=False,
                        help='Pass argument if you want to view GCode in Craftware.')

    grp_info = parser.add_argument_group('Slicer Info')
    grp_info.add_argument('--numlayer', action='store_true', default=False,
                          help='Adds total number of layers to slice-info of G-Code file.')

    move_x_group = parser.add_mutually_exclusive_group()
    move_x_group.add_argument('--xy', action='store_true', default=False,
                              help='If --xy is provided, the printer will move to X and Y '
                              'of first start point, then drop the nozzle to Z at a third '
                              'the normal speed. '
                              '(Default: %(default)s)')

    move_x_group.add_argument('--nomove', action='store_true', default=False,
                              help='If --nomove is provided, no changes to the '
                              'Start-GCode will be made. '
                              '(Default: %(default)s)')

    comment_x_group = parser.add_mutually_exclusive_group()
    comment_x_group.add_argument('--oc', action='store_true', default=False,
                                 help='WIP! Use at own risk - does not yet produce valid PS-gcode.\n'
                                 'Obscures Configuration at end of file with bogus values. '
                                 '(Default: %(default)s)')

    comment_x_group.add_argument('--rk', action='store_true', default=False,
                                 help='Removes comments from end of line, except '
                                 'configuration and pure comments. '
                                 '(Default: %(default)s)')

    comment_x_group.add_argument('--rak', action='store_true', default=False,
                                 help='Removes all comments! Note: PrusaSlicers GCode preview '
                                 'might not render file correctly. '
                                 '(Default: %(default)s)')

    grp_counter = parser.add_argument_group('Counter settings')
    grp_counter.add_argument('--filecounter', action='store_true', default=False,
                             help='Add a prefix counter, if desired, to the output gcode file. '
                             'Default counter length is 6 digits (000001-999999_file.gcode). '
                             f'Currently at {ppsc.fileincrement}. (Default: %(default)s)')

    grp_counter.add_argument('--rev', action='store_true', default=False,
                             help='If True, adds counter in reverse, down to zero and it will restart '
                             'at 999999 if -setcounter was not specified otherwise.'
                             '(Default: %(default)s)')

    grp_counter.add_argument('--setcounter', action='store', metavar='int', type=int,
                             help='Reset counter to this [int]. Or edit spp_config.cfg directly.')

    grp_counter.add_argument('--digits', action='store', metavar='int', type=int, default=6,
                             help='Number of digits for counter. '
                             f'Currently set to: {ppsc.counterdigits}. '
                             '(Default: %(default)s)')

    grp_counter.add_argument('--easeinfactor', action='store', metavar='int', type=int, default=15,
                             help='Scale Factor for ease in on Z. Z moves fast to this point then slows down.'
                             'Scales the first layer height by this factor. '
                             '(Default: %(default)s)')

    grp_progress = parser.add_argument_group('Progress bar settings')
    grp_progress.add_argument('--prog', action='store_true', default=False,
                              help='If --prog is provided, a progress bar instead of layer number/percentage, '
                              'will be added to your GCode file and displayed on your printer (M117). '
                              '(Default: %(default)s)')

    grp_progress.add_argument('--proglayer', action='store_true', default=False,
                              help='If --proglayer is provided, progress is reported as layer number/of layers, '
                              '(Default: %(default)s)')

    grp_progress.add_argument('--pwidth', metavar='int', type=int, default=17,
                              help='Define the progress bar length in characters. You might need to '
                              'adjust the default value. Allow two more chars for brackets. '
                              'Example: [' + 'OOOOO'.ljust(18, '.') + ']. (Default: %(default)d)')

    grp_progress.add_argument('--pchar', metavar='str', type=str, default="O",
                              help='Set progress bar character. '
                              '(Default: %(default)s)')

    try:
        args = parser.parse_args()
        return args

    except IOError as msg:
        parser.error(str(msg))
        sys.exit(1)


def myerror(message):
    """
        Custom Error message for argparse if something goes wrong.
    """
    print(message)
    pymsgbox.alert(text=message,
                   title="Post-Processing Script", button=pymsgbox.OK_TEXT)
    sys.exit(1)


def coords(xy):
    """Processes XY Coordinates for parking

    Args:
        xy (tuple): xy coordinates

    Raises:
        argparse.ArgumentTypeError: _description_

    Returns:
        _type_: _description_
    """
    try:
        x, y = map(int, xy.split(','))
        return x, y
    except Exception as exc:
        print(exc.args)
        raise argparse.ArgumentTypeError("Park Coordinates must be x,y")


def main(args, conf):
    """
        MAIN
    """

    get_configuration(args)

    for sourcefile in args.input_file:

        # Counter: count up or down
        if path.exists(sourcefile):
            # counter increment
            if args.rev:
                ppsc.fileincrement -= 1
                if ppsc.fileincrement < 0:
                    ppsc.fileincrement = (10 ** ppsc.counterdigits) - 1
            else:
                ppsc.fileincrement += 1
                if ppsc.fileincrement >= (10 ** ppsc.counterdigits) - 1:
                    ppsc.fileincrement = 0

            # Create a backup file, if the user wants it.
            try:
                # if user wants a backup file ...
                if args.backup is True:
                    copy2(sourcefile, re.sub(r"\.gcode$", ".gcode.bak",
                          sourcefile, flags=re.IGNORECASE))

            except OSError as exc:
                print('FileNotFoundError (backup file):' + str(exc))
                sys.exit(1)

            #
            #
            process_gcodefile(args, sourcefile)

            #
            #
            destfile = sourcefile
            if args.filecounter:

                # Create Counter String, zero-padded accordingly
                counter = str(ppsc.fileincrement).zfill(ppsc.counterdigits)

                if args.notprusaslicer is False:

                    # get envvar from PrusaSlicer
                    env_slicer_pp_output_name = str(
                        getenv('SLIC3R_PP_OUTPUT_NAME'))

                    # create file for PrusaSlicer with correct name as content
                    with open(sourcefile + '.output_name', mode='w', encoding='UTF-8') as fopen:
                        fopen.write(counter + '_' +
                                    ntpath.basename(env_slicer_pp_output_name))

                else:
                    # NOT PrusaSlicer:
                    destfile = ntpath.join(ntpath.dirname(sourcefile), counter
                                           + '_' + ntpath.basename(sourcefile))

                    copy2(sourcefile, destfile)
                    remove(sourcefile)

            #
            # write settings back
            conf.set('DEFAULT', 'FileIncrement', str(ppsc.fileincrement))
            conf.set('DEFAULT', 'CounterDigits', str(ppsc.counterdigits))

            write_config_file(conf)


def obscure_configuration(strline):
    """
        Obscure _all_ settings
    """
    # the easy way out:
    strline = "; = 0\n"
    return strline


def process_gcodefile(args, sourcefile):
    """
        MAIN Processing.
        To do with ever file from command line.
    """

    # Read the ENTIRE GCode file into memory
    try:
        with open(sourcefile, "r", encoding='UTF-8') as readfile:
            lines = readfile.readlines()
    except ReadError as exc:
        print('FileReadError:' + str(exc))
        sys.exit(1)

    #
    # Define list of progressbar percentage and cacters
    progress_list = [[0, "."], [.25, ":"], [.5, "+"], [.75, "#"]]
    # progress_list = [[.5, "o"]]
    # progress_list = [[0, "0"], [.2, "2"], [.4, "4"], [.6, "6"], [.8, "8"]]
    #

    first_layer_height = 0
    b_edited_line = False
    b_skip_all = False
    b_skip_removed = False
    b_start_remove_comments = False
    b_start_add_custom_info = False
    writefile = None
    number_of_layers = 0
    current_layer = 0
    is_config_comment = True
    icount = 0

    try:
        # Find total layers - search from back of file until
        # first "M117 Layer [num]" is found.
        # Store total number of layers.
        # Also, measure configuration section length.
        len_lines = len(lines)
        for line_index in range(len_lines):
            # start from the back
            strline = lines[len_lines-line_index-1]

            if is_config_comment is True:
                # Count number of lines of the configuration section
                icount += 1
                # find beginning of configuration section
                if strline == "; prusaslicer_config = begin\n":
                    is_config_comment = False

            # Find last Layer:
            rgxm117 = re.search(regex.findlayer, strline, flags=re.IGNORECASE)
            if rgxm117:
                # Found M117 Layer xy
                number_of_layers = int(rgxm117.group(1))
                break
    except Exception as exc:
        print("Oops! Something went wrong in finding total numbers of layers. " + str(exc))
        sys.exit(1)

    try:
        with open(sourcefile, "w", newline='\n', encoding='UTF-8') as writefile:

            # Store args in vars - easier to type, or change, add...
            argprogress = args.prog
            argprogresslayer = args.proglayer
            args_info_numlayer = args.numlayer
            argscraftwaretypes = args.craftwaretypes
            argseaseinfactor = args.easeinfactor
            argsnocuramove = args.nomove
            argsobscureconfig = args.oc
            argsprogchar = args.pchar
            argsremoveallcomments = args.rak
            argsremovecomments = args.rk
            argsxy = args.xy
            fspeed = 3000
            pwidth = int(args.pwidth)

            # obscure configuration section, if parameter submitted:
            if argsobscureconfig:
                len_lines = len(lines)
                for line_index in range(len_lines):
                    # start from the back
                    strline = strline = lines[len_lines-line_index-1]
                    if strline == "; prusaslicer_config = begin\n":
                        break
                    if strline != "; prusaslicer_config = end\n":
                        strline = obscure_configuration(strline)

                    lines[len_lines-line_index-1] = strline

            # REMOVE configuration
            # del lines[len(lines)-ICOUNT:len(lines)]

            # Loop over GCODE file
            for i, strline in enumerate(lines):
                i_line_after_edit = 0

                #
                # PROGRESS-BAR in M117:
                rgxm117 = re.search(regex.findlayer, strline,
                                    flags=re.IGNORECASE)

                # if --prog was passed:
                if rgxm117 and argprogress:
                    current_layer = int(rgxm117.group(1))

                    # Create progress bar on printer's display
                    # Use a different char every 0.25% progress:
                    #   Edit progress_list to get finer progress
                    filled_length = int(
                        pwidth * current_layer // number_of_layers)
                    filled_lengt_half = float(
                        pwidth * current_layer / number_of_layers - filled_length)
                    strlcase = ""
                    p2width = pwidth

                    if current_layer == 0:
                        strlcase = "1st Layer"
                        p2width = len(strlcase)
                    elif current_layer / number_of_layers < 1:
                        # check for percentage and insert corresponding char from progress_list
                        for prog_thing in enumerate(progress_list):
                            if filled_lengt_half >= (prog_thing[1])[0]:
                                strlcase = (prog_thing[1])[1]
                                p2width = pwidth - 1
                            else:
                                break

                    # assemble the progressbar (M117)
                    strline = rf'M117 [{argsprogchar * filled_length + strlcase + "." * (p2width - filled_length)}];' + '\n'

                # if --prog was NOT passed
                elif rgxm117:
                    current_layer = int(rgxm117.group(1))
                    tmppercentage = f"{((current_layer / number_of_layers) * 100):#.3g}"
                    percentage = tmppercentage[:3] \
                        if tmppercentage.endswith('.') else tmppercentage[:4]

                    if current_layer == 0:
                        strline = str.format(
                            'M117 First Layer' + '\n')
                    else:
                        if argprogresslayer:
                            strline = str.format(
                                'M117 Layer {0} of {1}' + '\n', current_layer + 1, number_of_layers + 1)
                        else:
                            strline = str.format(
                                'M117 Layer {0}, {1}%' + '\n', current_layer + 1, percentage)

                if strline and first_layer_height == 0:
                    # if strline and b_found_z == False and b_skip_all == False:
                    # Find: ;Z:0.2 and store first layer height value
                    rgx1stlayer = re.search(
                        r"^;Z:(.*)", strline, flags=re.IGNORECASE)
                    if rgx1stlayer:
                        # Found ;Z:
                        first_layer_height = format_number(
                            Decimal(rgx1stlayer.group(1)))

                else:
                    if strline and first_layer_height != 0 and not b_skip_removed and not b_skip_all and not argsnocuramove:
                        # G1 Z.2 F7200 ; move to next layer (0)
                        # and replace with empty string
                        layerzero = re.search(
                            rf'^(?:G1)\s(?:(?:Z)([-+]?\d*(?:\.\d+)))\s(?:F({regex.findnumber})?)(?:.*layer \(0\).*)$', strline, flags=re.IGNORECASE)
                        if layerzero:
                            # Get the speed for moving to Z?
                            fspeed = format_number(Decimal(layerzero.group(2)))

                            # clear this line, I got no use for that one!
                            strline = ""

                            b_edited_line = True
                            b_skip_removed = True

                if args_info_numlayer:
                    # then, add info as soon as empty line is found.
                    # set b_start_add_custom_info = False
                    line = strline

                    if b_start_add_custom_info is False:
                        rgx_infoblock = re.search(
                            r'(?:^;\s)(?:.*)(extrusion width)', line, flags=re.IGNORECASE)

                        if rgx_infoblock:
                            if rgx_infoblock.group(1):
                                b_start_add_custom_info = True

                    else:
                        # add before first empty line
                        if line == '\n':
                            line = f'; total number of layers = {number_of_layers}\n'
                            line += '\n'

                            # reset, so it won't do it for the entire file
                            args_info_numlayer = False

                    strline = line

                if b_edited_line and not b_skip_all and not argsnocuramove:
                    line = strline

                    # Day after PS changes **** again!!!!
                    # G1 X92.706 Y96.155 ; move to first skirt point
                    m_c = re.search(
                        rf'^((G1\sX{regex.findnumber}\sY{regex.findnumber})\s.*(?:(move to first).*(?:point)))', strline, flags=re.IGNORECASE)
                    if m_c:
                        # In 2.4.0b1 something changed:
                        # It was:
                        # G1 E-6 F3000 ; retract
                        # G92 E0 ; reset extrusion distance
                        # G1 Z.2 F9000 ; move to next layer (0)
                        # G1 X92.706 Y96.155 ; move to first skirt point
                        # G1 E6 F3000 ;  ; unretract

                        # But needs to be this:
                        # G1 E-6 F3000 ; retract
                        # G92 E0 ; reset extrusion distance
                        # G0 F3600 Y50 ; avoid prime blob
                        # G0 X92.706 Y96.155 F3600; just XY
                        # G0 F3600 Z3 ; Then Z3 at normal speed
                        # G0 F1200 Z0.2 ; Then to first layer height at a third of previous speed
                        # G1 E6 F3000 ;  ; unretract

                        # Replace G1 with G0: Non extruding move
                        grp2 = m_c.group(2).replace('G1', 'G0')

                        if argsxy:
                            # add first line to move to XY only
                            line += f'{grp2} F{str(fspeed)}; just XY' + '\n'

                            # check height of FIRST_LAYER_HEIGHT
                            # to make ease-in a bit safer
                            scaled_layerheight = format_number(
                                Decimal(first_layer_height) * argseaseinfactor)

                            # Then ease-in a bit ... this always gave me a heart attack!
                            #   So, depending on first layer height, drop to 15 times (default)
                            #   first layer height in mm, ...
                            line += f'G0 F{str(fspeed)} Z{str(scaled_layerheight)} ; Then Z{str(scaled_layerheight)} at normal speed' + '\n'

                            #   then do the final Z-move at a third of the previous speed.
                            line += f'G0 F{str(format_number(float(fspeed)/3))} Z{str(first_layer_height)} ; ' \
                                'Then to first layer height at a third of previous speed\n'

                        else:
                            # Combined move to first skirt point.
                            # Prusa thinks driving through clips is no issue!
                            line += f'{grp2} Z{str(first_layer_height)} F{str(fspeed)} ; move to first skirt/support point\n'

                        b_edited_line = False
                        b_skip_all = True
                        b_start_remove_comments = True
                        i_line_after_edit = i + 1

                    strline = line

                if argscraftwaretypes:
                    if strline.startswith(";TYPE:"):
                        if 'Skirt/Brim' in strline:
                            strline = ';segType:Skirt\n;TYPE:Skirt/Brim\n'

                        elif 'Support material interface' in strline:
                            strline = ';segType:SoftSupport\n;TYPE:Support material interface\n'

                        elif 'Support material' in strline:
                            strline = ';segType:Support\n;TYPE:Support material\n'

                        elif ':Solid infill' in strline or 'Internal infill' in strline:
                            strline = ';segType:Infill\n;TYPE:Solid infill\n'

                        elif 'Gap fill' in strline:
                            strline = ';segType:Perimeter\n;TYPE:Gap fill\n'

                        elif 'External perimeter' in strline:
                            strline = ';segType:Perimeter\n;TYPE:External perimeter\n'

                        elif 'Perimeter' in strline:
                            strline = ';segType:Loop\n;TYPE:Perimeter\n'

                if (i + 1) > i_line_after_edit and argsremovecomments and b_start_remove_comments:
                    if strline.startswith("; prusaslicer_config"):
                        b_start_remove_comments = False
                    if (not strline.startswith(";") or strline.startswith(" ;")):
                        rgx = re.search(r'^[^;\s].*(\;)',
                                        strline, flags=re.IGNORECASE)
                        if rgx:
                            line = rgx.group(0)[:-1].strip()
                            strline = line + '\n'

                if argsremoveallcomments:
                    if (strline.startswith(";") or strline.startswith(" ;")):
                        strline = ""
                    else:
                        rgx = re.search(r'(.*)(?:;)', strline,
                                        flags=re.IGNORECASE)
                        if rgx:
                            line = rgx.group(0)[:-1].strip()
                            strline = line + '\n'
                        else:
                            strline = ""

                #
                # Write line back to file
                writefile.write(strline)

    except Exception as exc:
        print("Oops! Something went wrong. " + str(exc))
        sys.exit(1)

    finally:
        writefile.close()
        readfile.close()


# Write config file
def write_config_file(config):
    """
        Write Config File
    """

    with open(ppsc.configfile, 'w', encoding='UTF-8') as configfile:
        config.write(configfile)


# Reset counter
def reset_counter(conf, set_counter_to):
    """
        Reset Counter
    """
    if path.exists(ppsc.configfile):

        conf.set('DEFAULT', 'FileIncrement', str(set_counter_to))

        write_config_file(conf)


def format_number(num):
    """
        https://stackoverflow.com/a/5808014/827526
    """
    try:
        dec = Decimal(num)
    except decimal.DecimalException as ex:
        print(str(ex))
        # return f'Bad number. Not a decimal: {num}'
        return "nan"
    tup = dec.as_tuple()
    delta = len(tup.digits) + tup.exponent
    digits = ''.join(str(d) for d in tup.digits)
    if delta <= 0:
        zeros = abs(tup.exponent) - len(tup.digits)
        val = '0.' + ('0'*zeros) + digits
    else:
        val = digits[:delta] + ('0'*tup.exponent) + '.' + digits[delta:]
    val = val.rstrip('0')
    if val[-1] == '.':
        val = val[:-1]
    if tup.sign:
        return '-' + val
    return val


def get_int(notint):
    """
        Whatever to INT
    """
    xvalue = float(notint)
    yvalue = int(xvalue)
    zvalue = str(yvalue)
    return zvalue


def get_configuration(args):
    """
        GET/SET configuration
    """
    # check if config file exists; else create it with default 0

    conf = configparser.ConfigParser()
    if not path.exists(ppsc.configfile):

        conf.set('DEFAULT', 'FileIncrement', '0')
        conf.set('DEFAULT', 'CounterDigits', str(args.digits))

        write_config_file(conf)
    else:
        if args.setcounter is not None:
            reset_counter(conf, args.setcounter)

        conf.read(ppsc.configfile)
        ppsc.fileincrement = conf.getint(
            'DEFAULT', 'FileIncrement', fallback=0)

        if str(args.digits) != conf.getint('DEFAULT', 'CounterDigits', fallback=6):
            ppsc.counterdigits = args.digits
        else:
            ppsc.counterdigits = conf.getint(
                'DEFAULT', 'CounterDigits', fallback=6)


class REGEX():
    """
        Class for REGEX
    """

    def __init__(self):
        self.findnumber = r"-?\d*\.?\d+"
        self.findlayer = r"^M117 Layer (\d+)"


class PPSConfig(object):
    """
        Class instead of of global vars
    """

    def __init__(self):
        self.fileincrement = 0
        self.counterdigits = 0
        self.configfile = None


if __name__ == "__main__":
    ppsc = PPSConfig()
    regex = REGEX()

    # Config file full path; where _THIS_ file is
    ppsc.configfile = ntpath.join(
        f'{path.dirname(path.abspath(__file__))}', 'spp_config.cfg')

    ARGS = argumentparser()
    CONFIG = configparser.ConfigParser()

    main(ARGS, CONFIG)
