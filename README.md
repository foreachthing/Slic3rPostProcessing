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
- Option: `--xy` will move to X and Y first, then drops on Z (eases-in a bit: full speed to 15 times "first layer height", then at half speed to first layer height).
             Omitting this option will lead to XYZ simultaneous move to first point. This will still clear the clips on the Ultimaker 2 plate. If not, you'd have to edit your start gcode to place the nozzle somewhere "better" (i.e. in the center of the bed) first.
- Option: `--oc` obscures slicer configuration at the end of the file. None of the settings will remain for anyone to see.
- Option: `--rk` removes comments except configuration and real comments.
- Option: `--rak` removes _all_ comments.
- Option: `--backup` Create a backup file, if True is passed. (Default: False).
- Option: `--filecounter` adds a file counter (prefix) to the output file name.
- Option: `--rev` reverse counter (count down).
- Option: `--setcounter  int` set counter manually to this [int].
- Option: `--digits int` set counter's number of digits. I.e. 5 = 00123.
- Option: `--easeinfactor int` Scale Factor for ease in on Z. Z moves fast to this point then slows down.Scales the first layer height by this factor.
- Option: `--notprusaslicer` Pass argument for any other slicer (based on Slic3r) than PrusaSlicer.
- Option: `--craftwaretypes` Pass argument if you want to view GCode in Craftware.
- Option: `--orc2ps` Create comments, for OcrcaSlicer to be viewed in PrusaSlicer Viewer.
- Option: `--nomove` If --nomove is provided, no changes to the Start-GCode will be made.
- Option: `--numlayer`  Adds total number of layers to slice-info of G-Code file.
- Option: `--prog` If --prog is provided, a progress bar instead of layer number/percentage, will be added to your GCode file and displayed on your printer (M117).
- Option: `--proglayer` If --proglayer is provided, progress is reported as layer number/of layers, (Default: False)
- Option: `--pwidth int` Define the progress bar length in characters. You might need to adjust the default value. Allow two more chars for brackets. Example: [OOOOO.............].
- Option: `--pchar str` Set progress bar character. (Default: O)
- Required: GCode file name (will be provided by the Slicer; _must_ be provided if used as standalone)



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
