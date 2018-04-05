using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Diagnostics;
using NDesk.Options;
using System.Globalization;

namespace Slic3rPostProcessing
{
    internal class Program
    {
        public static short insertedSkirtSegment { get; set; }
        public static short insertedInfillSegment { get; set; }
        public static short insertedSupportSegment { get; set; }
        public static short insertedSoftSupportSegment { get; set; }
        public static short insertedPerimeterSegment { get; set; }

        public static int ConsoleWidth { get; set; }

        public static string strTimeformat = "yyMMdd-HHmmss";

        /// <summary>
        /// Post processing for Slic3r to color the toolpaths to view in Craftware
        /// </summary>
        /// <param name="args">GCode file fresh out from Slic3r.</param>
        /// <remarks>The option `verbose` in Slic3r, needs to be set to true.
        /// and also this `before layer-change-G-code` needs to be in place: `;layer:[layer_num];`.
        /// Start G-Code: `; END Header`.
        /// End G-Code: `; END Footer`.</remarks>
        private static int Main(string[] args)
        {
            Properties.Settings.Default.Reload();

            if (Properties.Settings.Default._UpdateRequired == true)
            {
                Properties.Settings.Default.Upgrade();
                Properties.Settings.Default._UpdateRequired = false;
                Properties.Settings.Default.Save();
            }

            bool show_help = false;

            int verbosity = 3;
            int intSizeOfCounter = Properties.Settings.Default._intCounterSize;
            double stopbeadheater = 0d;
            string strINputFile = null;
            string strOUTputFile = null;

            bool booTimestamp = false;
            bool booCounter = true;
            bool booRemoveConfig = false;
            bool booResetCounter = false;

            ////// / / / / / / / / / / / / /
            // Log writer START
            Trace.AutoFlush = false;

            ConsoleWidth = Logger.GetConsoleWidth();

            OptionSet os = new OptionSet();
            os.Add("i|input=", "The {INPUT} to process. " + Environment.NewLine + "If file extention is omitted, .gcode will be assumed.",
                i => strINputFile = i);

            os.Add("o|output=", "The {OUTPUT} filename. " + Environment.NewLine + "Optional. {INPUT} will get overwritten if {OUTPUT} is not specified. File extension will be added if omitted.",
                o => strOUTputFile = o);

            os.Add("c|counter=", "Adds an export-counter to the FRONT of the filename ({+ or -})." + Environment.NewLine + "Default: -c+ (true)" + Environment.NewLine + "If the timestamp is set to true as well, only the counter will be added.",
                c => booCounter = c != null);

            os.Add("cd|counterdigits=", "Counter padded with this many zeros {1-10}. Default " + intSizeOfCounter.ToString() + ". Next counter: " + (Properties.Settings.Default.export_counter + 1).ToString("D" + intSizeOfCounter.ToString()), (int cd) => { if (cd > 0 & cd < 11) intSizeOfCounter = cd; });

            os.Add("r|removeconfig=", "Removes Configuration at end of file ({+ or -}). Everything after \"END FOOTER\" will be removed." + Environment.NewLine + "Default: -r- (false).",
                r => booRemoveConfig = r != null);

            os.Add("s|stopbedheater=", "Stops heating of the bed after this height in millimeter ({0-inf}). Default = 0 => off",
                (double s) => { if (s >= 0) stopbeadheater = s; });

            os.Add("t|timestamp=", "Adds a timestamp to the END of the filename ({+ or -})." + Environment.NewLine + "Default: -t- (false)",
                t => booTimestamp = t != null);

            os.Add("tf|timeformat=", "{FORMAT} of the timestamp. Default: \"" + strTimeformat + "\" Right now: " + DateTime.Now.ToString(strTimeformat),
                f => strTimeformat = f);

            os.Add("v|verbosity=", "Debug message verbosity ({0-4}). Default: " + verbosity + ". " + Environment.NewLine + "0 = Off " + Environment.NewLine + "1 = Error " + Environment.NewLine + "2 = Warning " + Environment.NewLine + "3 = Info " + Environment.NewLine + "4 = Verbose (this will output EVERY line of GCode!)",
                (int v) => { if (v >= 0 & v < 5) verbosity = v; });

            os.Add("x|resetcounter", "Reset export-counter to zero and exit (3).",
              x => booResetCounter = x != null);

            os.Add("h|help", "Show this message and exit (2). Nothing will be done.",
                h => show_help = h != null);

            List<string> extra;
            try
            {
                extra = os.Parse(args);

                if (extra.Count == 1 & args.Length == 1) strINputFile = extra[0];

                if (strINputFile != null)
                {
                    if (!strINputFile.ToLower().EndsWith("gcode")) strINputFile += ".gcode";
                }
            }
            catch (OptionException e)
            {
                Logger.LogError(e.Message);
                ShowHelp(os);
                Environment.Exit(1);
                return 1;
            }

            Logger.traceSwitch.Level = (TraceLevel)verbosity;//TraceLevel.Info;
            Trace.Listeners.Clear();

            TextWriterTraceListener listener = new TextWriterTraceListener(Console.Out);
            Trace.Listeners.Add(listener);

            if (show_help)
            {
                ShowHelp(os);
                Environment.Exit(2);
                return 2;
            }

            if (booResetCounter)
            {
                Properties.Settings.Default.export_counter = 0;
                Properties.Settings.Default.Save();
                Environment.Exit(3);
                return 3;
            }

            if (Properties.Settings.Default._intCounterSize != intSizeOfCounter)
            {
                // add settings to user-settings
                Properties.Settings.Default._intCounterSize = intSizeOfCounter;
                Properties.Settings.Default.Save();
                //
            }

            if (strINputFile == null)
            {
                // Console.WriteLine("I need an arguement; your's not good!");
                ShowHelp(os);
                Environment.Exit(1);
                return 1;
            }
            else
            {
                if (!WaitForFile(strINputFile, 5))
                {
                    Console.WriteLine(" ");
                    Logger.LogWarning("File not found:");
                    PrintFileSummary(strINputFile, true);
                    Logger.LogWarning("Please try again later or check your input.");
#if DEBUG
                    {
                        Console.WriteLine("Press any key to continue . . .");
                        Console.ReadKey();
                    }
#else
                    {
                        System.Threading.Thread.Sleep(500);
                        Environment.Exit(1);
                    }
#endif
                    Environment.Exit(1);
                    return 1;
                }
                var lines = File.ReadAllLines(strINputFile).ToList();

                Logger.LogInfo("Input :");
                PrintFileSummary(strINputFile);

                NumberFormatInfo nfi = new CultureInfo("de-CH", false).NumberFormat;
                nfi.NumberDecimalDigits = 0;
                Logger.LogInfo((lines.Count - 1).ToString("N", nfi) + " lines of gcode will be processed.");

                string newfilename = Path.Combine(Path.GetDirectoryName(strINputFile), Guid.NewGuid().ToString().Replace("-", "") + ".gcode_temp");

                ResetAllCountersButThis(DonotReset.AllReverseNone);
                bool StartGCode = false;
                bool EndGCode = false;
                bool EndFooter = false;
                bool StartPoint = false;
                bool FirstLine = false;
                bool bedheaterstopped = false;
                bool eof = false;
                string FirstLayer = null;
                double currentlayerheight = 0;

                int q = -1;

                StringBuilder sb = new StringBuilder();

                // Count all Layers
                int iLayerCount = 0;
                foreach (string l in lines)
                { //("; END Header"))
                    if (l.Contains(";layer:") && (!l.Contains("before_layer_gcode"))) iLayerCount++;
                }

                int iLayer = 0;
                Console.WriteLine("");
                foreach (string l in lines)
                {
                    int paddingverbose = lines.Count.ToString().Length;
                    Logger.LogVerbose((q + 1).ToString("N", nfi).PadLeft(paddingverbose) + ": " + l);

                    q++;

                    // Report progress every percent; if not verbose
                    if (Logger.traceSwitch.Level == TraceLevel.Info)
                    {
                        if (q % (lines.Count / 100) == 0) Progressbar((double)q * 100 / lines.Count);
                        if (q + 1 == lines.Count) { Console.WriteLine(""); Console.WriteLine(""); }
                    }
                    if (l.Contains(";layer:0;"))  //("; END Header"))
                    {
                        StartGCode = true;
                        sb.AppendLine(l);
                        continue;
                    }

                    if (l.Contains(";") & l.Contains("START Header") & !eof)
                    {
                        StartGCode = false;
                        sb.AppendLine(l);
                        continue;
                    }

                    if (l.Contains(";") & l.Contains("START Footer") & !eof)
                    {
                        EndGCode = true;
                        sb.AppendLine(l);
                        continue;
                    }

                    if (l.Contains(";") & l.Contains("END Footer") & !eof)
                    {
                        EndGCode = true;
                        EndFooter = true;
                        sb.AppendLine(l);
                        continue;
                    }

                    // exit if no config should remain with the file
                    if (booRemoveConfig && EndFooter)
                    {
                        // if at end of footer, go to next empty line and then break;
                        if (l == string.Empty & !eof)
                        {
                            eof = true;
                            continue;
                        }
                        else
                        {
                            continue;
                        }
                    }

                    if (StartGCode & !EndGCode)
                    {
                        //
                        // Stop Bed Heater
                        if (stopbeadheater > 0)
                        {
                            Match matchlayerheight = Regex.Match(l, @"^(?:G1)\s(Z(\d+(\.\d+)?|\.\d+?))", RegexOptions.IgnoreCase);

                            if (matchlayerheight.Success)
                            {
                                currentlayerheight = Convert.ToDouble(matchlayerheight.Groups[2].Value);
                                Logger.LogVerbose("Current Layer Height: " + currentlayerheight + " mm");

                                if (currentlayerheight >= stopbeadheater & (bedheaterstopped == false))
                                {
                                    sb.AppendLine("M140 S0; Stop Bed Heater on Layer Height " + currentlayerheight + " mm");
                                    sb.AppendLine("M117 Stopping Bed Heater.");

                                    bedheaterstopped = true;
                                    stopbeadheater = currentlayerheight;
                                }
                            }
                        }

                        if (!StartPoint | !FirstLine)
                        {
                            if (FirstLayer == null)
                            {
                                Match match0 = Regex.Match(l, @"^([gG]1)\s([zZ](-?(0|[1-9]\d*)(\.\d+)?))\s([fF](-?(0|[1-9]\d*)(\.\d+)?))(.*)$", RegexOptions.IgnoreCase);

                                // Here we check the Match instance.
                                if (match0.Success)
                                {
                                    FirstLayer = match0.Groups[2].Value;
                                    Logger.LogVerbose("First Layer Height: " + FirstLayer + " mm");
                                    FirstLine = true;
                                    continue;
                                }
                            }

                            if (FirstLayer != null)
                            {
                                Match match1 = Regex.Match(l, @"^([gG]1)\s([xX]-?(0|[1-9]\d*)(\.\d+)?)\s([yY]-?(0|[1-9]\d*)(\.\d+)?)\s([fF]-?(0|[1-9]\d*)(\.\d+)?)\s((; move to first)\s(\w+).*(point))$", RegexOptions.IgnoreCase);
                                // Here we check the Match instance.
                                if (match1.Success)
                                {
                                    sb.AppendLine(l.Replace(match1.Groups[8].Value, FirstLayer + " " + match1.Groups[8].Value));
                                    Logger.LogVerbose("Start Point: " + l);
                                    StartPoint = true;
                                    continue;
                                }
                            }
                        }

                        if (l.StartsWith("M117"))
                        {
                            iLayer++;
                            sb.AppendLine("M117 Layer " + iLayer + "/" + iLayerCount);
                            continue;
                        }

                        if (l.EndsWith("; skirt") | l.EndsWith(" ; brim"))
                        {
                            // RESET counter
                            ResetAllCountersButThis(DonotReset.SkirtSegment);

                            Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

                            if (l.Contains("segType:Skirt") | insertedSkirtSegment != 0)
                            {
                                sb.AppendLine(TrimComment(l));
                            }
                            else
                            {
                                sb.AppendLine(";segType:Skirt");
                                sb.AppendLine(";Type:Skirt".ToUpper());
                                sb.AppendLine(TrimComment(l));
                                insertedSkirtSegment = 1;
                            }
                            continue;
                        }

                        if (l.EndsWith("; infill"))
                        {
                            // RESET counter
                            ResetAllCountersButThis(DonotReset.InfillSegment);

                            Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

                            if (l.Contains("segType:Infill") | insertedInfillSegment != 0)
                            {
                                sb.AppendLine(TrimComment(l));
                            }
                            else
                            {
                                sb.AppendLine(";segType:Infill");
                                sb.AppendLine(";Type:Infill".ToUpper());
                                sb.AppendLine(TrimComment(l));
                                insertedInfillSegment = 1;
                            }
                            continue;
                        }

                        if (l.EndsWith("; support material interface"))
                        {
                            // RESET counter
                            ResetAllCountersButThis(DonotReset.SoftSupportSegment);

                            Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

                            if (l.Contains("segType:SoftSupport") | insertedSoftSupportSegment != 0)
                            {
                                sb.AppendLine(TrimComment(l));
                            }
                            else
                            {
                                sb.AppendLine(";segType:SoftSupport");
                                sb.AppendLine(";Type:SoftSupport".ToUpper());
                                sb.AppendLine(TrimComment(l));
                                insertedSoftSupportSegment = 1;
                            }
                            continue;
                        }

                        if (l.EndsWith("; support material"))
                        {
                            // RESET counter
                            ResetAllCountersButThis(DonotReset.SupportSegment);

                            Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

                            if (l.Contains("segType:Support") | insertedSupportSegment != 0)
                            {
                                sb.AppendLine(TrimComment(l));
                            }
                            else
                            {
                                sb.AppendLine(";segType:Support");
                                sb.AppendLine(";Type:Support".ToUpper());
                                sb.AppendLine(TrimComment(l));
                                insertedSupportSegment = 1;
                            }
                            continue;
                        }

                        if (l.EndsWith("; perimeter"))
                        {
                            // RESET counter
                            ResetAllCountersButThis(DonotReset.PerimeterSegment);

                            Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

                            if (l.Contains("segType:Perimeter") | insertedPerimeterSegment != 0)
                            {
                                sb.AppendLine(TrimComment(l));
                            }
                            else
                            {
                                sb.AppendLine(";segType:Perimeter");
                                sb.AppendLine(";Type:Perimeter".ToUpper());
                                sb.AppendLine(TrimComment(l));
                                insertedPerimeterSegment = 1;
                            }
                            continue;
                        }

                        // Remove any leftover comments
                        sb.AppendLine(TrimComment(l));
                    }
                    else
                    {
                        sb.AppendLine(l);
                    }
                }

                try
                {
                    File.WriteAllText(newfilename, sb.ToString());

                    if (booCounter & booTimestamp) booTimestamp = false;

                    if (booCounter)
                    {
                        Properties.Settings.Default.export_counter++;
                        Properties.Settings.Default.Save();
                    }

                    Logger.LogInfo("Output :");
                    if (strOUTputFile != null & File.Exists(newfilename))
                    {
                        if (!strOUTputFile.ToLower().EndsWith("gcode")) strOUTputFile += ".gcode";

                        File.Delete(strOUTputFile);
                        if (booTimestamp)
                        {
                            string newfile = strOUTputFile.AppendTimeStamp();
                            File.Move(newfilename, newfile);
                            PrintFileSummary(newfile);
                        }
                        else if (booCounter)
                        {
                            string newfile = strOUTputFile.PrependCounter(intSizeOfCounter);
                            File.Move(newfilename, strOUTputFile.PrependCounter(intSizeOfCounter));
                            PrintFileSummary(newfile);
                        }
                        else
                        {
                            File.Move(newfilename, strOUTputFile);
                            PrintFileSummary(strOUTputFile);
                        }
                    }

                    if (strOUTputFile == null & File.Exists(newfilename))
                    {
                        File.Delete(strINputFile);
                        if (booTimestamp)
                        {
                            string newfile = strINputFile.AppendTimeStamp();
                            File.Move(newfilename, newfile);
                            PrintFileSummary(newfile);
                        }
                        else if (booCounter)
                        {
                            string newfile = strINputFile.PrependCounter(intSizeOfCounter);
                            File.Move(newfilename, newfile);
                            PrintFileSummary(newfile);
                        }
                        else
                        {
                            File.Move(newfilename, strINputFile);
                            PrintFileSummary(strINputFile);
                        }
                    }

                    if (stopbeadheater > 0) { Logger.LogInfo("Bed Heater disabled after height " + stopbeadheater + " mm."); }
                    if (booRemoveConfig) { Logger.LogInfo("Configuration/Settings have been removed from GCode."); }

#if DEBUG
                    {
                        Console.WriteLine("Press any key to continue . . .");
                        Console.ReadKey();
                    }
#else
                    System.Threading.Thread.Sleep(500);
#endif

                    string ts = ((char)('\u25a0')).ToString();
                    ts = ts.PadRight(5, '\u25a0');
                    Logger.LogInfo(ts + " All Done " + ts);

                    Environment.Exit(0);
                    return 0;
                }
                catch (Exception ex)
                {
                    Logger.LogError(ex.Message);
                    ShowHelp(os);
                    Environment.Exit(1);
                    return 1;
                }
            }
        }

