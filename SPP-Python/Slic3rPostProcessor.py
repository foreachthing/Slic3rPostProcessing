#!/usr/bin/python
""" Post Processing Script for Slic3r, PrusaSlicer and SuperSlicer.
    This will make the curent start behaviour more like Curas'.

    New:
    1. Heat up, down nozzle and ooze at your discretion.
    2. Move to the first entry point on XYZ simultaneously.

    Current:
    1. Heat up, down nozzle and ooze at your discretion.
    2. Lower nozzle to first layer height and then move to
       first entry point in only X and Y.
       (This gives me heart-attacks!!)
    
    Parameters:
    1. GCode file (required!)
    2. --xy to move to XY first, then drop to Z "first layer height"
    
"""

# Script based on:
# http://projects.ttlexceeded.com/3dprinting_prusaslicer_post-processing.html

# got issues?
# Please complain here: https://github.com/foreachthing/Slic3rPostProcessing/issues

import sys
import re
import argparse
from shutil import ReadError, copyfile
from os import path

def argumentparser():
    """ ArgumentParser """
    parser = argparse.ArgumentParser(
        prog=path.basename(__file__),
        description='** Slicer Post Processing Script ** \n' \
            'Do the Cura move, for us with an Ultimaker 2 or similar'\
            ' and/or clips on the build plate.'\
            ' Since the default PrusaSlicer code tends to move'\
            ' through them - ouch!',
        epilog='Result: Ultimaker 2 (and up) friedly start code.')

    parser.add_argument('input_gcode_file', action='store', type=str,\
    help='This is the GCode file to be processed - as last and required argument.')

    parser.add_argument('--xy', action='store_true', default=False, \
    help='If --xy is provided, the script tells the printer to move to X and Y first, '\
        'then drop the nozzle to Z at half the speed of XY.\n'\
        '(Default: %(default)s)')

    try:
        args = parser.parse_args()
        
        return args

    except IOError as msg:
        parser.error(str(msg))   


def main(args):
    """
        MAIN
    """
    #print(len(sys.argv))
    #print(args.input_gcode_file)
    
    sourcefile=args.input_gcode_file

    # Create a backup file
    try:
        copyfile(sourcefile, re.sub(r"\.gcode$",".gcode.bak", sourcefile, flags=re.IGNORECASE))
    except OSError as exc:
        print('FileNotFoundError:' + str(exc))
        sys.exit(1)

    # Read the ENTIRE g-code file into memory
    try:
        with open(sourcefile, "r") as readfile:
            lines = readfile.readlines()
    except ReadError as exc:
        print('FileReadError:' + str(exc))
        sys.exit(1)

    FIRST_LAYER_HEIGHT = 0
    B_FOUND_Z = False
    B_EDITED_LINE = False
    B_SKIP_ALL = False
    B_SKIP_REMOVED = False
    WRITEFILE = None
    RGX_FIND_NUMBER = r"-?\d*\.?\d+"

    try:
        with open(sourcefile, "w") as WRITEFILE:
            for lIndex in range(len(lines)):
                strline = lines[lIndex]

                if strline and B_FOUND_Z == False and B_SKIP_ALL == False:
                    # Find: ;HEIGHT:0.2 and store first layer height value
                    m = re.search(r"^;HEIGHT:(.*)", strline, flags=re.IGNORECASE)
                    if m:
                        # Found ;HEIGHT:
                        FIRST_LAYER_HEIGHT = m.group(1)
                        B_FOUND_Z = True

                else:
                    if strline and B_FOUND_Z and B_SKIP_REMOVED == False and B_SKIP_ALL == False:
                        # find:   G1 Z-HEIGHT F...
                        # result: ; G1 Z0.200 F7200.000 ; REMOVED by PostProcessing Script:
                        m = re.search(rf'^(?:G1)\s(?:Z{FIRST_LAYER_HEIGHT}.*)\s(?:F{RGX_FIND_NUMBER}?)(?:.*)$', strline, flags=re.IGNORECASE)
                        if m:
                            strline = re.sub(r'\n', '', strline, flags=re.IGNORECASE)
                            strline = '; ' + strline + ' ; REMOVED by PostProcessing Script:\n'
                            B_EDITED_LINE = True
                            B_SKIP_REMOVED = True

                if B_EDITED_LINE and B_SKIP_ALL == False:
                    # find:   G1 X85.745 Y76.083 F7200.000; fist "point" on Z-HEIGHT and add Z-HEIGHT
                    # result: G1 X85.745 Y76.083 Z0.2 F7200 ; added by PostProcessing Script
                    ln = strline
                    if args.xy:
                        mc = re.search(rf'^((G1\sX{RGX_FIND_NUMBER}\sY{RGX_FIND_NUMBER})\s.*(?:F({RGX_FIND_NUMBER})))', strline, flags=re.IGNORECASE)
                        if mc:
                            ln = mc.group(1) + ' ; just XY - added by PostProcessing Script\n'
                            
                            # check height of FIRST_LAYER_HEIGHT
                            # to make ease-in a bit safer
                            flh = float(FIRST_LAYER_HEIGHT) * 10
                            
                            # Then ease-in a bit ... this always gave me a heart attack!
                            #   So, depending on first layer height, drop to 10 times 
                            #   first layer height mm (this is hardcoded above),
                            ln = ln + 'G1' + ' Z' + str(flh) + ' F' + str(mc.group(3)) + ' ; Then Z' + str(flh) + ' at normal speed - added by PostProcessing Script\n'
                            #   then do the final Z-move at half the speed as before.
                            ln = ln + 'G1' + ' Z' + str(FIRST_LAYER_HEIGHT) + ' F' + str(float(mc.group(3))/2) + ' ; Then to firt layer height at half the speed - added by PostProcessing Script\n'
                            B_EDITED_LINE = False
                            B_SKIP_ALL = True
                                                
                    else:
                        mc = re.search(rf'^((G1\sX{RGX_FIND_NUMBER}\sY{RGX_FIND_NUMBER})\s.*(F{RGX_FIND_NUMBER}))', strline, flags=re.IGNORECASE)
                        if mc:
                            ln = mc.group(2) + ' Z' + str(FIRST_LAYER_HEIGHT) + ' ' + mc.group(3) + ' ; added Z' + str(FIRST_LAYER_HEIGHT) + ' by PostProcessing Script\n'
                            B_EDITED_LINE = False
                            B_SKIP_ALL = True
                    strline = ln

                # Write line back to file
                WRITEFILE.write(strline)

    except Exception as exc:
        print("Oops! Something went wrong." + str(exc))
        sys.exit(1)

    finally:
        WRITEFILE.close()
        readfile.close()
        print('All done.')


ARGS = argumentparser()
main(ARGS)
