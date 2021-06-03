# Slic3r-Post-Processing

### IMPORTANT
This commit https://github.com/prusa3d/PrusaSlicer/commit/eaf6e0dca7c54ba71056a4bc0fd15450e40b81da broke the way PostProcessing is done! It first creates a temp file on the local drive, does the processing and then copies the file back.

## What it does
Post processing for [Slic3r](http://slic3r.org), [PrusaSlicer](https://www.prusa3d.com/prusaslicer/) and [SuperSlicer](https://github.com/supermerill/SuperSlicer):

* Adds a number prefix to the filename (no more overwriting gcode).
  * **NOTE**: See IMPORTANT above, when this script stops working. The standalone version is not affected. 
* Changes the start code to be more like Cura.
  * XYZ-move to start point after oozing.
* Added ability to stop Bed-Heater at Height x mm. See help for usage.
* Color the toolpaths to be viewed in [CraftWare](https://craftunique.com/craftware).
* and lots more ...

### All-New Python Script:
In /[SPP-Python](https://github.com/foreachthing/Slic3rPostProcessing/tree/master/SPP-Python)/ is the Python-version of the "Cura"-move:
1. Heat up, down nozzle and ooze at your discretion.
1. Move to the first entry point on XYZ simultaneously.
    - Before it was like this: heat up, ooze, move to first layer height (Z), move to first start point (XY).
    - Now: heat up, ooze, move to first start point (XYZ).
The Python version does not require the verbose mode enabled or any other changes to the Start-, End-, or Layer-code.

Only requirement: the gcode has to have `;HEIGHT:[layer_z]` after `G92 E0`, or after Header G-Code. If you use a recent version of PrusaSlicer, you don't have to do anything. With Slic3r you'd have to add `;HEIGHT:[layer_z]` to the "Before layer change G-Code" field.

### Parameters for the Python Version
1. Optional: `--xy` will move to X and Y first, then drops on Z (eases-in a bit: full speed to 15 times "first layer height", then at half speed to first layer height).
2. Optional: `--rc` removes slicer configuration at the end of the file.
3. Optional: `--noback` won't create a backup file if True is passed.
4. GCode file name (will be provided by the Slicer; _must_ be provided if used as standalone)


### Installation of Python Version
Add this line to your "Print Settings" under "Output options" to the "Post-Processing scrips" field:
`<path to your python installation>\python.exe <path to script>\Slic3rPostProcessor.py;`, 
or `<path to your python installation>\python.exe <path to script>\Slic3rPostProcessor.py --xy;` (see above).

If you have one or more script active, add this to the correct spot (add new line). Scripts will be processed from top to bottom.


## Download
[Latest release](https://github.com/foreachthing/Slic3rPostProcessing/releases) can be found here.

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
  
![Print Settings](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/misc/slic3r_print_settings.png)


## Standalone:
Pass your GCode file, from Slic3r, to this exe. Either provide an output filename or not. If no output filename is given, then the original file will be overwritten.
Examples:
- Simple: `Slic3rPostProcessing.exe -i "c:\temp\myfile.gcode" -o "c:\temp\mynewfile.gcode"`
  The `mynewfile.gcode` can now be viewed in CraftWare - in color!

- To stop the bed heater after 2.5 mm:
  `Slic3rPostProcessing.exe -i "c:\temp\myfile.gcode" -o "c:\temp\mynewfile.gcode" -s2.5`

### Console
Current console:

<!-- ![console](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/misc/console.png) -->


```

                   This program is compatible with Slic3r (standalone use see below) and PrusaSlicer.                   

  Print Settings -> Output options
    * Enable Verbose G-Code (!)
    * Copy and paste this full filename to Post-Processing Scripts:
      "C:\temp\Slic3rPostProcessing.exe"

  Printer Settings:
    * Add '; START Header' and '; END Header' to your Start GCode.
    * Add '; START Footer' and '; END Footer' to your End GCode.

                                     Standalone use: Slic3rPostProcessing [OPTIONS]                                     

Options:
  -i, --input=INPUT          The INPUT to process.
                               If file extention is omitted, .gcode will be
                               assumed.
  -o, --output=OUTPUT        The OUTPUT filename.
                               Optional. INPUT will get overwritten if OUTPUT
                               is not specified. File extension will be added
                               if omitted. If the counter is added, the INPUT
                               file will not be changed.
  -c, --counter=+ or -       Adds an export-counter to the FRONT of the
                               filename (+ or -). Default: -c+ (true)
                               Next counter: 000004
                               (If the timestamp is set to true as well, only
                               the counter will be added.)
  -p, --progress=+ or -      Display Progressbar (+ or -) on printer's LCD
                               instead of 'Layer 12/30'.
                               Default: -p- (false).
      --pw, --progresswidth=VALUE
                             Width (or number of Chars in Progressbar) on
                               printer's LCD. Allow two more characters for
                               opening and closing brackets.
                               Default: 18.
  -r, --removeconfig=+ or -  Removes Configuration at end of file (+ or -).
                               Everything after "END FOOTER" will be removed.
                               Default: -r- (false).
  -s, --stopbedheater=0-inf  Stops heating of the bed after this height in
                               millimeter (0-inf). Default = 0 => off
  -t, --timestamp=+ or -     Adds a timestamp to the END of the filename (+ or
                               -).
                               Default: -t- (false)
      --tf, --timeformat=FORMAT
                             FORMAT of the timestamp. Default: "yyMMdd-HHmmss"
                               Right now: 200812-152527
  -v, --verbosity=0-4        Debug message verbosity (0-4). Default: 3.
                               0 = Off
                               1 = Error
                               2 = Warning
                               3 = Info
                               4 = Verbose (this will output EVERY line of
                               GCode!)
  -x, --resetcounter         Reset export-counter to zero and exit (3).
      --xs, --setcounter=VALUE
                             Set export-counter to non-zero and exit (3).
  -h, --help                 Show this message and exit (2). Nothing will be
                               done.

```


## GCode reviewed in CraftWare:
* before:
![before](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/misc/slicer_before.png)
* after:
![after](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/misc/slicer_after.png)
