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
		public static int insertedSkirtSegment { get; set; }
		public static int insertedInfillSegment { get; set; }
		public static int insertedSupportSegment { get; set; }
		public static int insertedSoftSupportSegment { get; set; }
		public static int insertedPerimeterSegment { get; set; }

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
			bool show_help = false;
			bool debugger = false;
			int verbosity = 3;
			int repprogress = 5;
			string strINputFile = null;
			string strOUTputFile = null;

			var p = new OptionSet() {
				{ "i|input=", "The {INPUTFILE} to process.",
					v => strINputFile=v },
				{ "o|output=", "The {OUTPUTFILE} to copy the processed content to (optional).",
					v => strOUTputFile=v },
				{ "h|help",  "Show this message and exit. Nothing will be done.",
					v => show_help = v != null },
				{ "d|debug",  "Show debug info if set to true. Default: false.",
					v => debugger = v != null },
				{ "v|verbosity=", "Debug message verbosity (0 to 4). Default: 3 (Info). 0 = Off; 1 = Error; 2 = Warning; 3 = Info; 4 = Verbose (will output EVER line of GCode! There will be LOTS of output!)",
					(int v) => { if ( v >= 0 & v <5) verbosity = v; } },
				{ "p|progress=", "Report progress ever {PROGRESS} percentage. Default 5.",
					(int v) => { if ( v >= 0 & v <=100) repprogress = v; } },
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

			//Logger.LogInfo(strINputFile);
			//Console.WriteLine("Press any key to continue . . .");
			//Console.ReadKey();

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

					if (wait > 20 * 6)
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
				string line = null;
				int repprogint = cLines * repprogress / 100;
				int repnewprog = repprogint;

				for (int i = 0; i < cLines - 1; i++)
				{
					try
					{
						line = lines[i];
						Logger.LogVerbose((i + 1).ToString("N", nfi) + ": " + line);

						if (i == repnewprog)
						{
							Double progress = (Double)i / (Double)cLines;

							Logger.LogInfo("Progress: " + Math.Round(progress * 100d, 0) + "%");
							repnewprog += repprogint;
						}

						if (line.Contains(";layer:0;"))
						{
							StartGCode = true;
							continue;
						}

						if (line.Contains("; END Footer"))
						{
							EndGCode = true;
							continue;
						}

						if (line.Contains("; # # # # # # Header"))
						{
							StartGCode = false;
							continue;
						}

						if (line.Contains("; # # # # # # Footer"))
						{
							EndGCode = true;
							continue;
						}

						if (StartGCode == true & EndGCode == false)
						{
							if (!StartPoint | !FirstLine)
							{
								if (FirstLayer == null)
								{
									Match match0 = Regex.Match(line, @"^([gG]1)\s([zZ](-?(0|[1-9]\d*)(\.\d+)?))\s([fF](-?(0|[1-9]\d*)(\.\d+)?))(.*)$", RegexOptions.IgnoreCase);

									// Here we check the Match instance.
									if (match0.Success)
									{
										FirstLayer = match0.Groups[2].Value;
										Logger.LogVerbose("First Layer Height: " + FirstLayer + " mm");
										lines.RemoveAt(i);
										i -= 1;
										FirstLine = true;
										continue;
									}
								}

								if (FirstLayer != null)
								{
									Match match1 = Regex.Match(line, @"^([gG]1)\s([xX]-?(0|[1-9]\d*)(\.\d+)?)\s([yY]-?(0|[1-9]\d*)(\.\d+)?)\s([fF]-?(0|[1-9]\d*)(\.\d+)?)\s((; move to first)\s(\w+).*(point))$", RegexOptions.IgnoreCase);
									// Here we check the Match instance.
									if (match1.Success)
									{
										lines[i] = line.Replace(match1.Groups[8].Value, FirstLayer + " " + match1.Groups[8].Value);
										Logger.LogVerbose("Start Point: " + lines[i]);
										StartPoint = true;
										continue;
									}
								}
							}

							if (line.EndsWith("; skirt") | line.EndsWith(" ; brim"))
							{
								// RESET counter
								ResetAllCountersButThis(DonotReset.SkirtSegment);

								Logger.LogVerbose(" -->  " + line);

								if (lines[insertedSkirtSegment].Contains("segType:Skirt") | lines[i - 1].Contains("segType:Skirt"))
								{
									lines[i] = TrimComment(line);
								}
								else
								{
									lines[i] = ";segType:Skirt" + Environment.NewLine + TrimComment(line);

									insertedSkirtSegment = i;
								}
								continue;
							}

							if (line.EndsWith("; infill"))
							{
								// RESET counter
								ResetAllCountersButThis(DonotReset.InfillSegment);

								Logger.LogVerbose(" -->  " + line);

								if (lines[insertedInfillSegment].Contains("segType:Infill") | lines[i - 1].Contains("segType:Infill"))
								{
									lines[i] = TrimComment(line);// line.Replace(" ; infill", null);
								}
								else
								{
									lines[i] = ";segType:Infill" + Environment.NewLine + TrimComment(line);
									insertedInfillSegment = i;
								}
								continue;
							}

							if (line.EndsWith("; support material interface"))
							{
								// RESET counter
								ResetAllCountersButThis(DonotReset.SoftSupportSegment);

								Logger.LogVerbose(" -->  " + line);

								if (lines[insertedSoftSupportSegment].Contains("segType:SoftSupport") | lines[i - 1].Contains("segType:SoftSupport"))
								{
									lines[i] = TrimComment(line);//line.Replace(" ; support material interface", null);
								}
								else
								{
									lines[i] = ";segType:SoftSupport" + Environment.NewLine + TrimComment(line);
									insertedSoftSupportSegment = i;
								}
								continue;
							}

							if (line.EndsWith("; support material"))
							{
								// RESET counter
								ResetAllCountersButThis(DonotReset.SupportSegment);

								Logger.LogVerbose(" -->  " + line);

								if (lines[insertedSupportSegment].Contains("segType:Support") | lines[i - 1].Contains("segType:Support"))
								{
									lines[i] = TrimComment(line);//line.Replace(" ; support material", null);
								}
								else
								{
									lines[i] = ";segType:Support" + Environment.NewLine + TrimComment(line);
									insertedSupportSegment = i;
								}
								continue;
							}

							if (line.EndsWith("; perimeter"))
							{
								// RESET counter
								ResetAllCountersButThis(DonotReset.PerimeterSegment);

								Logger.LogVerbose(" -->  " + line);

								if (lines[insertedPerimeterSegment].Contains("segType:Perimeter") | lines[i - 1].Contains("segType:Perimeter"))
								{
									lines[i] = TrimComment(line);//line.Replace(" ; perimeter", null);
								}
								else
								{
									lines[i] = ";segType:Perimeter" + Environment.NewLine + TrimComment(line);
									insertedPerimeterSegment = i;
								}
								continue;
							}

							// Remove any leftover comments
							lines[i] = TrimComment(line);
						}
					}
					catch (Exception ex)
					{
						Console.Write(ex.ToString());

#if DEBUG
						{
							Logger.LogWarning(ex.ToString());
							Console.WriteLine("Press any key to continue . . .");
							Console.ReadKey();
						}
#endif

						Environment.Exit(1);
						return 1;
					}
				}
				try
				{
					File.WriteAllLines(newfilename, lines);

					if (strOUTputFile != null & File.Exists(newfilename))
					{
						File.Delete(strOUTputFile);
						File.Move(newfilename, strOUTputFile);
					}

					if (strOUTputFile == null & File.Exists(newfilename))
					{
						File.Delete(strINputFile);
						File.Move(newfilename, strINputFile);
					}

					Logger.LogInfo("All done - Thank you. Will close soone ... ");

#if DEBUG
					{
						Console.WriteLine("Press any key to continue . . .");
						Console.ReadKey();
					}
#else
					System.Threading.Thread.Sleep(3000);
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
			if (line.Contains(";"))
			{
				line = line.Split(';')[0].TrimEnd();
			}

			return line;
		}

		private static void ShowHelp(OptionSet p)
		{
			Console.WriteLine();
			Console.WriteLine("This program is for use with Slic3r or standalone.");
			Console.WriteLine("Slic3r - Print Settings");
			Console.WriteLine("        -> Output options");
			Console.WriteLine("        -> Enable Verbose G-Code (important!)");
			Console.WriteLine("        -> Put full filename to exe and ` --i=` in Post-Processing Scripts.");
			Console.WriteLine("        Example: c:\\temp\\Slic3rPostProcessing --i=");

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

	internal class Logger
	{
		public static void LogInfo(string message)
		{
			Trace.WriteLineIf(Logger.traceSwitch.TraceInfo, "INFO : " + message);
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
			Trace.WriteLineIf(Logger.traceSwitch.TraceVerbose, "VERBOSE : " + message);
		}

		public static TraceSwitch traceSwitch = new TraceSwitch("Application", "Application");
	}
}