        /// <summary>
        /// Sit here and wait for 'filename'.
        /// </summary>
        /// <param name="filename">Filename to look for</param>
        /// <param name="timeout">[Optional] Timeout, in seconds, to quit loop if file does not exist - ever.</param>
        private static bool WaitForFile(string filename, int timeout = 30)
        {
            int wait = 0; // loop counter for waiting
            int waitfor = 10; // wait this many quick loops before timeout starts
            int dt = 0; // delta time
            bool fileexists = File.Exists(filename);
            bool exitloop = fileexists;
            if (!fileexists)
            {
                do
                {
                    // wait here until the file exists.
                    // It can take some time to copy/rename the .tmp to .gcode.
                    // QUIT after timeout has expired.
                    if (wait > waitfor)
                    {
                        if (wait == waitfor + 1)
                        {
                            Console.WriteLine("");
                            Logger.LogInfo("Waiting for input file (" + Path.GetFileName(filename) + ") at " + Environment.NewLine + "          " + Path.GetDirectoryName(filename));
                        }

                        int prog = 100 - (dt * 100 / timeout);
                        Progressbar(prog, false, timeout - dt);
                        if (timeout - dt == 0) Console.WriteLine("");

                        System.Threading.Thread.Sleep(new TimeSpan(0, 0, 1));

                        if (timeout - dt == 0) exitloop = true;

                        dt += 1;
                    }
                    else
                    {
                        System.Threading.Thread.Sleep(50);
                    }

                    wait++;

                    fileexists = File.Exists(filename);
                    if (fileexists)
                    {
                        Logger.LogInfo(" ");
                        break;
                    }
                } while (!exitloop);
            }

            return fileexists;
        }

