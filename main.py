# /usr/bin/python3
""" Post Processing Script for Slic3r, PrusaSlicer and SuperSlicer.
    This will make the curent start behaviour more like Curas'.

    A word of waring:
    # USE THIS POST-PROCESSING SCRIPT AT YOUR OWN RISK! #
    Lots of features have been tested in production. Some didn't.
    Some features might lead to crashes of the nozzle and could harm your printer.
    Always check the G-Code before printing.


    TODO: Line ;WIDTH:0.388362
            G1 X138.903 Y97.76 E9.23279 ; infill
    should be merged into one. ArcWelder cannot find points.
    One solution: add "G-Code Substitution" in PrusaSlicer ->
        Find: ^((?:;WIDTH:).*)$ -> Replace with [EMPTY] -> REGEX checked

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
    - use with non PrusaSlicer Slicer (Prusa uses a temp file first, others don't)
    - Add sort-of progressbar as M117 command
    - Option to disable Cura-move with '--nomove' parameter
    - Option for coloring output to be viewed in CraftWare
    - Option to add total number of layers to slice-info block
    - OrcaSlicer: Option to export GCode to be viewed in PrusaSlicer GCode-Viewer.

    Individual objects -- CAUTIOIN!! STILL NEEDS TESTING
    - Print individual objects in blocks of x mm.
    - Print first layer of all the individual objects first

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

    Requirements:
    - in "Custom G-Code" -> "Before Layer Change G-Code", this line is required:
      ;layer:[layer_num]

"""

# Script based on:
# http://projects.ttlexceeded.com/3dprinting_prusaslicer_post-processing.html

# got issues?
# Please complain/explain here: https://github.com/foreachthing/Slic3rPostProcessing/issues

#
# "cheat" pylint, because it can be annoying
# pylint: disable = line-too-long, broad-except, missing-function-docstring
# noqa: E501
#


import sys
import argparse
import configparser
import ntpath
import subprocess
from shutil import copy2
from os import path, remove, getenv
from utils import individual_objects
from utils import post_processing
from utils import post_classes


def install(package):
    """ Install Package with PIP
        But, first check for PIP-updates.
    Args:
        package (string): Name of Package
    """
    if package == "pip":
        #  pip install --upgrade pip
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", package])
    else:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package])


try:
    import pymsgbox
    # import progressbar
