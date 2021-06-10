#!/usr/bin/python
""" Post Processing Script for Slic3r, PrusaSlicer and SuperSlicer.
    This will make the curent start behaviour more like Curas'.

    New behaviour:
    - Heat up, down nozzle and ooze at your discretion.
    - Move to the first entry point on XYZ simultaneously.
    - Or, move to the first entry point on XY first, then Z!

    Current behaviour:
    1. Heat up, down nozzle and ooze at your discretion.
    2. Lower nozzle to first layer height and then move to
       first entry point in only X and Y.
       (This move can and will collide with the clips on the Ultimaker 2!)
    
"""

# Script based on:
# http://projects.ttlexceeded.com/3dprinting_prusaslicer_post-processing.html

# got issues?
# Please complain/explain here: https://github.com/foreachthing/Slic3rPostProcessing/issues

import sys
import re
import argparse
import configparser
import time
import ntpath
from shutil import ReadError, copy2
from os import path, remove
from decimal import Decimal
from datetime import datetime

# datetime object containing current date and time
NOW = datetime.now()
DEBUG = True

def debugprint(s):
    if DEBUG:
        print(f"{NOW.strftime('%Y-%m-%d %H:%M:%S')}: {str(s)}")
        time.sleep(5)

def argumentparser():
    """ ArgumentParser """
    parser = argparse.ArgumentParser(
        prog=path.basename(__file__),
        description='** Slicer Post Processing Script ** \n\r' \
            'Do the Cura move, for us with an Ultimaker 2 or similar'\
            ' and/or clips on the build plate.'\
            ' Since the default PrusaSlicer code tends to move'\
            ' right through them - ouch!',
        epilog = 'Result: An Ultimaker 2 (and up) friedly GCode file.')

    parser.add_argument('input_file', metavar='gcode-files', type=str, nargs='+',\
        help='One or more GCode file(s) to be processed - at least one is required.')

    parser.add_argument('--xy', action='store_true', default=False, \
        help='If --xy is provided, the script tells the printer to move to '\
            'X and Y of first start point, then drop the nozzle to Z at half '\
            'the normal speed. '\
            '(Default: %(default)s)')
    
    parser.add_argument('--rc', action='store_true', default=False, \
        help='Removes Configuration/Comments at end of file. '\
            '(Default: %(default)s)')
    
    parser.add_argument('--noback', action='store_true', default=False, \
        help='Don\'t create a backup file, if parameter is passed. '\
            '(Default: %(default)s)')

    parser.add_argument('--filecounter', action='store_true', default=False, \
        help='Add a prefix counter, if desired, to the output gcode file. '\
            'Default counter length is 6 digits (000001-999999_file.gcode). '\
            'The counter, however, DOES NOT work with PrusaSlicer! '\
            'It does work with SuperSlicer and Slic3r. '\
            '(Default: %(default)s)')

    grp_progress = parser.add_argument_group('Progress bar settings')
    grp_progress.add_argument('--p', action='store_true', default=False, \
        help='If --p is provided, a progress bar instead of layer number/percentage, '\
            'will be added to your GCode file and displayed on your printer (M117). '\
            '(Default: %(default)s)')

    grp_progress.add_argument('-pwidth', metavar='int', type=int, default=18, \
        help='Define the progress bar length in characters. You might need to '\
            'adjust the default value. Allow two more chars for brackets. '\
            'Example: [' + 'OOOOO'.ljust(18, '.') + ']. (Default: %(default)d)')

    try:
        args = parser.parse_args()
        return args

    except IOError as msg:
        parser.error(str(msg))
    

def main(args, conf):
    """
        MAIN
    """
    conf = configparser.ConfigParser()
    conf.read('spp_config.cfg')
    fileincrement = conf.getint('DEFAULT', 'FileIncrement', fallback=0)
    
    for sourcefile in args.input_file:
        
        if path.exists(sourcefile):        
            # file increment + 1
            fileincrement += 1
            
            # Create a backup file, if the user wants it.
            try:
                if args.noback == False:
                    copy2(sourcefile, re.sub(r"\.gcode$", ".gcode.bak", sourcefile, flags=re.IGNORECASE))
            except OSError as exc:
                print('FileNotFoundError:' + str(exc))
                sys.exit(1)
            
            debugprint(f"Working on {sourcefile}")
            process_gcodefile(args, sourcefile)
            
            # copy sourcefile to new file with counter
            # and remove old sourcefile.
            destfile = sourcefile
            if args.filecounter:
                counter = ("{:06d}".format(fileincrement))
                destfile = ntpath.join(ntpath.dirname(sourcefile)  , counter + '_' + ntpath.basename(sourcefile))         
                
                copy2(sourcefile, destfile)
                remove(sourcefile)
                sourcefile = destfile
            
            #
            # write settings back
            conf['DEFAULT'] = {'FileIncrement': fileincrement}
            with open('spp_config.cfg', 'w') as configfile:
                conf.write(configfile)
        
            debugprint(f'File {sourcefile} done.')
    
    