        private static void Progressbar(double Progress, bool ReportAsPercentage = true, int Value = -1)
        {
            int conswidth = ConsoleWidth - 20;
            char pad = '\u2588'; //  '█';
            char spad = '\u2591'; // '░';
            string prog = "";
            string progformat = "";
            double newprog;

            newprog = (Value != -1) ? Value : Progress / 100;

            progformat = ReportAsPercentage ? String.Format("{0:P0} ", newprog).PadRight(5) : String.Format("{0} ", newprog).PadRight(5);

            double doh = Progress / 100 * conswidth;

            int progr = (int)Math.Round(doh, 0);

            string mynewfunkyprogressbar = "       " +
                progformat +
                prog.PadLeft(progr, pad) +
                prog.PadLeft(conswidth - progr, spad);

            Logger.LogInfoOverwrite(mynewfunkyprogressbar);
        }

        private static void PrintFileSummary(string filename, bool asWarning = false)
        {
            if (asWarning)
            {
                Logger.LogWarning("  File name : \"" + Path.GetFileName(filename) + "\"");
                if (Path.GetDirectoryName(filename) != "") Logger.LogWarning("  Directory : \"" + Path.GetDirectoryName(filename) + "\"");
            }
            else
            {
                Logger.LogInfo("  File name : \"" + Path.GetFileName(filename) + "\"");
                if (Path.GetDirectoryName(filename) != "") Logger.LogInfo("  Directory : \"" + Path.GetDirectoryName(filename) + "\"");
            }
        }