except ImportError:
    install("pip")
    install("pymsgbox")
    # install("progressbar2")
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
        ppsc.filecounter = conf.getint(
            'DEFAULT', 'filecounter', fallback=0)
        ppsc.counterdigits = conf.getint(
            'DEFAULT', 'CounterDigits', fallback=6)
        ppsc.iobh = conf.getfloat(
            'IndividualObjects', 'BlockHeight', fallback=9999.0)

    ##

    parser.add_argument('input_file', metavar='gcode-files', type=str, nargs='+',
                        help='One or more GCode file(s) to be processed '
                        '- at least one is required.')

    parser.add_argument('-b', '--backup', action='store_true', default=False,
                        help='Create a backup file, if True is passed. '
                        '(Default: %(default)s)')

    # "Other"-Slicers stuff
    parser.add_argument('-t', '--usetempfile', action='store_true', default=False,
                        help='Pass argument for any other slicer (based on Slic3r) than '
                        'PrusaSlicer. This is for handling the temp-file and then '
                        'replace the original file.')
    # choose slicer
    parser.add_argument('--slicer', choices=list(post_classes.SlicersArgParse), type=post_classes.SlicersArgParse.argparse, default="prusa",
                        help='Pass string, if you\'re not using PrusaSlicer. Default: prusa.')

    parser.add_argument('-cwt', '--craftwaretypes', action='store_true', default=False,
                        help='Pass argument if you want to view GCode in Craftware.')
    parser.add_argument('-ost', '--orcaslicertypes', action='store_true', default=False,
                        help='Create comments, for OcrcaSlicer to be viewed in PrusaSlicer Viewer.')

    grp_info = parser.add_argument_group('Slicer Info')
    grp_info.add_argument('-n', '--numlayer', action='store_true', default=False,
                          help='Adds total number of layers to slice-info of G-Code file.')

    # Individual Object Settings
    grp_individuals = parser.add_argument_group('Individual Objects Settings')
    grp_individuals.add_argument('--iob', action='store_true', default=False,
                                 help='If provided, individual objects will be printed in blocks. '
                                 '(Default: %(default)s)')
    grp_individuals.add_argument('--iobh', action='store', metavar='float', type=float, default=ppsc.iobh,
                                 help='Prints indivdual objects in blocks of this height. '
                                 '  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  '
                                 ' ### THIS IS VERY, VERY EXPERIMENTAL!! USE IT WITH CAUTION!!!'
                                 'Always check your GCode before sending it to the printer!!! ### You could damage your printer !!!'
                                 '  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  '
                                 'This is, or might be in the future, useful if your nozzle has a clearance, of i.e. 4 mm, to '
                                 'the shroud. That way you can print 4 mm of each object and then move on. '
                                 'Keep in mind: Objects will be sorted from shortest to talles, no matter what. '
                                 'Note: Value has same unit as layer height does. '
                                 'Default: %(default)s. This setting is stored in spp_config.cfg.')
    grp_individuals.add_argument('--iobfl', action='store_true', default=False,
                                 help='If --iobfl is provided, the first layer of all objects will '
                                 'be printet at the same time. If _only_ the first layer shall '
                                 'be printed first, set -iobh=9999 or something taller than your build plate. '
                                 '(Default: %(default)s)')

    # the CURA Move
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

    # Remove Comments
    comment_x_group = parser.add_mutually_exclusive_group()
    comment_x_group.add_argument('--oc', action='store_true', default=False,
                                 help='Warning! Use at own risk - does not produce valid PrusaSlicer-GCode.\n'
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

    start_counter = "0" * int(ppsc.counterdigits-1)
    end_counter = "9" * int(ppsc.counterdigits)

    # Counter
    grp_counter = parser.add_argument_group('Counter settings')
    grp_counter.add_argument('-f', '--filecounter', action='store_true', default=False,
                             help='Add a prefix counter, if desired, to the output gcode file. '
                             f'Counter length is set to {ppsc.counterdigits} digits ({start_counter}1-{end_counter}_filename.gcode). '
                             '(Default: %(default)s). This setting is stored in spp_config.cfg.')

    grp_counter.add_argument('--rev', action='store_true', default=False,
                             help='If passed, adds counter in reverse, down to zero and it will restart '
                             f'at {end_counter}. '
                             '(Default: %(default)s)')

    grp_counter.add_argument('--setcounter', action='store', metavar='int', type=int,
                             help='Reset counter to this [int]. Or edit spp_config.cfg directly. '
                             'Can also be done manually in the spp_config.cfg file.')

    grp_counter.add_argument('--digits', action='store', metavar='int', type=int, default=ppsc.counterdigits,
                             help='Number of digits for counter. '
                             '(Default: %(default)s). This setting is stored in spp_config.cfg.')

    grp_counter.add_argument('-e', '--easeinfactor', action='store', metavar='int', type=int, default=15,
                             help='Scale Factor for ease in on Z. Z moves fast to this point then slows down. '
                             'Scales the first layer height by this factor. '
                             '(Default: %(default)s)')

    # Progress Bar
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
    # sys.exit(0)


def coords(x_y):
    """Processes XY Coordinates for parking

    Args:
        xy (tuple): xy coordinates

    Raises:
        argparse.ArgumentTypeError: _description_

    Returns:
        _type_: _description_
    """
    try:
        _x, _y = map(int, x_y.split(','))
        return _x, _y
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
                ppsc.filecounter -= 1
                if ppsc.filecounter < 0:
                    ppsc.filecounter = (10 ** ppsc.counterdigits) - 1
            else:
                ppsc.filecounter += 1
                if ppsc.filecounter >= (10 ** ppsc.counterdigits) - 1:
                    ppsc.filecounter = 0

            # Create a backup file, if the user wants it.
            try:
                # if user wants a backup file ...
                if args.backup is True:

                    sourcefile_bak = sourcefile.lower().replace(".gcode", ".gcode.bak")

                    copy2(sourcefile, sourcefile_bak)

            except OSError as exc:
                print('FileNotFoundError (backup file):' + str(exc))
                sys.exit(1)

            #
            #
            # #
            # # # #

            # Read the ENTIRE GCode file into memory, once.
            try:
                with open(sourcefile, "r", encoding='UTF-8') as readfile:
                    lines = readfile.readlines()
            except EnvironmentError as exc:
                print('FileReadError:' + str(exc))
                sys.exit(1)

            # Individual Object Treatment
            if args.iob:
                lines = individual_objects.process_split_by_block(
                    lines, int(args.slicer), args.iobh, args.iobfl)

            # "Regular" Post-Processing
            post_processing.process_gcodefile(
                args, sourcefile, lines, args.slicer)

            # # # #
            # #
            #
            #

            destfile = sourcefile
            if args.filecounter:

                # Create Counter String, zero-padded accordingly
                counter = str(ppsc.filecounter).zfill(ppsc.counterdigits)

                # if using a temp file, before writing back to SD, go here:
                if args.usetempfile is True:

                    # get envvar from PrusaSlicer
                    env_slicer_pp_output_name = str(
                        getenv('SLIC3R_PP_OUTPUT_NAME'))

                    # create file for PrusaSlicer with correct name as content
                    with open(sourcefile + '.output_name', mode='w', encoding='UTF-8') as fopen:
                        fopen.write(counter + '_' +
                                    ntpath.basename(env_slicer_pp_output_name))

                # saving directly to media:
                else:
                    # NOT PrusaSlicer:
                    destfile = ntpath.join(ntpath.dirname(
                        sourcefile), counter + '_' + ntpath.basename(sourcefile))

                    copy2(sourcefile, destfile)

                    remove(sourcefile)

            #
            # write settings back
            conf.set('DEFAULT', 'filecounter', str(ppsc.filecounter))
            conf.set('DEFAULT', 'CounterDigits', str(ppsc.counterdigits))

            conf.add_section('IndividualObjects')
            conf.set('IndividualObjects', 'BlockHeight', str(ppsc.iobh))

            write_config_file(conf)


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
        conf.set('DEFAULT', 'filecounter', str(set_counter_to))
        write_config_file(conf)


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

        conf.set('DEFAULT', 'filecounter', '0')
        conf.set('DEFAULT', 'CounterDigits', '6')

        conf.add_section('IndividualObjects')
        conf.set('IndividualObjects', 'BlockHeight', str(1.0))

        write_config_file(conf)
    else:
        if args.setcounter is not None:
            reset_counter(conf, args.setcounter)
        conf.read(ppsc.configfile)

        # configuration vars
        if not conf.has_section('IndividualObjects'):
            conf.add_section('IndividualObjects')

        if args.iobh is not None:
            ppsc.iobh = args.iobh
        else:
            ppsc.iobh = conf.getfloat(
                'IndividualObjects', 'BlockHeight', fallback=1.0)

        ppsc.filecounter = conf.getint(
            'DEFAULT', 'filecounter', fallback=0)

        if str(args.digits) != conf.getint('DEFAULT', 'CounterDigits', fallback=6):
            ppsc.counterdigits = args.digits
        else:
            ppsc.counterdigits = conf.getint(
                'DEFAULT', 'CounterDigits', fallback=6)


if __name__ == "__main__":

    ppsc = post_classes.PPSConfig()

    # Config file full path; where _THIS_ file is
    ppsc.configfile = ntpath.join(
        f'{path.dirname(path.abspath(__file__))}', 'spp_config.cfg')

    ARGS = argumentparser()
    CONFIG = configparser.ConfigParser()

    main(ARGS, CONFIG)