def process_gcodefile(args, sourcefile):
    """
        MAIN Processing.
        To do with ever file from command line.
    """

    # Read the ENTIRE GCode file into memory
    try:
        with open(sourcefile, "r") as readfile:
            lines = readfile.readlines()
    except ReadError as exc:
        print('FileReadError:' + str(exc))
        sys.exit(1)
        
    #
    # Define list of progressbar percentage and characters
    PROGRESS_LIST = [[0, "."], [.25, ":"], [.5, "+"], [.75, "#"]]
    # PROGRESS_LIST = [[.5, "o"]]
    # PROGRESS_LIST = [[0, "0"], [.2, "2"], [.4, "4"], [.6, "6"], [.8, "8"]]
    #

    RGX_FIND_LAYER = r"^M117 Layer (\d+)"
    RGX_FIND_NUMBER = r"-?\d*\.?\d+"
    FIRST_LAYER_HEIGHT = 0
    B_FOUND_Z = False
    B_EDITED_LINE = False
    B_SKIP_ALL = False
    B_SKIP_REMOVED = False
    WRITEFILE = None
    NUM_OF_LAYERS = 0
    CURR_LAYER = 0
    IS_COMMENT = True
    ICOUNT = 0
    
    try:
        # Find total layers - search from back of file until
        #   first "M117 Layer [num]" is found.
        # Store total number of layers.
        # Also, measure configuration section length.
        len_lines = len(lines)
        for lIndex in range(len_lines):
            # start from the back
            strline = lines[len_lines-lIndex-1]
            
            if IS_COMMENT == True:
                if strline.startswith('; '):
                    # Count number of lines of the configuration section                    
                    ICOUNT += 1
                    continue
                # find first empty line before configuration section
                elif strline == "\n":
                    IS_COMMENT = False
            
            # Find last Layer:            
            rgxm117 = re.search(RGX_FIND_LAYER, strline, flags=re.IGNORECASE)
            if rgxm117:
                # Found M117 Layer xy
                NUM_OF_LAYERS = int(rgxm117.group(1))
                break
    except Exception as exc:
        print("Oops! Something went wrong in finding total numbers of layers. " + str(exc))
        sys.exit(1)


    try:
            
        with open(sourcefile, "w") as WRITEFILE:
            
            # Store args in vars
            pwidth = int(args.pwidth)
            
            # Progressbar Character
            pchar = "O"
            
            # remove configuration section, if parameter submitted:
            if args.rc:
                del lines[len(lines)-ICOUNT:len(lines)]
                if DEBUG:
                    debugprint('Removed Config Section; a total of {ICOUNT} lines.')

            if DEBUG:
                appendstring = 'by PostProcessing Script'
            else:
                appendstring = ''

            # Loop over GCODE file
            for lIndex in range(len(lines)):
                strline = lines[lIndex]
                
                #
                # PROGRESS-BAR in M117:
                rgxm117 = re.search(RGX_FIND_LAYER, strline, flags=re.IGNORECASE)
                if rgxm117:
                    CURR_LAYER = int(rgxm117.group(1))
                                        
                    if args.p:
                        # Create progress bar on printer's display
                        # Use a different char every 0.25% progress:
                        #   Edit PROGRESS_LIST to get finer progress
                        filledLength = int(pwidth * CURR_LAYER // NUM_OF_LAYERS)
                        filledLengthHALF = float(pwidth * CURR_LAYER / NUM_OF_LAYERS - filledLength)
                        strlcase = ""
                        p2width = pwidth

                        if CURR_LAYER / NUM_OF_LAYERS < 1:
                            # check for percentage and insert corresponding char from PROGRESS_LIST
                            for i in range(len(PROGRESS_LIST)):                                
                                if filledLengthHALF >= PROGRESS_LIST[i][0]:
                                    strlcase = PROGRESS_LIST[i][1]
                                    p2width = pwidth - 1
                                else:
                                    break
                                                            
                            if CURR_LAYER == 0:
                                strlcase = "1st Layer"
                                p2width = 9
                                    
                        # assemble the progressbar (M117)
                        strline = rf'M117 [{pchar * filledLength + strlcase + "." * (p2width - filledLength)}];' + '\n'
                    else:
                        tmppercentage = "{:#.3g}".format((CURR_LAYER / NUM_OF_LAYERS) * 100)
                        percentage = tmppercentage[:3] if tmppercentage.endswith('.') else tmppercentage[:4]
                        strline = rf'M117 Layer {CURR_LAYER}, {percentage} %;' + '\n'
                
                if strline and B_FOUND_Z == False and B_SKIP_ALL == False:
                    # Find: ;HEIGHT:0.2 and store first layer height value
                    rgx1stlayer = re.search(r"^;HEIGHT:(.*)", strline, flags=re.IGNORECASE)
                    if rgx1stlayer:
                        # Found ;HEIGHT:
                        FIRST_LAYER_HEIGHT = format_number(Decimal(rgx1stlayer.group(1)))      
                        B_FOUND_Z = True
                else:
                    if strline and B_FOUND_Z and B_SKIP_REMOVED == False and B_SKIP_ALL == False:
                        # find:    G1 Z-HEIGHT F...
                        # result:  ; G1 Z0.200 F7200.000 ; REMOVED by PostProcessing Script:
                        if re.search(rf'^(?:G1)\s(?:Z{str(FIRST_LAYER_HEIGHT)}.*)\s(?:F{RGX_FIND_NUMBER}?)(?:.*)$', strline, flags=re.IGNORECASE):
                            strline = re.sub(r'\n', '', strline, flags=re.IGNORECASE)
                            strline = f'; {strline} ; REMOVED {appendstring}:\n'
                            B_EDITED_LINE = True
                            B_SKIP_REMOVED = True

                if B_EDITED_LINE and B_SKIP_ALL == False:
                    # find:   G1 X85.745 Y76.083 F7200.000; fist "point" on Z-HEIGHT and add Z-HEIGHT
                    # result: G1 X85.745 Y76.083 Z0.2 F7200 ; added by PostProcessing Script
                    line = strline
                    mc = re.search(rf'^((G1\sX{RGX_FIND_NUMBER}\sY{RGX_FIND_NUMBER})\s.*(?:F({RGX_FIND_NUMBER})))', strline, flags=re.IGNORECASE)
                    if mc:   
                        # get F-value and format it like a human would
                        fspeed = format_number(Decimal(mc.group(3)))
                    
                        if args.xy:
                            # add first line to move to XY only
                            line = f'{mc.group(2)} F{str(fspeed)}; just XY - added {appendstring}\n'                           

                            # check height of FIRST_LAYER_HEIGHT
                            # to make ease-in a bit safer
                            flh = format_number(Decimal(FIRST_LAYER_HEIGHT) * 15)

                            # Then ease-in a bit ... this always gave me a heart attack!
                            #   So, depending on first layer height, drop to 15 times 
                            #   first layer height in mm (this is hardcoded above),                         
                            line = f'{line}G1 Z{str(flh)} F{str(fspeed)}; Then Z{str(flh)} at normal speed - added {appendstring}\n'

                            #   then do the final Z-move at half the speed as before.
                            line = f'{line}G1 Z{str(FIRST_LAYER_HEIGHT)} F{str(format_number(float(fspeed)/2))}; Then to first layer height at half the speed - added {appendstring}\n'

                            B_EDITED_LINE = False
                            B_SKIP_ALL = True

                        else:
                            line = f'{mc.group(2)} Z{str(FIRST_LAYER_HEIGHT)} F{str(fspeed)} ; added Z {str(FIRST_LAYER_HEIGHT)} {appendstring}\n'

                            B_EDITED_LINE = False
                            B_SKIP_ALL = True
                    strline = line

                #
                # Write line back to file
                WRITEFILE.write(strline)

    except Exception as exc:
        print("Oops! Something went wrong. " + str(exc))
        sys.exit(1)

    finally:
        WRITEFILE.close()
        readfile.close()


def format_number(num):
    """
        https://stackoverflow.com/a/5808014/827526
    """
    try:
        dec = Decimal(num)
    except:
        return f'Bad number. Not a decimal: {num}'
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


ARGS = argumentparser()
CONFIG = configparser.ConfigParser()

main(ARGS, CONFIG)