        private static string TrimComment(string line)
        {
            char[] TrimChars = new char[] { ' ' };
            if (line.Contains(";")) line = line.Split(';')[0].TrimEnd(TrimChars);
            return line;
        }

        private static void ShowHelp(OptionSet p)
        {
            ConsoleColor fg = Console.ForegroundColor;
            ConsoleColor bg = Console.BackgroundColor;

            Console.WriteLine();
            Console.BackgroundColor = ConsoleColor.Black;
            Console.ForegroundColor = ConsoleColor.Yellow;

            string textnote = "This program is for use with Slic3r (or standalone).";
            int paaad = (Program.ConsoleWidth - textnote.Length) / 2;

            Console.WriteLine("".PadLeft(paaad) + textnote.PadRight(Program.ConsoleWidth - paaad));
            Console.ResetColor();
            Console.WriteLine();
            Console.WriteLine("  Print Settings -> Output options");
            Console.WriteLine("    * Enable Verbose G-Code (!)");

            Console.WriteLine("    * Put this filename " + Path.GetFileName(System.Reflection.Assembly.GetEntryAssembly().Location) + " in Post-Processing Scripts.");
            Console.WriteLine("      Current filename: \"" + System.Reflection.Assembly.GetEntryAssembly().Location + "\"");

            Console.WriteLine("");
            Console.WriteLine("  Printer Settings:");
            Console.WriteLine("    * Add \"; START Header\" and \"; END Header\" to your Start GCode.");
            Console.WriteLine("    * Add \"; START Footer\" and \"; END Footer\" to your End GCode.");

            Console.WriteLine();
            Console.BackgroundColor = ConsoleColor.Black;
            Console.ForegroundColor = ConsoleColor.Yellow;

            textnote = "Standalone usage: Slic3rPostProcessing [OPTIONS]";
            paaad = (Program.ConsoleWidth - textnote.Length) / 2;
            Console.WriteLine("".PadLeft(paaad) + textnote.PadRight(Program.ConsoleWidth - paaad));

            Console.ResetColor();
            Console.WriteLine();
            Console.WriteLine("Options:");
            p.WriteOptionDescriptions(Console.Out);
        }

