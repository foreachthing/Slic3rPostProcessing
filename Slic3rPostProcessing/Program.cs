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

		public static string strTimeformat = "HHmmss-yyyyMMdd";

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
			if (Properties.Settings.Default._UpdateRequired == true)
			{
				Properties.Settings.Default.Upgrade();
				Properties.Settings.Default._UpdateRequired = false;
				Properties.Settings.Default.Save();
			}

			bool show_help = false;

			int verbosity = 3;
			double repprogress = 5d;
			string strINputFile = null;
			string strOUTputFile = null;

			bool booTimestamp = false;
			bool booCounter = true;
			bool booResetCounter = false;

			var p = new OptionSet() {
				{ "i|input=", "The {INPUTFILE} to process.",
					v => strINputFile=v },

				{ "o|output=", "The {OUTPUTFILE} filename. \n Optional. {INPUTFILE} will get overwritten if {OUTPUTFILE} is not specified.",
					v => strOUTputFile=v },

				{ "r|repprog=", "Report progress ever {PROG} percentage. Default "+ repprogress +".",
					(double iprog) => repprogress=(iprog >= 1 & iprog<=100 ? iprog : repprogress ) },

				{ "t|timestamp=","Adds a timestamp to the END of the filename.\n {+ or -}; Default = -",
					t => booTimestamp = t != null },

				{ "c|counter=","Adds an export-counter to the FRONT of the filename.\n {+ or -}; Default = + \n If the timestamps is set to true, too, then only the counter will be added.",
					t => booCounter = t != null },

				{ "f|formatstamp=","{FORMAT} of the timestamp. \n Default: " + strTimeformat,
					tf => strTimeformat = tf },

				{ "v|verbosity=", "Debug message verbosity. Default: "+ verbosity +". \n {INT}:\n 0 = Off \n 1 = Error \n 2 = Warning \n 3 = Info \n 4 = Verbose (will output EVER line of GCode! There will be LOTS of output!)",
					(int v) => { if ( v >= 0 & v <5) verbosity = v; } },

				{ "h|help",  "Show this message and exit. Nothing will be done.",
					v => show_help = v != null },

				{ "resetcounter=","Reset export-counter to zero and exit.",
					t => booResetCounter = t != null },
			};

			List<string> extra;
			try
			{
				extra = p.Parse(args);

				if (extra.Count == 1 & args.Length == 1)
				{
					if (extra[0].ToLower().EndsWith("gcode"))
					{
						strINputFile = extra[0];
					}
				}
			}
			catch (OptionException e)
			{
				Logger.LogError(e.Message);
				ShowHelp(p);
				Environment.Exit(1);
				return 1;
			}

			////// / / / / / / / / / / / / /
			// Log writer START
			Trace.AutoFlush = true;
			Logger.traceSwitch.Level = (TraceLevel)verbosity;//TraceLevel.Info;
			Trace.Listeners.Clear();

			TextWriterTraceListener listener = new TextWriterTraceListener(Console.Out);
			Trace.Listeners.Add(listener);

			if (show_help)
			{
				ShowHelp(p);
				Environment.Exit(1);
				return 1;
			}

			if (booResetCounter)
			{
				Properties.Settings.Default.export_counter = 0;
				Properties.Settings.Default.Save();
				Environment.Exit(1);
				return 1;
			}

			if (strINputFile == null)
			{
				// Console.WriteLine("I need an arguement; your's not good!");
				ShowHelp(p);
				Environment.Exit(1);
				return 1;
			}
			else
			{
				int wait = 0;
				do
				{
					// wait here until the file exists.
					// It can take some time to copy the .tmp to .gcode.
					if (wait > 20)
					{
						System.Threading.Thread.Sleep(new TimeSpan(0, 0, 1));
					}
					else
					{
						System.Threading.Thread.Sleep(50);
					}
					wait++;

					if (wait > 20 * 3 * 5)
					{
						Logger.LogInfo("I assume there is no " + strINputFile + " and abort. Please retry, if you like, after the file actually exists.");
					}
				} while (!File.Exists(strINputFile));

				var lines = File.ReadAllLines(strINputFile).ToList();
				int cLines = lines.Count;

				Logger.LogInfo("Running " + strINputFile);

				NumberFormatInfo nfi = new CultureInfo("de-CH", false).NumberFormat;
				nfi.NumberDecimalDigits = 0;
				Logger.LogInfo((cLines - 1).ToString("N", nfi) + " lines of gcode will be processed.");

				string newfilename = Path.Combine(Path.GetDirectoryName(strINputFile), Guid.NewGuid().ToString().Replace("-", "") + ".gcode_temp");

				ResetAllCountersButThis(DonotReset.AllReverseNone);
				bool StartGCode = false;
				bool EndGCode = false;
				bool StartPoint = false;
				bool FirstLine = false;
				string FirstLayer = null;
				int repprogint = (int)(cLines * repprogress / 100);
				int repnewprog = repprogint;

				int q = -1;

				StringBuilder sb = new StringBuilder();

				// Count all Layers
				int iLayerCount = 0;
				foreach (string l in lines)
				{
					if (l.Contains(";layer:") && (!l.Contains("before_layer_gcode")))  //("; END Header"))
					{
						iLayerCount++;
					}
				}

				int iLayer = 0;
				foreach (string l in lines)
				{
					Logger.LogVerbose((q + 1).ToString("N", nfi) + ": " + l);

					q++;

					if (q == repnewprog)
					{
						Double progress = (Double)q / (Double)cLines;
						Logger.LogInfo("Progress: " + Math.Round(progress * 100d, 0) + "%");
						repnewprog += repprogint;
					}

					if (l.Contains(";layer:0;"))  //("; END Header"))
					{
						StartGCode = true;
						sb.AppendLine(l);
						continue;
					}

					if (l.Contains("; END Footer"))
					{
						EndGCode = true;
						sb.AppendLine(l);
						continue;
					}

					if (l.Contains("; # # # # # # Header"))
					{
						StartGCode = false;
						sb.AppendLine(l);
						continue;
					}

					if (l.Contains("; # # # # # # Footer"))
					{
						EndGCode = true;
						sb.AppendLine(l);
						continue;
					}

					if (StartGCode == true & EndGCode == false)
					{
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

							Logger.LogVerbose(" -->  " + l);

							if (l.Contains("segType:Skirt") | insertedSkirtSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:Skirt");
								sb.AppendLine(TrimComment(l));
								insertedSkirtSegment = 1;
							}
							continue;
						}

						if (l.EndsWith("; infill"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.InfillSegment);

							Logger.LogVerbose(" -->  " + l);

							if (l.Contains("segType:Infill") | insertedInfillSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:Infill");
								sb.AppendLine(TrimComment(l));
								insertedInfillSegment = 1;
							}
							continue;
						}

						if (l.EndsWith("; support material interface"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.SoftSupportSegment);

							Logger.LogVerbose(" -->  " + l);

							if (l.Contains("segType:SoftSupport") | insertedSoftSupportSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:SoftSupport");
								sb.AppendLine(TrimComment(l));
								insertedSoftSupportSegment = 1;
							}
							continue;
						}

						if (l.EndsWith("; support material"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.SupportSegment);

							Logger.LogVerbose(" -->  " + l);

							if (l.Contains("segType:Support") | insertedSupportSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:Support");
								sb.AppendLine(TrimComment(l));
								insertedSupportSegment = 1;
							}
							continue;
						}

						if (l.EndsWith("; perimeter"))
						{
							// RESET counter
							ResetAllCountersButThis(DonotReset.PerimeterSegment);

							Logger.LogVerbose(" -->  " + l);

							if (l.Contains("segType:Perimeter") | insertedPerimeterSegment != 0)
							{
								sb.AppendLine(TrimComment(l));
							}
							else
							{
								sb.AppendLine(";segType:Perimeter");
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
					System.IO.File.WriteAllText(newfilename, sb.ToString());

					if (booCounter & booTimestamp)
					{
						booTimestamp = false;
					}

					if (strOUTputFile != null & File.Exists(newfilename))
					{
						File.Delete(strOUTputFile);
						if (booTimestamp)
						{
							string newfile = strOUTputFile.AppendTimeStamp();
							File.Move(newfilename, newfile);
							Logger.LogInfo("File written: " + newfile);
						}
						else if (booCounter)
						{
							string newfile = strOUTputFile.PrependCounter();
							File.Move(newfilename, strOUTputFile.PrependCounter());
							Logger.LogInfo("File written: " + newfile);
						}
						else
						{
							File.Move(newfilename, strOUTputFile);
							Logger.LogInfo("File written: " + strOUTputFile);
						}
					}

					if (strOUTputFile == null & File.Exists(newfilename))
					{
						File.Delete(strINputFile);
						if (booTimestamp)
						{
							string newfile = strINputFile.AppendTimeStamp();
							File.Move(newfilename, newfile);
							Logger.LogInfo("File written: " + newfile);
						}
						else if (booCounter)
						{
							string newfile = strINputFile.PrependCounter();
							File.Move(newfilename, newfile);
							Logger.LogInfo("File written: " + newfile);
						}
						else
						{
							File.Move(newfilename, strINputFile);
							Logger.LogInfo("File written: " + strINputFile);
						}
					}

					Logger.LogInfo("All done - Thank you. Will close now ... ");

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
					ShowHelp(p);
					Environment.Exit(1);
					return 1;
				}
			}
		}

		private static string TrimComment(string line)
		{
			char[] TrimChars = new char[] { ' ' };

			if (line.Contains(";"))
			{
				line = line.Split(';')[0].TrimEnd(TrimChars);
			}

			return line;
		}

		private static void ShowHelp(OptionSet p)
		{
			Console.WriteLine();
			Console.WriteLine("This program is for use with Slic3r or standalone.");
			Console.WriteLine();
			Console.WriteLine("Slic3r  -> Print Settings -> Output options");
			Console.WriteLine("        * Enable Verbose G-Code (!)");
			Console.WriteLine("        * Put full filename to " + Path.GetFileName(System.Reflection.Assembly.GetEntryAssembly().Location) + " in Post-Processing Scripts.");
			Console.WriteLine("        Current filename: \"" + System.Reflection.Assembly.GetEntryAssembly().Location + "\"");

			Console.WriteLine();
			Console.WriteLine("Standalone usage: Slic3rPostProcessing [OPTIONS]");
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

		public static string PrependCounter(this string fileName)
		{
			int counter = Properties.Settings.Default.export_counter;

			Properties.Settings.Default.export_counter++;
			Properties.Settings.Default.Save();

			return Path.Combine(Path.GetDirectoryName(fileName),
				counter.ToString("D6")
				+ "_"
				+ Path.GetFileNameWithoutExtension(fileName)
				+ Path.GetExtension(fileName));
		}
	}

	internal class Logger
	{
		public static void LogInfo(string message)
		{
			Trace.WriteLineIf(Logger.traceSwitch.TraceInfo, "Info : " + message);
		}

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
			Trace.WriteLineIf(Logger.traceSwitch.TraceWarning, "WARNING : " + message);
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