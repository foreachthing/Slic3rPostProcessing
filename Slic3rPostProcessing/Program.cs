using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace Slic3rPostProcessing
{
	internal class Program
	{
		private static void Main(string[] args)
		{
			string newfilename = Path.Combine(Path.GetDirectoryName(args[0]), "temp_newfilename.gcode");

			if (args.Length != 1)
			{
				// Environment.Exit(0);
			}
			else
			{
				var lines = File.ReadAllLines(args[0]).ToList();

				Console.WriteLine("Running " + args[0]);

				int insertedSkirtSegment = 0;
				int insertedInfillSegment = 0;
				int insertedSupportSegment = 0;
				int insertedPerimeterSegment = 0;
				bool StartGCode = false;
				bool EndGCode = false;

				for (int i = 0; i < lines.Count; i++)
				{
					try
					{
						string line = lines[i];

						if (line.Contains(";layer:0;") | line.Contains("; filament used"))
						{
							StartGCode = true;
						}

						if (line.Contains("; filament used"))
						{
							EndGCode = true;
						}

						if (StartGCode == true & EndGCode == false)
						{
							if (line.Contains("; move to first infill point"))
							{
								lines[i] = line.Replace(" ; move to first infill point", null);
							}

							if (line.Contains("; skirt"))
							{
								// RESET counter
								insertedInfillSegment = 0;
								insertedSupportSegment = 0;
								insertedPerimeterSegment = 0;

								// Console.WriteLine(" -->  " + line);

								if (lines[insertedSkirtSegment].Contains("segType:Skirt") | lines[i - 1].Contains("segType:Skirt"))
								{
									lines[i] = line.Replace(" ; skirt", null);
								}
								else
								{
									lines.Insert(i, ";segType:Skirt");
									lines[i + 1] = line.Replace(" ; skirt", null);
									insertedSkirtSegment = i;
								}
							}

							if (line.Contains("; infill"))
							{
								// RESET counter
								insertedSkirtSegment = 0;
								insertedSupportSegment = 0;
								insertedPerimeterSegment = 0;

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
							}

							if (line.Contains("; support material"))
							{
								// RESET counter
								insertedSkirtSegment = 0;
								insertedInfillSegment = 0;
								insertedPerimeterSegment = 0;

								//Console.WriteLine(" -->  " + line);

								if ((lines[insertedSupportSegment].Contains("segType:Support") | lines[i - 1].Contains("segType:Support")) | (lines[insertedSupportSegment].Contains("segType:SoftSupport") | lines[i - 1].Contains("segType:SoftSupport")))
								{
									if (line.Contains("; support material interface"))
									{
										lines[i] = line.Replace(" ; support material interface", null);
									}
									else
									{
										lines[i] = line.Replace(" ; support material", null);
									}
								}
								else
								{
									if (line.Contains("; support material interface"))
									{
										lines.Insert(i, ";segType:SoftSupport");
										lines[i + 1] = line.Replace(" ; support material interface", null);
									}
									else
									{
										lines.Insert(i, ";segType:Support");
										lines[i + 1] = line.Replace(" ; support material", null);
									}

									insertedSupportSegment = i;
								}
							}

							if (line.Contains("; perimeter"))
							{
								// RESET counter
								insertedSkirtSegment = 0;
								insertedInfillSegment = 0;
								insertedSupportSegment = 0;

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
							}
						}
					}
					catch (Exception ex)
					{
						Console.Write(ex.ToString());
					}
				}
				try
				{
					File.WriteAllLines(newfilename, lines);
					File.Delete(args[0]);
					File.Move(newfilename, args[0]);
				}
				catch (Exception ex)
				{
					Console.Write(ex.ToString());
				}
			}
		}
	}
}