        /// <summary>
        /// Resets all other Counters to their respective default.
        /// </summary>
        /// <param name="CounterNOT2Reset">Counter NOT to reset!</param>
        public static void ResetAllCountersButThis(int CounterNOT2Reset)
        {
            if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.InfillSegment)
            {
                insertedInfillSegment = 0;
            }
            if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.SupportSegment)
            {
                insertedSupportSegment = 0;
            }
            if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.PerimeterSegment)
            {
                insertedPerimeterSegment = 0;
            }
            if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.SoftSupportSegment)
            {
                insertedSoftSupportSegment = 0;
            }
            if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.SkirtSegment)
            {
                insertedSkirtSegment = 0;
            }
        }
    }

    public static class DonotReset
    {
        public const int AllReverseNone = -1;
        public const int InfillSegment = 0;
        public const int SupportSegment = 1;
        public const int PerimeterSegment = 2;
        public const int SoftSupportSegment = 3;
        public const int SkirtSegment = 4;
    }

    public static class MyExtensions
    {
        public static string AppendTimeStamp(this string fileName)
        {
            return Path.Combine(Path.GetDirectoryName(fileName),
                Path.GetFileNameWithoutExtension(fileName)
                + "_"
                + DateTime.Now.ToString(Program.strTimeformat)
                + Path.GetExtension(fileName));
        }

        public static string PrependCounter(this string fileName, int digits)
        {
            int counter = Properties.Settings.Default.export_counter;

            string numformat = "D" + digits.ToString();

            return Path.Combine(Path.GetDirectoryName(fileName),
                counter.ToString(numformat)
                + "_"
                + Path.GetFileNameWithoutExtension(fileName)
                + Path.GetExtension(fileName));
        }
    }

    internal class Logger
    {
        private static int origWidth { get; set; }
        private static int origHeight { get; set; }
        private static int origBWidth { get; set; }
        private static int origBHeight { get; set; }

        private static ConsoleColor fg = Console.ForegroundColor;
        private static ConsoleColor bg = Console.BackgroundColor;

        public static int GetConsoleWidth()
        {
            // IntPtr myHandle = Process.GetCurrentProcess().MainWindowHandle;
            // NOW WHAT?! What do I do with myHandle? I Need the console to return
            // the width of the window.

            //return Console.WindowWidth;

            return 80;
        }

        public static void LogInfo(string message)
        {
            Trace.WriteLineIf(Logger.traceSwitch.TraceInfo, "Info    : " + message);
        }

        /// <summary>
        /// Overwrites current line
        /// </summary>
        /// <param name="message"></param>
        public static void LogInfoOverwrite(string message)
        {
            Console.Write("\r" + message);
        }

        /// <summary>
        /// Writeline with datetime stamp
        /// </summary>
        /// <param name="message"></param>
        public static void Log(string message)
        {
            Trace.WriteLine(DateTime.Now + " : " + message);
        }

        public static void LogError(string message)
        {
            Trace.WriteLineIf(Logger.traceSwitch.TraceError, "ERROR : " + message);
        }

        public static void LogWarning(string message)
        {
            string warn = "WARNING :";

            Console.ForegroundColor = ConsoleColor.Black;
            Console.BackgroundColor = ConsoleColor.Yellow;
            Trace.WriteLineIf(Logger.traceSwitch.TraceWarning, warn);
            Console.ResetColor();

            Console.SetCursorPosition(warn.Length + 1, Console.CursorTop - 1);
            Trace.WriteIf(Logger.traceSwitch.TraceWarning, message);
            Trace.WriteLineIf(Logger.traceSwitch.TraceWarning, "");
        }

        public static void LogError(Exception e)
        {
            Trace.WriteLineIf(Logger.traceSwitch.TraceError, "EXCEPTION : " + e);
        }

        public static void LogVerbose(string message)
        {
            Trace.WriteLineIf(Logger.traceSwitch.TraceVerbose, "Verbose : " + message);
        }

        public static TraceSwitch traceSwitch = new TraceSwitch("Application", "Application");
    }
}