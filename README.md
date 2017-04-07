# Slic3r-Post-Processing
Post processing for [Slic3r](http://slic3r.org) to color the toolpaths to view in [CraftWare](https://craftunique.com/craftware).
This tool basically looks for `; skirt` and collects this block _(skirts, perimeter, softsupport and support are supported)_ and writes `;segType:Skirt` before. Then, it removes the verbose output to reduce the file size.

## to use in Slic3r
* The option `verbose` in Slic3r _(Slic3r -> Print Settings -> Output options)_, needs to be set to true.
  * In Post-Processing Scripts, add the full path to _this_ exe (see screenshot below).
* In Slic3r -> Printer -> Custom G-Code; add this:
  * Start G-Code: `; END Header`
  * End G-Code: `; END Footer`
  
![Print Settings](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/slic3r_print_settings.png)


## Standalone:
Pass your GCode file, from Slic3r, to this exe. Either provide an output filename or not. If no output filename is given, then the original file will be overwritten.
Example: `Slic3rPostProcessing.exe "c:\temp\myfile.gcode" "c:\temp\mynewfile.gcode"`
The `mynewfile.gcode` can now be viewed in CraftWare - in color!




## GCode reviewd in CraftWare:
* before:
![before](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/slicer_before.png)
* after:
![after](https://github.com/foreachthing/Slic3rPostProcessing/blob/master/slicer_after.png)
