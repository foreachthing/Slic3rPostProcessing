# Slic3rPostProcessing
Post processing for Slic3r to color the toolpaths to view in Craftware.

* The option `verbose` in Slic3r _(Slic3r -> Print Settings -> Output options)_, needs to be set to true.
  * In Post-Processing Scripts, add the full path to _this_ exe.
* In Slic3r -> Printer -> Custom G-Code; add this:
  * Start G-Code: `; END Header`
  * End G-Code: `; END Footer`
