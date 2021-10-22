# Slic3r-Post-Processing

## What it does
Post processing for [PrusaSlicer](https://www.prusa3d.com/prusaslicer/), [SuperSlicer](https://github.com/supermerill/SuperSlicer) and maybe [Slic3r](http://slic3r.org):


## All-New Python Script:
In /[SPP-Python](https://github.com/foreachthing/Slic3rPostProcessing/tree/master/SPP-Python)/ is the Python-version of the "Cura"-move:
1. Heat up, down nozzle and ooze at your discretion.
1. Move to the first entry point on XYZ simultaneously.
    - Before: heat up, ooze, move to first layer height (Z), move to first start point (XY). This could lead to crashing the nozzle into the clips.
    - Now: heat up, ooze, move to first start point (XYZ).
The Python version does not require the verbose mode enabled or any other changes to the Start-, End-, or Layer-code.

Only requirement: the gcode has to have `;HEIGHT:[layer_z]` after `G92 E0`, or after Header G-Code. If you use a recent version of PrusaSlicer, you don't have to do anything. With Slic3r you'd have to add `;HEIGHT:[layer_z]` to the "Before layer change G-Code" field.


### Parameters for the Python Version
1. Optional: `--xy` will move to X and Y first, then drops on Z (eases-in a bit: full speed to 15 times "first layer height", then at half speed to first layer height).
             Omitting this option will lead to XYZ simultaneous move to first point. This will still clear the clips on the Ultimaker 2 plate. If not, you'd have to edit your start gcode to place the nozzle somewhere "better" (i.e. in the center of the bed) first.
2. Optional: `--oc` obscures slicer configuration at the end of the file. None of the settings will remain for anyone to see.
3. Optional: `--rk` removes comments except configuration and real comments.
4. Optional: `--rak` removes _all_ comments.
5. Optional: `--noback` won't create a backup file if True is passed.
6. Optional: `--filecounter` adds a file counter (prefix) to the output file name.
7. Optional: &ensp;`--rev` reverse counter (count down).
8. Optional: &ensp;`--setcounter` set counter manually to this [int].
9. Optional: &ensp;`--digits` set counter's number of digits. I.e. 5 = 00123.
10. Optional: `--notprusaslicer` should work with non-PrusaSlic3r (not tested!).
11. Optional: `--prog` a progress bar will be pushed to display (M117).
12. Optional:  `--pwidth` progress bar width in chars (= display-char-width - 2).
13. GCode file name (will be provided by the Slicer; _must_ be provided if used as standalone)


### Installation
Add this line to your "Print Settings" under "Output options" to the "Post-Processing scrips" field:
`<path to python.exe> <path to script>\Slic3rPostProcessor.py;`, 
or `<path to python.exe> <path to script>\Slic3rPostProcessor.py --xy;` (see above).

If you have one or more script active, add this to the correct spot (add new line). Scripts will be processed from top to bottom.


## to use in Slic3r
* The option `verbose` in Slic3r _(Slic3r -> Print Settings -> Output options)_, needs to be set to true.
  * In Post-Processing Scripts, add the full path to _this_ exe (see screenshot below).
* In Slic3r -> Printer -> Custom G-Code; add this:
  * Start G-Code:
    * `; START Header`
    * `; ... your header here`
    * `; END Header`
  * End G-Code:
    * `; START Footer`
    * `; ... your footer here`
    * `; END Footer`
  * Before layer change G-Code: `;layer:[layer_num]; \n M117 Layer [layer_num];`
  

## NOTE:
CS version will no longer be maintained and has been removed.
