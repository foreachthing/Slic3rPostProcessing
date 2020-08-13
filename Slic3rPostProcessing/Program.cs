using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Diagnostics;
using System.Globalization;
using Mono.Options;

namespace Slic3rPostProcessing
{
	internal class Program
	{
		public static short InsertedSkirtSegment { get; set; }
		public static short InsertedInfillSegment { get; set; }
		public static short InsertedSupportSegment { get; set; }
		public static short InsertedSoftSupportSegment { get; set; }
		public static short InsertedPerimeterSegment { get; set; }

		private static readonly char ChrConsoleProgressbar = '\u2588'; //  '█';
		private static readonly char ChrConsoleProgressPadding = '\u2591'; // '░';

		private static readonly char ChrLCDProgress = Convert.ToChar("O");
		private static readonly char[] ChrsLCDProgress = new char[] { Convert.ToChar("+"), Convert.ToChar("-"), Convert.ToChar("x") };
		private static int IntLCDProgressPrevPadding;

		public static int IntConsoleWidth { get; set; }

		public static string StrTimeFormat = "yyMMdd-HHmmss";
		public static int IntExportCounter;
		public static int IntCounterPadding;

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

			string sINIFile = Path.Combine(Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location), "settings.ini");
			INI inisettings = new INI(sINIFile);

			if (!File.Exists(sINIFile))
			{
				inisettings.WriteValue("ExportCounter", "PostProcessing", 0.ToString());
				inisettings.WriteValue("CounterPadding", "PostProcessing", 6.ToString());
				inisettings.Save();
			}

			int.TryParse(inisettings.GetValue("ExportCounter", "PostProcessing"), out IntExportCounter);
			int.TryParse(inisettings.GetValue("CounterPadding", "PostProcessing"), out IntCounterPadding);

			int iVerbosity = 3;
			int iProgressbarWidth = 18;

			double dStopBedHeater = 0d;
			string sInputFile = null;
			string sOutputFile = null;

			string sSetCounter = "notanumber";

			bool bTimestamp = false;
			bool bCounter = true;
			bool bRemoveConfig = false;
			bool bProgressbar = false;
			bool bResetCounter = false;
			bool bShowHelp = false;

			////// / / / / / / / / / / / / /
			// Log writer START
			Trace.AutoFlush = false;

			IntConsoleWidth = Logger.GetConsoleWidth();

			OptionSet os = new OptionSet
			{
				{
					"i|input=",
					"The {INPUT} to process. " + Environment.NewLine + "If file extention is omitted, .gcode will be assumed.",
					i => sInputFile = i
				},

				{
					"o|output=",
					"The {OUTPUT} filename. " + Environment.NewLine + "Optional. {INPUT} will get overwritten if {OUTPUT} is not specified. File extension will be added if omitted. If the counter is added, the {INPUT} file will not be changed.",
					o => sOutputFile = o
				},

				{
					"c|counter=",
					"Adds an export-counter to the FRONT of the filename ({+ or -}). Default: -c+ (true)" + Environment.NewLine + "Next counter: " + (IntExportCounter).ToString("D" + IntCounterPadding) + Environment.NewLine + "(If the timestamp is set to true as well, only the counter will be added.)",
					c => bCounter = c != null
				},

				{
					"p|progress=",
					"Display Progressbar ({+ or -}) on printer's LCD instead of 'Layer 12/30'." + Environment.NewLine + "Default: -p- (false).",
					p => bProgressbar = p != null
				},
				{
					"pw|progresswidth=",
					"Width (or number of Chars in Progressbar) on printer's LCD. Allow two more characters for opening and closing brackets." + Environment.NewLine + "Default: "+ iProgressbarWidth.ToString() +".",
					(int pw) => iProgressbarWidth = pw
				},

				{
					"r|removeconfig=",
					"Removes Configuration at end of file ({+ or -}). Everything after \"END FOOTER\" will be removed." + Environment.NewLine + "Default: -r- (false).",
					r => bRemoveConfig = r != null
				},

				{
					"s|stopbedheater=",
					"Stops heating of the bed after this height in millimeter ({0-inf}). Default = 0 => off",
					(double s) => { if (s >= 0) dStopBedHeater = s; }
				},

				{
					"t|timestamp=",
					"Adds a timestamp to the END of the filename ({+ or -})." + Environment.NewLine + "Default: -t- (false)",
					t => bTimestamp = t != null
				},

				{
					"tf|timeformat=",
					"{FORMAT} of the timestamp. Default: \"" + StrTimeFormat + "\" Right now: " + DateTime.Now.ToString(StrTimeFormat),
					f => StrTimeFormat = f
				},

				{
					"v|verbosity=",
					"Debug message verbosity ({0-4}). Default: " + iVerbosity + ". " + Environment.NewLine + "0 = Off " + Environment.NewLine + "1 = Error " + Environment.NewLine + "2 = Warning " + Environment.NewLine + "3 = Info " + Environment.NewLine + "4 = Verbose (this will output EVERY line of GCode!)",
					(int v) => { if (v >= 0 & v < 5) iVerbosity = v; }
				},

				{
					"x|resetcounter",
					"Reset export-counter to zero and exit (3).",
					x => bResetCounter = x != null
				},

				{
					"xs|setcounter=",
					"Set export-counter to non-zero and exit (3).",
					xs => sSetCounter = xs.ToString()
				},

				{
					"h|help",
					"Show this message and exit (2). Nothing will be done.",
					h => bShowHelp = h != null
				}
			};

