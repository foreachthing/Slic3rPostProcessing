#/usr/bin/python3
""" Post Processing Script for Slic3r, PrusaSlicer and SuperSlicer.
    This will make the curent start behaviour more like Curas'.

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

    Current behaviour:
    1. Heat up, down nozzle and ooze at your discretion.
    2. Lower nozzle to first layer height and then move to
       first entry point in only X and Y.
       (This move can and will collide with the clips on the Ultimaker 2!)

"C:/Program Files/Python39/python.exe" "c:/dev/Slic3rPostProcessing/SPP-Python/Slic3rPostProcessor.py" --xy --noback --rk --filecounter;
    
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
import random
from posixpath import split
from shutil import ReadError, copy2
from os import path, remove, getenv
from decimal import Decimal
from datetime import datetime

# datetime object containing current date and time
NOW = datetime.now()
DEBUG = False

# Global Regex
RGX_FIND_NUMBER = r"-?\d*\.?\d+"

# Config file full path; where _THIS_ file is
config_file = ntpath.join(f'{path.dirname(path.abspath(__file__))}', 'spp_config.cfg')


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
    
    parser.add_argument('--notprusaslicer', action='store_true', default=False, \
        help='Set to False for any other slicer (based on Slic3r) than PrusaSlicer.' \
            'Leave default (%(default)s) if you\'re using PrusaSlicer.')

    parser.add_argument('--xy', action='store_true', default=False, \
        help='If --xy is provided, the script tells the printer to move to '\
            'X and Y of first start point, then drop the nozzle to Z at a third '\
            'the normal speed. '\
            '(Default: %(default)s)')
    
    parser.add_argument('--oc', action='store_true', default=False, \
        help='WIP! Use at own risk - does not yet produce valid PS-gcode.\n' \
            'Obscures Configuration at end of file with bogus values. '\
            '(Default: %(default)s)')
            
    parser.add_argument('--rk', action='store_true', default=False, \
        help='Removes comments from end of line, except Configuration and pure comments. '\
            '(Default: %(default)s)')
    
    parser.add_argument('--rak', action='store_true', default=False, \
        help='Removes all comments! Note: PrusaSlicers GCode preview might not render file correctly. '\
            '(Default: %(default)s)')
    
    parser.add_argument('--noback', action='store_true', default=False, \
        help='Don\'t create a backup file, if parameter is passed. '\
            '(Default: %(default)s)')

    grp_counter = parser.add_argument_group('Counter settings')
    grp_counter.add_argument('--filecounter', action='store_true', default=False, \
        help='Add a prefix counter, if desired, to the output gcode file. '\
            'Default counter length is 6 digits (000001-999999_file.gcode). '\
            '(Default: %(default)s)')
    
    grp_counter.add_argument('-rev', action='store_true', default=False, \
        help='If True, adds counter in reverse, down to zero and it will restart '\
            'at 999999 if -setcounter was not specified otherwise.' \
            '(Default: %(default)s)')
    
    grp_counter.add_argument('-setcounter', action='store', metavar='int', type=int, \
        help='Reset counter to this [int]. Or edit spp_config.cfg directly.')
    
    grp_counter.add_argument('-digits', action='store', metavar='int', type=int, default=6, \
        help='Number of digits for counter.' \
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
    
    grp_progress.add_argument('-pchar', metavar='str', type=str, default="O", \
        help='Set progress bar character. '\
            '(Default: %(default)d)')

    try:
        args = parser.parse_args()
        return args

    except IOError as msg:
        parser.error(str(msg))


def main(args, conf):
    """
        MAIN
    """
    
    # check if config file exists; else create it with default 0
    conf = configparser.ConfigParser()
    if not path.exists(config_file):
        conf['DEFAULT'] = {'FileIncrement': 0}
        write_file(conf)
    else:
        if args.setcounter is not None:
            resetCounter(conf, args.setcounter)
            
        conf.read(config_file)
        fileincrement = conf.getint('DEFAULT', 'FileIncrement', fallback=0)
    
    for sourcefile in args.input_file:
        
        # Count up or down
        if path.exists(sourcefile):        
            # counter increment
            if args.rev:
                fileincrement -= 1
                if fileincrement < 0:
                    fileincrement = (10 ** args.digits) - 1
            else:
                fileincrement += 1
                if fileincrement >= (10 ** args.digits) - 1:
                    fileincrement = 0

            # Create a backup file, if the user wants it.
            try:
                if args.noback == False:
                    copy2(sourcefile, re.sub(r"\.gcode$", ".gcode.bak", sourcefile, flags=re.IGNORECASE))
            except OSError as exc:
                print('FileNotFoundError:' + str(exc))
                sys.exit(1)

            #
            #
            #
            debugprint(f"Working on {sourcefile}")
            process_gcodefile(args, sourcefile)

            #
            #
            #
            destfile = sourcefile
            if args.filecounter:
                
                # Create Counter String, zero-padded accordingly
                counter = str(fileincrement).zfill(args.digits)
                
                if args.notprusaslicer == False:
                                        
                    # get envvar from PrusaSlicer
                    env_slicer_pp_output_name = str(getenv('SLIC3R_PP_OUTPUT_NAME'))
                    
                    # create file for PrusaSlicer with correct name as content
                    f = open(sourcefile + '.output_name', mode='w')
                    f.write(counter + '_' + ntpath.basename(env_slicer_pp_output_name))
                    f.close()
                    
                    if DEBUG:
                        debugprint("# # # # -filecounter-")
                        debugprint("\tSLIC3R_PP_OUTPUT_NAME:\t" + env_slicer_pp_output_name )
                        debugprint("\tTemp file: " + sourcefile + '.output_name')
                        debugprint("\t\tContent :"+ counter + '_' + ntpath.basename(env_slicer_pp_output_name))

                else:
                    # NOT PrusaSlicer:
                    destfile = ntpath.join(ntpath.dirname(sourcefile)  , counter + '_' + ntpath.basename(sourcefile))         

                    copy2(sourcefile, destfile)
                    remove(sourcefile)
            
            #
            # write settings back
            conf['DEFAULT'] = {'FileIncrement': fileincrement}
            write_file(conf)
        
            debugprint(f'File {destfile} done.')


def obscure_configuration(line, oscurechar):
    """
        Obscure all settings
    """
    
    return_line_if = ["colour = #", "ramming", "gcode_flavor", "machine_limits_usage", "support_material_style", "printer_technology"]
    
    for retline in return_line_if:
        if line.__contains__(retline):
            return line

    line = re.sub(RGX_FIND_NUMBER, "0", line, 0, re.IGNORECASE|re.MULTILINE)
    
    key = line.split('=')[0].strip()
    value = line.split('=')[1].strip()

    try:
        float(value)
        if key.__contains__("speed"):
            value = str(random.randint(1, 255))
        elif key.__contains__("width"):
            value = str(round(random.random(), 2))
        elif key.__contains__("variable_layer_height"):
            value = "1"
        elif key.__contains__("height"):
            value = str(round(random.randint(15, 100) / 100, 2))
    except ValueError:
        # valueisfloat = False
        
        if key.__contains__("top_fill_pattern" or "bottom_fill_pattern"):
            value = "monotonic"
        elif key.__contains__("fill_pattern"):
            value = "stars"
        elif key.__contains__("support_material_pattern"):
            value = "rectilinear"
        elif key.__contains__("support_material_interface_pattern"):
            value = "auto"
        elif key.__contains__("slicing_mode"):
            value = "regular"
        elif key.__contains__("seam_position"):
            value = "aligned"
        elif key.__contains__("ironing_type"):
            value = "top"
        elif key.__contains__("host_type"):
            value = "octoprint"
        elif key.__contains__("fuzzy_skin"):
            value = "none"
        elif key.__contains__("draft_shield"):
            value = "disabled"
        elif key.__contains__("brim_type"):
            value = "outer_only"
        elif key.__contains__("pattern"):
            value = "Rectilinear"


        else:
            if value == "end":
                value = "end"
            elif value == "begin":
                value = "begin"
            elif value.endswith("%"):
                value = str(random.randint(1, 99)) + "%"
            elif value == "0,0":
                value = "0,0"
            else:
                value = "" #"\"\""

    return key  + " = " + value + "\n"

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
    progress_list = [[0, "."], [.25, ":"], [.5, "+"], [.75, "#"]]
    # progress_list = [[.5, "o"]]
    # progress_list = [[0, "0"], [.2, "2"], [.4, "4"], [.6, "6"], [.8, "8"]]
    #

    RGX_FIND_LAYER = r"^M117 Layer (\d+)"
    FIRST_LAYER_HEIGHT = 0
    B_FOUND_Z = False
    B_EDITED_LINE = False
    B_SKIP_ALL = False
    B_SKIP_REMOVED = False
    B_START_REMOVE_COMMENTS = False
    WRITEFILE = None
    NUM_OF_LAYERS = 0
    CURR_LAYER = 0
    IS_CONFIG_COMMENT = True
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
            
            if IS_CONFIG_COMMENT == True:
                # Count number of lines of the configuration section
                ICOUNT += 1
                # find beginning of configuration section
                if strline == "; prusaslicer_config = begin\n":
                    IS_CONFIG_COMMENT = False
            
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
        with open(sourcefile, "w",  newline='\n') as WRITEFILE:
            
            # Store args in vars - easier to type, or change, add...
            pwidth = int(args.pwidth)
            argsxy = args.xy
            argsobscureconfig = args.oc
            argprogress = args.p
            argsremovecomments = args.rk
            argsremoveallcomments = args.rak
            argsprogchar = args.pchar            
            
            # obscure configuration section, if parameter submitted:
            if argsobscureconfig:
                len_lines = len(lines)
                for lIndex in range(len_lines):
                    # start from the back
                    strline = strline = lines[len_lines-lIndex-1]
                    if strline == "; prusaslicer_config = begin\n":
                        break
                    if strline != "; prusaslicer_config = end\n":
                        strline = obscure_configuration(strline, "0")
                    
                    lines[len_lines-lIndex-1] = strline
                
            # REMOVE configuration
            # del lines[len(lines)-ICOUNT:len(lines)]
            # if DEBUG:
            #     debugprint('Removed Config Section; a total of {ICOUNT} lines.')

            if DEBUG:
                appendstring = 'edited by PostProcessing Script'
            else:
                appendstring = ''

            i_current_line = 0
            
            # Loop over GCODE file
            for lIndex in range(len(lines)):
                strline = lines[lIndex]
                
                i_current_line += 1
                i_line_after_edit = 0
                
                #
                # PROGRESS-BAR in M117:
                rgxm117 = re.search(RGX_FIND_LAYER, strline, flags=re.IGNORECASE)
                if rgxm117:
                    CURR_LAYER = int(rgxm117.group(1))
                                        
                    if argprogress:
                        # Create progress bar on printer's display
                        # Use a different char every 0.25% progress:
                        #   Edit progress_list to get finer progress
                        filledLength = int(pwidth * CURR_LAYER // NUM_OF_LAYERS)
                        filledLengthHALF = float(pwidth * CURR_LAYER / NUM_OF_LAYERS - filledLength)
                        strlcase = ""
                        p2width = pwidth

                        if CURR_LAYER / NUM_OF_LAYERS < 1:
                            # check for percentage and insert corresponding char from progress_list
                            for i in range(len(progress_list)):                                
                                if filledLengthHALF >= progress_list[i][0]:
                                    strlcase = progress_list[i][1]
                                    p2width = pwidth - 1
                                else:
                                    break
                                                            
                            if CURR_LAYER == 0:
                                strlcase = "1st Layer"
                                p2width = 9
                                    
                        # assemble the progressbar (M117)
                        strline = rf'M117 [{argsprogchar * filledLength + strlcase + "." * (p2width - filledLength)}];' + '\n'
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
                        
                        if re.search(rf'^(?:G1)\s(?:(Z)([-+]?\d*(?:\.\d+)))\s(?:F{RGX_FIND_NUMBER}?)(?:.*)$', strline, flags=re.IGNORECASE):
                            strline = re.sub(r'\n', '', strline, flags=re.IGNORECASE)
                            if DEBUG:
                                strline = f'; {strline} ; {appendstring}\n'
                            else:
                                strline = ""
                                
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
                    
                        if argsxy:
                            # add first line to move to XY only
                            line = f'{mc.group(2)} F{str(fspeed)}; just XY - {appendstring}\n'                           

                            # check height of FIRST_LAYER_HEIGHT
                            # to make ease-in a bit safer
                            flh = format_number(Decimal(FIRST_LAYER_HEIGHT) * 15)

                            # Then ease-in a bit ... this always gave me a heart attack!
                            #   So, depending on first layer height, drop to 15 times 
                            #   first layer height in mm (this is hardcoded above),                         
                            line = f'{line}G1 Z{str(flh)} F{str(fspeed)}; Then Z{str(flh)} at normal speed - {appendstring}\n'

                            #   then do the final Z-move at half the speed as before.
                            line = f'{line}G1 Z{str(FIRST_LAYER_HEIGHT)} F{str(format_number(float(fspeed)/3))}; Then to first layer height at a third of previous speed - {appendstring}\n'

                        else:
                            line = f'{mc.group(2)} Z{str(FIRST_LAYER_HEIGHT)} F{str(fspeed)} ; Z {str(FIRST_LAYER_HEIGHT)} - {appendstring}\n'

                        B_EDITED_LINE = False
                        B_SKIP_ALL = True                            
                        B_START_REMOVE_COMMENTS = True
                        i_line_after_edit = i_current_line
                        
                    strline = line

                if i_current_line > i_line_after_edit and argsremovecomments and B_START_REMOVE_COMMENTS == True:
                    if (strline.startswith("; prusaslicer_config")):
                        B_START_REMOVE_COMMENTS = False
                    if (not strline.startswith(";") or strline.startswith(" ;")):
                        rgx = re.search(rf'^[^;\s].*(\;)', strline, flags=re.IGNORECASE)
                        if rgx:
                            line = rgx.group(0)[:-1].strip()
                            line += '\n'
                            strline = line

                if (argsremoveallcomments):
                    if (strline.startswith(";") or strline.startswith(" ;")):
                        strline = ""
                    else:
                        rgx = re.search(rf'(.*)(?:;)', strline, flags=re.IGNORECASE)
                        if rgx:
                            line = rgx.group(0)[:-1].strip()
                            line += '\n'
                            strline = line
                        else:
                            strline = ""
    
                #
                # Write line back to file
                WRITEFILE.write(strline)

    except Exception as exc:
        print("Oops! Something went wrong. " + str(exc))
        sys.exit(1)

    finally:
        WRITEFILE.close()
        readfile.close()


# Write config file
def write_file(config):
    config.write(open(config_file, 'w+'))


# Reset counter
def resetCounter(conf, setCounterTo):
    if path.exists(config_file):
        conf['DEFAULT'] = {'FileIncrement': setCounterTo}
        write_file(conf)


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


def debugprint(s):
    if DEBUG:
        print(f"{NOW.strftime('%Y-%m-%d %H:%M:%S')}: {str(s)}")
        time.sleep(5)


def getINT(notint):
    x = float(notint)
    y = int(x)
    z = str(y)
    return z


ARGS = argumentparser()
CONFIG = configparser.ConfigParser()

main(ARGS, CONFIG)
