# Slic3r-Post-Processing

## What it does
Post processing for [Slic3r](http://slic3r.org) to color the toolpaths to view in [CraftWare](https://craftunique.com/craftware).
This tool basically looks for `; skirt` and collects this block _(skirts, perimeter, softsupport and support are supported)_ and writes `;segType:Skirt` before. Then, it removes the verbose output to reduce the file size.

* Adds a number prefix to the filename (no more overwriting gcode).
* Changes the start code to be more like Cura.
  * XYZ-move to start point after oozing.
* Added ability to stop Bed Heater at Height x mm. See help for usage.
* and some more ...


### Download
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
![console](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/misc/console.png)



## GCode reviewed in CraftWare:
* before:
![before](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/misc/slicer_before.png)
* after:
![after](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/misc/slicer_after.png)