			List<string> extra;
			try
			{
				extra = os.Parse(args);

				if (extra.Count == 1 & args.Length == 1) sInputFile = extra[0];

				if (sInputFile != null)
				{
					if (!sInputFile.ToLower().EndsWith("gcode")) sInputFile += ".gcode";
				}
			}
			catch (OptionException e)
			{
				Logger.LogError(e.Message);
				ShowHelp(os);
				Environment.Exit(1);
				return 1;
			}

			Logger.traceSwitch.Level = (TraceLevel)iVerbosity;//TraceLevel.Info;
			Trace.Listeners.Clear();

			TextWriterTraceListener listener = new TextWriterTraceListener(Console.Out);
			Trace.Listeners.Add(listener);

			if (bShowHelp)
			{
				ShowHelp(os);
				Environment.Exit(2);
				return 2;
			}

			if (bResetCounter)
			{
				IntExportCounter = 0;
				inisettings.WriteValue("ExportCounter", "PostProcessing", 0.ToString());
				inisettings.Save();
				Environment.Exit(3);
				return 3;
			}

			int iSetCounterTest = -1;
			if (int.TryParse(sSetCounter, out iSetCounterTest))
			{
				if (iSetCounterTest > 0)
				{
					inisettings.WriteValue("ExportCounter", "PostProcessing", sSetCounter);
					inisettings.Save();
				}
				Environment.Exit(3);
				return 3;
			}

			if (sInputFile == null)
			{
				// Console.WriteLine("I need an argument; your's not good!");
				ShowHelp(os);
				Environment.Exit(1);
				return 1;
			}
			else
			{
				if (!WaitForFile(sInputFile, 5))
				{
					Console.WriteLine(" ");
					Logger.LogWarning("File not found:");
					PrintFileSummary(sInputFile, true);
					Logger.LogWarning("Please try again later or check your input.");
#if DEBUG
					{
						Console.WriteLine("Press any key to continue . . .");
						Console.ReadKey();
					}
#else
					{
						System.Threading.Thread.Sleep(2000);
						Environment.Exit(1);
					}
#endif
					Environment.Exit(1);
					return 1;
				}
				var lines = File.ReadAllLines(sInputFile).ToList();

				Logger.LogInfo("Input :");
				PrintFileSummary(sInputFile);

				NumberFormatInfo nfi = new CultureInfo("en-US", false).NumberFormat;
				nfi.NumberDecimalDigits = 0;
				Logger.LogInfo((lines.Count - 1).ToString("N", nfi) + " lines of gcode will be processed.");

				string sNewfilename = Path.Combine(Path.GetDirectoryName(sInputFile), Guid.NewGuid().ToString().Replace("-", "") + ".gcode_temp");

				ResetAllCountersButThis(DonotReset.AllReverseNone);
				bool bStartGCode = false;
				bool bEndGCode = false;
				bool bEndFooter = false;
				bool bStartPoint = false;
				bool bFirstLine = false;
				bool bBedHeaterStopped = false;
				bool bEOF = false;
				string sFirstLayer = null;
				double dCurrentLayerHeight = 0;
				int intCharIndex = 0;

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
						bStartGCode = true;
						sb.AppendLine(l);
						continue;
					}

