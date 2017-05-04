﻿using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;

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
			if (args.Length < 1)
			{
				// Console.WriteLine("I need an arguement; your's not good!");
				Console.WriteLine(Environment.NewLine + "This, for use with Slic3r.");
				Console.WriteLine("Slic3r - Print Settings");
				Console.WriteLine("        -> Output options");
				Console.WriteLine("        -> Enable Verbose G-Code (important!)");
				Console.WriteLine("        -> Put full filename to exe in Post-Processing Scripts.");

				Console.WriteLine(Environment.NewLine + "To use in Command line:");
				Console.WriteLine("Example: Slic3rPostProcessing.exe \"c:\\temp\\file.gcode\" [enter] ");
				Console.WriteLine(Environment.NewLine + "NOTE: Passed file will be overwritten if no output filename is passed.");
				Console.WriteLine("Example: Slic3rPostProcessing.exe \"c:\\temp\\inputfile.gcode\"  \"c:\\temp\\outputfile.gcode\" [enter] ");
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
					System.Threading.Thread.Sleep(500);
					wait++;

					if (wait > 20 * 6)
					{
						Console.WriteLine(Environment.NewLine + "Time's up! I've been waiting for a minute now.");
						Console.WriteLine(Environment.NewLine + "I'll assume, there is no " + args[0] + " and abort. Please retry, if you like, after the file actually exists.");
					}
				} while (!File.Exists(args[0]));

				var lines = File.ReadAllLines(args[0]).ToList();

				Console.WriteLine(Environment.NewLine + "Running " + args[0]);

				string newfilename = Path.Combine(Path.GetDirectoryName(args[0]), "temp_newfilename.gcode");

				ResetAllOtherCounters();
				bool StartGCode = false;
				bool EndGCode = false;
				bool StartPoint = false;
				bool FirstLine = false;
				string FirstLayer = null;

				for (int i = 0; i < lines.Count; i++)
				{
					try
					{
						string line = lines[i];

						if (line.Contains("; END Header"))
						{
							StartGCode = true;
						}

						if (line.Contains("; END Footer"))
						{
							EndGCode = true;
						}

						if (line.Contains("; # # # # # # Header"))
						{
							StartGCode = false;
						}

						if (line.Contains("; # # # # # # Footer"))
						{
							EndGCode = true;
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
										Console.WriteLine("First Layer Height: " + FirstLayer + " mm");
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
										Console.WriteLine("Start Point: " + lines[i]);
										StartPoint = true;
										continue;
									}
								}
							}

							if (line.EndsWith("; skirt") | line.EndsWith(" ; brim"))
							{
								// RESET counter
								ResetAllOtherCounters("insertedSkirtSegment");

								// Console.WriteLine(" -->  " + line);

								if (lines[insertedSkirtSegment].Contains("segType:Skirt") | lines[i - 1].Contains("segType:Skirt"))
								{
									lines[i] = line.Replace(" ; skirt", null);
									lines[i] = line.Replace(" ; brim", null);
								}
								else
								{
									lines.Insert(i, ";segType:Skirt");
									lines[i + 1] = line.Replace(" ; skirt", null);
									lines[i + 1] = line.Replace(" ; brim", null);
									insertedSkirtSegment = i;
								}
								continue;
							}

							if (line.EndsWith("; infill"))
							{
								// RESET counter
								ResetAllOtherCounters("insertedInfillSegment");

								//Console.WriteLine(" -->  " + line);

								if (lines[insertedInfillSegment].Contains("segType:Infill") | lines[i - 1].Contains("segType:Infill"))
								{
									lines[i] = line.Replace(" ; infill", null);
								}
								else
								{
									lines.Insert(i, ";segType:Infill");
									lines[i + 1] = line.Replace(" ; infill", null);
									insertedInfillSegment = i;
								}
								continue;
							}

							if (line.EndsWith("; support material interface"))
							{
								// RESET counter
								ResetAllOtherCounters("insertedSoftSupportSegment");

								//Console.WriteLine(" -->  " + line);

								if (lines[insertedSoftSupportSegment].Contains("segType:SoftSupport") | lines[i - 1].Contains("segType:SoftSupport"))
								{
									lines[i] = line.Replace(" ; support material interface", null);
								}
								else
								{
									lines.Insert(i, ";segType:SoftSupport");
									lines[i + 1] = line.Replace(" ; support material interface", null);
									insertedSoftSupportSegment = i;
								}
								continue;
							}

							if (line.EndsWith("; support material"))
							{
								// RESET counter
								ResetAllOtherCounters("insertedSupportSegment");

								//Console.WriteLine(" -->  " + line);

								if (lines[insertedSupportSegment].Contains("segType:Support") | lines[i - 1].Contains("segType:Support"))
								{
									lines[i] = line.Replace(" ; support material", null);
								}
								else
								{
									lines.Insert(i, ";segType:Support");
									lines[i + 1] = line.Replace(" ; support material", null);
									insertedSupportSegment = i;
								}
								continue;
							}

							if (line.EndsWith("; perimeter"))
							{
								// RESET counter
								ResetAllOtherCounters("insertedPerimeterSegment");

								//Console.WriteLine(" -->  " + line);

								if (lines[insertedPerimeterSegment].Contains("segType:Perimeter") | lines[i - 1].Contains("segType:Perimeter"))
								{
									lines[i] = line.Replace(" ; perimeter", null);
								}
								else
								{
									lines.Insert(i, ";segType:Perimeter");
									lines[i + 1] = line.Replace(" ; perimeter", null);
									insertedPerimeterSegment = i;
								}
								continue;
							}

							// Remove leftover comments
							if (line.Contains(" ;"))
							{
								lines[i] = line.Split(';')[0].TrimEnd();
							}
						}
					}
					catch (Exception ex)
					{
						Console.Write(ex.ToString());
						Environment.Exit(1);
						return 1;
					}
				}
				try
				{
					File.WriteAllLines(newfilename, lines);

					if (args.Length > 1)
					{
						File.Delete(args[1]);
						File.Move(newfilename, args[1]);
					}
					else
					{
						File.Delete(args[0]);
						File.Move(newfilename, args[0]);
					}

					Console.WriteLine(Environment.NewLine + "All done - Thank you.");
					Environment.Exit(0);
					return 0;
				}
				catch (Exception ex)
				{
					Console.Write(ex.ToString());
					Environment.Exit(1);
					return 1;
				}
			}
		}

		/// <summary>
		/// Resets all other Properties to their respective default.
		/// </summary>
		/// <param name="PropertyNOTToReset">Name of Property. Do NOT reset this Property!</param>
		public static void ResetAllOtherCounters(string PropertyNOTToReset = "empty")
		{
			if (PropertyNOTToReset != "insertedInfillSegment")
			{
				insertedInfillSegment = 0;
			}
			if (PropertyNOTToReset != "insertedSupportSegment")
			{
				insertedSupportSegment = 0;
			}
			if (PropertyNOTToReset != "insertedPerimeterSegment")
			{
				insertedPerimeterSegment = 0;
			}
			if (PropertyNOTToReset != "insertedSoftSupportSegment")
			{
				insertedSoftSupportSegment = 0;
			}
			if (PropertyNOTToReset != "insertedSkirtSegment")
			{
				insertedSoftSupportSegment = 0;
			}
		}
	}
}