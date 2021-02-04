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
"""

# Script based on:
# http://projects.ttlexceeded.com/3dprinting_prusaslicer_post-processing.html

# got issues?
# Please complain here: https://github.com/foreachthing/Slic3rPostProcessing/issues

import sys
import re
from shutil import ReadError, copyfile

sourcefile=sys.argv[1]

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
WRITEFILE = None

try:
    with open(sourcefile, "w") as WRITEFILE:
        for lIndex in range(len(lines)):
            strline = lines[lIndex]
            strcurrentline = strline

            if FIRST_LAYER_HEIGHT == 0 and B_SKIP_ALL == False:
                if strcurrentline and B_FOUND_Z == False:
                    # Find: ;HEIGHT:0.2 and store first layer height value
                    m = re.search(r"^;HEIGHT:(.*)", strcurrentline, flags=re.IGNORECASE)
                    if m:
                        # Found ;HEIGHT:
                        FIRST_LAYER_HEIGHT = m.group(1)
                        B_FOUND_Z = True

            else:
                if strcurrentline and B_FOUND_Z and B_SKIP_ALL == False:
                    # find:   G1 Z-HEIGHT F...
                    # result: ; G1 Z0.200 F7200.000 ; REMOVED by PostProcessing Script:
                    m = re.search(rf'^(?:G1)\s(?:Z{FIRST_LAYER_HEIGHT}.*)\s(?:F-?(?:0|[1-9]\d*)(?:\.\d+)?)(?:.*)$', strcurrentline, flags=re.IGNORECASE)
                    if m:
                        strline = re.sub(r'\n', '', strline, flags=re.IGNORECASE)
                        strline = '; ' + strline + ' ; REMOVED by PostProcessing Script:\n'
                        B_EDITED_LINE = True

            if B_EDITED_LINE and B_SKIP_ALL == False:
                # find:   G1 X85.745 Y76.083 F7200.000; fist "point" on Z-HEIGHT and add Z-HEIGHT
                # result: G1 X85.745 Y76.083 Z0.2 F7200 ; added by PostProcessing Script
                mc = re.search(r'^((G1\sX-?\d+\.?\d+\sY-?\d+\.?\d+)\s.*(F\d*))', strcurrentline, flags=re.IGNORECASE)
                if mc:
                    ln = mc.group(2) + ' Z' + str(FIRST_LAYER_HEIGHT) + ' ' + mc.group(3) + ' ; added by PostProcessing Script\n'
                    strline = ln
                    B_EDITED_LINE = False
                    B_SKIP_ALL = True

            # Write line back to file
            WRITEFILE.write(strline)

except Exception as exc:
    print("Oops! Something went wrong." + str(exc))
    sys.exit(1)

finally:
    WRITEFILE.close()
    readfile.close()
    print('All done.')