					if (l.Contains(";") & l.Contains("START Header") & !bEOF)
					{
						bStartGCode = false;
						sb.AppendLine(l);
						continue;
					}

					if (l.Contains(";") & l.Contains("START Footer") & !bEOF)
					{
						bEndGCode = true;
						sb.AppendLine(l);
						continue;
					}

					if (l.Contains(";") & l.Contains("END Footer") & !bEOF)
					{
						bEndGCode = true;
						bEndFooter = true;
						sb.AppendLine(l);
						continue;
					}

					// exit if no config should remain with the file
					if (bRemoveConfig && bEndFooter)
					{
						// if at end of footer, go to next empty line and then break;
						if (l == string.Empty & !bEOF)
						{
							bEOF = true;
							continue;
						}
						else
						{
							continue;
						}
					}

					if (bStartGCode & !bEndGCode)
					{
						//
						// Stop Bed Heater
						if (dStopBedHeater > 0)
						{
							Match matchlayerheight = Regex.Match(l, @"^(?:G1)\s(Z(\d+(\.\d+)?|\.\d+?))", RegexOptions.IgnoreCase);

							if (matchlayerheight.Success)
							{
								dCurrentLayerHeight = Convert.ToDouble(matchlayerheight.Groups[2].Value);
								Logger.LogVerbose("Current Layer Height: " + dCurrentLayerHeight + " mm");

								if (dCurrentLayerHeight >= dStopBedHeater & (bBedHeaterStopped == false))
								{
									sb.AppendLine("M140 S0; Stop Bed Heater on Layer Height " + dCurrentLayerHeight + " mm");
									sb.AppendLine("M117 Stopping Bed Heater.");

									bBedHeaterStopped = true;
									dStopBedHeater = dCurrentLayerHeight;
								}
							}
						}

						if (!bStartPoint | !bFirstLine)
						{
							if (sFirstLayer == null)
							{
								Match match0 = Regex.Match(l, @"^([gG]1)\s([zZ](-?(0|[1-9]\d*)(\.\d+)?))\s([fF](-?(0|[1-9]\d*)(\.\d+)?))(.*)$", RegexOptions.IgnoreCase);

								// Here we check the Match instance.
								if (match0.Success)
								{
									sFirstLayer = match0.Groups[2].Value;
									Logger.LogVerbose("First Layer Height: " + sFirstLayer + " mm");
									bFirstLine = true;
									continue;
								}
							}

							if (sFirstLayer != null)
							{
								Match match1 = Regex.Match(l, @"^([gG]1)\s([xX]-?(0|[1-9]\d*)(\.\d+)?)\s([yY]-?(0|[1-9]\d*)(\.\d+)?)\s([fF]-?(0|[1-9]\d*)(\.\d+)?)\s((; move to first)\s(\w+).*(point))$", RegexOptions.IgnoreCase);
								// Here we check the Match instance.
								if (match1.Success)
								{
									sb.AppendLine(l.Replace(match1.Groups[8].Value, sFirstLayer + " " + match1.Groups[8].Value));
									Logger.LogVerbose("Start Point: " + l);
									bStartPoint = true;
									continue;
								}
							}
						}

						if (l.StartsWith("M117"))
						{
							iLayer++;

							if (bProgressbar)
							{
								char chrpbar = ChrsLCDProgress[intCharIndex]; ;
								string pbar = "";

								int ipadding = (int)(((decimal)iLayer / iLayerCount) * iProgressbarWidth);
								decimal dpercentage = (decimal)iLayer / iLayerCount;

								if (IntLCDProgressPrevPadding != ipadding)
								{
									IntLCDProgressPrevPadding = ipadding;
									intCharIndex = 0;
									chrpbar = ChrsLCDProgress[0];
								}

								intCharIndex++;

								if (intCharIndex > ChrsLCDProgress.Length - 1)
								{
									intCharIndex = 0;
								}

								if (ipadding == 0)
								{
									pbar = "M117 ["
										+ chrpbar
										+ "".PadRight(iProgressbarWidth - 1, Convert.ToChar(" "))
										+ "]";
								}
								else if (iProgressbarWidth - ipadding > 0)
								{
									pbar = "M117 ["
										+ "".PadRight(ipadding, ChrLCDProgress)
										+ chrpbar
										+ "".PadRight(iProgressbarWidth - ipadding - 1, Convert.ToChar(" "))
										+ "]";
								}
								else if (dpercentage == 1)
								{
									pbar = "M117 ["
										+ "".PadRight(iProgressbarWidth, ChrLCDProgress)
										+ "]";
								}

								sb.AppendLine(pbar);
							}
							else
							{
								sb.AppendLine("M117 Layer " + iLayer + "/" + iLayerCount);
							}

							continue;
						}

						if (l.EndsWith("; skirt") | l.EndsWith(" ; brim"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.SkirtSegment);

							Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

							if (l.Contains("segType:Skirt") | InsertedSkirtSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:Skirt");
								sb.AppendLine(";Type:Skirt".ToUpper());
								sb.AppendLine(TrimComment(l));
								InsertedSkirtSegment = 1;
							}
							continue;
						}

						if (l.EndsWith("; infill"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.InfillSegment);

							Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

							if (l.Contains("segType:Infill") | InsertedInfillSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:Infill");
								sb.AppendLine(";Type:Infill".ToUpper());
								sb.AppendLine(TrimComment(l));
								InsertedInfillSegment = 1;
							}
							continue;
						}

						if (l.EndsWith("; support material interface"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.SoftSupportSegment);

							Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

							if (l.Contains("segType:SoftSupport") | InsertedSoftSupportSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:SoftSupport");
								sb.AppendLine(";Type:SoftSupport".ToUpper());
								sb.AppendLine(TrimComment(l));
								InsertedSoftSupportSegment = 1;
							}
							continue;
						}

						if (l.EndsWith("; support material"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.SupportSegment);

							Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

							if (l.Contains("segType:Support") | InsertedSupportSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:Support");
								sb.AppendLine(";Type:Support".ToUpper());
								sb.AppendLine(TrimComment(l));
								InsertedSupportSegment = 1;
							}
							continue;
						}

						if (l.EndsWith("; perimeter"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.PerimeterSegment);

							Logger.LogVerbose("".PadLeft(paddingverbose) + " -->  " + l);

							if (l.Contains("segType:Perimeter") | InsertedPerimeterSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:Perimeter");
								sb.AppendLine(";Type:Perimeter".ToUpper());
								sb.AppendLine(TrimComment(l));
								InsertedPerimeterSegment = 1;
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
					File.WriteAllText(sNewfilename, sb.ToString());

					if (bCounter & bTimestamp) bTimestamp = false;

					Logger.LogInfo("Output :");
					if (sOutputFile != null & File.Exists(sNewfilename))
					{
						if (!sOutputFile.ToLower().EndsWith("gcode")) sOutputFile += ".gcode";

						File.Delete(sOutputFile);
						if (bTimestamp)
						{
							string newfile = sOutputFile.AppendTimeStamp();
							File.Move(sNewfilename, newfile);
							PrintFileSummary(newfile);
						}
						else if (bCounter)
						{
							string newfile = sOutputFile.PrependCounter();
							File.Move(sNewfilename, newfile);
							PrintFileSummary(newfile);
						}
						else
						{
							File.Move(sNewfilename, sOutputFile);
							PrintFileSummary(sOutputFile);
						}
					}

					if (sOutputFile == null & File.Exists(sNewfilename))
					{
						File.Delete(sInputFile);
						if (bTimestamp)
						{
							string newfile = sInputFile.AppendTimeStamp();
							File.Move(sNewfilename, newfile);
							PrintFileSummary(newfile);
						}
						else if (bCounter)
						{
							string newfile = sInputFile.PrependCounter();
							File.Move(sNewfilename, newfile);
							PrintFileSummary(newfile);
						}
						else
						{
							File.Move(sNewfilename, sInputFile);
							PrintFileSummary(sInputFile);
						}
					}

					if (dStopBedHeater > 0) { Logger.LogInfo("Bed Heater disabled after height " + dStopBedHeater + " mm."); }
					if (bRemoveConfig) { Logger.LogInfo("Configuration/Settings have been removed from GCode."); }

					IntExportCounter++;
					inisettings.WriteValue("ExportCounter", "PostProcessing", IntExportCounter.ToString());
					inisettings.Save();

					string ts = ((char)('\u25a0')).ToString().PadRight(5, '\u25a0');
					Logger.LogInfo(ts + " All Done " + ts);

					//
					//
					//
					// END OF EVERYTHING

#if DEBUG
					{
						Console.WriteLine("Press any key to continue . . .");
						Console.ReadKey();
					}
#else
					System.Threading.Thread.Sleep(500);
#endif

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

						Progressbar(100 - (dt * 100 / timeout), false, timeout - dt);
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
			int iconswidth = IntConsoleWidth - 5;
			string sprog = "";
			double dnewprog = (Value != -1) ? Value : Progress / 100;
			string sprogformat = ReportAsPercentage ? String.Format("{0:P0} ", dnewprog).PadRight(5).PadLeft(10) : String.Format("{0} ", dnewprog).PadRight(5).PadLeft(10);
			//progformat = "       " + progformat;

			iconswidth -= sprogformat.Length;
			int iprogr = (int)Math.Round(Progress / 100 * iconswidth, 0);

			string mynewfunkyprogressbar =
				sprogformat +
				sprog.PadLeft(iprogr, ChrConsoleProgressbar) +
				sprog.PadLeft(iconswidth - iprogr, ChrConsoleProgressPadding);

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
			string pathname = Path.GetFullPath(System.Reflection.Assembly.GetEntryAssembly().Location);

			Console.WriteLine();
			Console.BackgroundColor = ConsoleColor.Black;
			Console.ForegroundColor = ConsoleColor.Yellow;

			string textnote = "This program is compatible with Slic3r (standalone use see below) and PrusaSlicer.";
			int paddin = (Program.IntConsoleWidth - textnote.Length) / 2;

			Console.WriteLine("".PadLeft(paddin) + textnote.PadRight(Program.IntConsoleWidth - paddin));
			Console.ResetColor();
			Console.WriteLine();
			Console.WriteLine("  Print Settings -> Output options");
			Console.WriteLine("    * Enable Verbose G-Code (!)");

			Console.WriteLine("    * Copy and paste this full filename to Post-Processing Scripts:");
			Console.WriteLine("      \"" + pathname + "\"");

			Console.WriteLine("");
			Console.WriteLine("  Printer Settings:");
			Console.WriteLine("    * Add \'; START Header\' and \'; END Header\' to your Start GCode.");
			Console.WriteLine("    * Add \'; START Footer\' and \'; END Footer\' to your End GCode.");

			Console.WriteLine();
			Console.BackgroundColor = ConsoleColor.Black;
			Console.ForegroundColor = ConsoleColor.Yellow;

			textnote = "Standalone use: Slic3rPostProcessing [OPTIONS]";
			paddin = (Program.IntConsoleWidth - textnote.Length) / 2;
			Console.WriteLine("".PadLeft(paddin) + textnote.PadRight(Program.IntConsoleWidth - paddin));

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
				InsertedInfillSegment = 0;
			}
			if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.SupportSegment)
			{
				InsertedSupportSegment = 0;
			}
			if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.PerimeterSegment)
			{
				InsertedPerimeterSegment = 0;
			}
			if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.SoftSupportSegment)
			{
				InsertedSoftSupportSegment = 0;
			}
			if (CounterNOT2Reset == -1 || CounterNOT2Reset != DonotReset.SkirtSegment)
			{
				InsertedSkirtSegment = 0;
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
				+ DateTime.Now.ToString(Program.StrTimeFormat)
				+ Path.GetExtension(fileName));
		}

		/// <summary>
		/// Adds counter to fileName
		/// </summary>
		/// <param name="fileName">Filename to add counter to</param>
		/// <param name="counter">Counter to add</param>
		/// <param name="digits">Number of digits padded with zero</param>
		/// <returns></returns>
		public static string PrependCounter(this string fileName)
		{
			string numformat = "D" + Program.IntCounterPadding.ToString();

			return Path.Combine(Path.GetDirectoryName(fileName),
				Program.IntExportCounter.ToString(numformat)
				+ "_"
				+ Path.GetFileNameWithoutExtension(fileName)
				+ Path.GetExtension(fileName));
		}
	}

	internal class Logger
	{
		public static int GetConsoleWidth()
		{
			// IntPtr myHandle = Process.GetCurrentProcess().MainWindowHandle;
			// NOW WHAT?! What do I do with myHandle? I Need the console to return
			// the width of the window.

			//return Console.WindowWidth;

			return Console.BufferWidth;
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
			try
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
			catch (Exception)
			{
			}
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