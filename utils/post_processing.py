""" _summary_

    Returns:
        _type_: _description_
"""

import sys
import re
import decimal
from decimal import Decimal
from utils import slicer_styles
from utils import post_classes as pc

#
# "cheat" pylint, because it can be annoying
# pylint: disable = line-too-long, invalid-name, broad-except
# noqa: E501
#


def splitbychar(mystring, mychar):
    """ Split STRING by CHAR and return first block

    Args:
        mystring (string): String to split
        mychar (string): Split by char

    Returns:
        string: First block of splitted string
    """
    # python 3: split by ; and only use first split.
    # The rest is discarded in *_, if any leftovers exist.
    abc, *_ = mystring.split(mychar)
    return abc


def obscure_configuration(strline):
    """
        Obscure _all_ settings
    """
    # the easy way out:
    strline = "; = 0\n"
    return strline


def get_first_layer_height(rgx, strline):
    """ Gets the first Layer height
    Args:
        strline (string): Current line to find Layer height info
    Returns:
        decimal: Layer height
    """
    rgx_first_layer = re.search(rgx, strline, flags=re.IGNORECASE)
    if rgx_first_layer:
        # Found ;Z:
        return format_number(Decimal(rgx_first_layer.group(1)))
    else:
        return 0


def format_number(num):
    """
        https://stackoverflow.com/a/5808014/827526
    """
    try:
        dec = Decimal(num)
    except decimal.DecimalException as ex:
        print(str(ex))
        # return f'Bad number. Not a decimal: {num}'
        return "nan"
    tup = dec.as_tuple()
    delta = len(tup.digits) + tup.exponent
    digits = ''.join(str(d) for d in tup.digits)
    if delta <= 0:
        zeros = abs(tup.exponent) - len(tup.digits)
        val = '0.' + ('0' * zeros) + digits
    else:
        val = digits[:delta] + ('0' * tup.exponent) + '.' + digits[delta:]
    val = val.rstrip('0')
    if val[-1] == '.':
        val = val[:-1]
    if tup.sign:
        return '-' + val
    return val


def process_gcodefile(args, sourcefile, lines, slicer):
    """
        MAIN Processing.
        To do with ever file from command line.
    """

    #
    # Define list of progressbar percentage and cacters
    progress_list = [[0, "."], [.25, ":"], [.5, "+"], [.75, "#"]]
    # progress_list = [[.5, "o"]]
    # progress_list = [[0, "0"], [.2, "2"], [.4, "4"], [.6, "6"], [.8, "8"]]
    #

    regex = pc.MyRegex()
    first_layer_height = 0
    b_edited_line = False
    b_skip_all = False
    b_skip_removed = False
    b_start_remove_comments = True
    b_start_add_custom_info = False
    writefile = None
    number_of_layers = 0
    current_layer = 0
    is_config_comment = True
    icount = 0

    slcr = pc.Slic3rs

    try:
        # Find total layers - search from back of file until
        # first "M117 Layer [num]" is found.
        # Store total number of layers.
        # Also, measure configuration section length.

        for line_index, strline in reversed(list(enumerate(lines))):
            if is_config_comment is True:
                # Count number of lines of the configuration section
                icount += 1
                # find beginning of configuration section

                if strline.strip() == slcr.str_config_start[int(slicer)]:
                    is_config_comment = False

            # Find last Layer:
            rgx_layer = re.search(regex.find_layer_num,
                                  strline, flags=re.IGNORECASE)
            if rgx_layer:
                number_of_layers = int(rgx_layer.group(1))
                break

        # len_lines = len(lines)
        # for line_index in range(len_lines):
        #     # start from the back
        #     strline = lines[len_lines - line_index - 1]

        #     if is_config_comment is True:
        #         # Count number of lines of the configuration section
        #         icount += 1
        #         # find beginning of configuration section
        #         if strline == "; prusaslicer_config = begin\n":
        #             is_config_comment = False

        #     # Find last Layer:
        #     rgx_layer = re.search(regex.find_layer_num,
        #                           strline, flags=re.IGNORECASE)
        #     if rgx_layer:
        #         number_of_layers = int(rgx_layer.group(1))
        #         break

    except Exception as exc:
        print("Oops! Something went wrong in finding total numbers of layers. " + str(exc))
        sys.exit(1)

    try:
        with open(sourcefile, "w", newline='\n', encoding='UTF-8') as writefile:

            # Store args in vars - easier to type, or change, add...
            argprogress = args.prog
            argprogresslayer = args.proglayer
            args_info_numlayer = args.numlayer
            argscraftwaretypes = args.craftwaretypes
            argseaseinfactor = args.easeinfactor
            argsnocuramove = args.nomove
            argsobscureconfig = args.oc
            argsprogchar = args.pchar
            argsremoveallcomments = args.rak
            argsremovecomments = args.rk
            argsxy = args.xy
            fspeed = 3000
            pwidth = int(args.pwidth)
            argsorca = args.orcaslicertypes

            # obscure configuration section, if parameter submitted:
            if argsobscureconfig:
                len_lines = len(lines)
                for line_index in range(len_lines):
                    # start from the back
                    strline = strline = lines[len_lines - line_index - 1]
                    if strline == "; prusaslicer_config = begin\n":
                        break
                    if strline != "; prusaslicer_config = end\n":
                        strline = obscure_configuration(strline)

                    lines[len_lines - line_index - 1] = strline

            # REMOVE configuration
            # del lines[len(lines)-ICOUNT:len(lines)]

            # Loop over GCODE file
            for i, strline in enumerate(lines):
                i_line_after_edit = 0

                #
                # PROGRESS-BAR in M117:
                rgxm117 = re.search(regex.find_layer_m117, strline,
                                    flags=re.IGNORECASE)

                # if --prog was passed:
                if rgxm117 and argprogress:
                    current_layer = int(rgxm117.group(1))

                    # Create progress bar on printer's display
                    # Use a different char every 0.25% progress:
                    #   Edit progress_list to get finer progress
                    filled_length = int(
                        pwidth * current_layer // number_of_layers)
                    filled_lengt_half = float(
                        pwidth * current_layer / number_of_layers - filled_length)
                    strlcase = ""
                    p2width = pwidth

                    if current_layer == 0:
                        strlcase = "1st Layer"
                        p2width = len(strlcase)
                    elif current_layer / number_of_layers < 1:
                        # check for percentage and insert corresponding char from progress_list
                        for prog_thing in enumerate(progress_list):
                            if filled_lengt_half >= (prog_thing[1])[0]:
                                strlcase = (prog_thing[1])[1]
                                p2width = pwidth - 1
                            else:
                                break

                    # assemble the progressbar (M117)
                    strline = rf'M117 [{argsprogchar * filled_length + strlcase + "." * (p2width - filled_length)}];' + '\n'

                # if --prog was NOT passed
                elif rgxm117:
                    current_layer = int(rgxm117.group(1))
                    tmppercentage = f"{((current_layer / number_of_layers) * 100):#.3g}"
                    percentage = tmppercentage[:3] \
                        if tmppercentage.endswith('.') else tmppercentage[:4]

                    if current_layer == 0:
                        strline = str.format(
                            'M117 First Layer' + '\n')
                    else:
                        if argprogresslayer:
                            strline = str.format(
                                'M117 Layer {0} of {1}' + '\n', current_layer + 1, number_of_layers + 1)
                        else:
                            strline = str.format(
                                'M117 Layer {0}, {1}%' + '\n', current_layer + 1, percentage)

                if strline and first_layer_height == 0:
                    # if strline and b_found_z == False and b_skip_all == False:
                    # Find: ;Z:0.2 and store first layer height value
                    first_layer_height = get_first_layer_height(
                        regex.find_z, strline)

                else:
                    if strline and first_layer_height != 0 and not b_skip_removed and not b_skip_all and not argsnocuramove:
                        # G1 Z.2 F7200 ; move to next layer (0)
                        # and replace with empty string
                        layerzero = re.search(
                            rf'^(?:G1)\s(?:(?:Z)([-+]?\d*(?:\.\d+)))\s(?:F({regex.find_number})?)(?:.*layer \(0\).*)$',
                            strline, flags=re.IGNORECASE)
                        if layerzero:
                            # Get the speed for moving to Z?
                            fspeed = format_number(Decimal(layerzero.group(2)))

                            # clear this line, I got no use for that one!
                            strline = ""

                            b_edited_line = True
                            b_skip_removed = True

                # add Total Layer Count to Slicer Info-Block
                if args_info_numlayer:
                    line = strline

                    if b_start_add_custom_info is False:
                        # find first "extrusion width", to make sure we're
                        # in the info-block
                        rgx_infoblock = re.search(
                            r'(?:^;\s)(?:.*)(extrusion width)', line, flags=re.IGNORECASE)

                        if rgx_infoblock:
                            if rgx_infoblock.group(1):
                                b_start_add_custom_info = True

                    else:
                        # add Total Layer Count before first empty line
                        if line == '\n':
                            line = f'; total number of layers = {number_of_layers}\n'
                            line += '\n'

                            # reset, so it won't do it anymore
                            args_info_numlayer = False

                    strline = line

                if b_edited_line and not b_skip_all and not argsnocuramove:
                    line = strline

                    # Day after PS changes **** again!!!!
                    # G1 X92.706 Y96.155 ; move to first skirt point
                    m_c = re.search(
                        rf'^((G1\sX{regex.find_number}\sY{regex.find_number})\s.*(?:(move to first).*(?:point)))', strline, flags=re.IGNORECASE)
                    if m_c:
                        # In 2.4.0b1 something changed:
                        # It was:
                        # G1 E-6 F3000 ; retract
                        # G92 E0 ; reset extrusion distance
                        # G1 Z.2 F9000 ; move to next layer (0)
                        # G1 X92.706 Y96.155 ; move to first skirt point
                        # G1 E6 F3000 ;  ; unretract

                        # But needs to be this:
                        # G1 E-6 F3000 ; retract
                        # G92 E0 ; reset extrusion distance
                        # G0 F3600 Y50 ; avoid prime blob
                        # G0 X92.706 Y96.155 F3600; just XY
                        # G0 F3600 Z3 ; Then Z3 at normal speed
                        # G0 F1200 Z0.2 ; Then to first layer height at a third of previous speed
                        # G1 E6 F3000 ;  ; unretract

                        # Replace G1 with G0: Non extruding move
                        grp2 = m_c.group(2).replace('G1', 'G0')

                        if argsxy:
                            # add first line to move to XY only
                            line += f'{grp2} F{str(fspeed)}; just XY' + '\n'

                            # check height of FIRST_LAYER_HEIGHT
                            # to make ease-in a bit safer
                            scaled_layerheight = format_number(
                                Decimal(first_layer_height) * argseaseinfactor)

                            # Then ease-in a bit ... this always gave me a heart attack!
                            #   So, depending on first layer height, drop to 15 times (default)
                            #   first layer height in mm, ...
                            line += f'G0 F{str(fspeed)} Z{str(scaled_layerheight)} ; ' \
                                'Then Z{str(scaled_layerheight)} at normal speed' + '\n'

                            #   then do the final Z-move at a third of the previous speed.
                            line += f'G0 F{str(format_number(float(fspeed)/3))} Z{str(first_layer_height)} ; ' \
                                'Then to first layer height at a third of previous speed\n'

                        else:
                            # Combined move to first skirt point.
                            # Prusa thinks driving through clips is no issue!
                            line += f'{grp2} Z{str(first_layer_height)} F{str(fspeed)} ; ' \
                                'move to first skirt/support point\n'

                        b_edited_line = False
                        b_skip_all = True
                        b_start_remove_comments = True
                        i_line_after_edit = i + 1

                    strline = line

                # Replace TYPES to view CGode in "other" Viewers
                if strline.startswith(";TYPE:"):
                    strtype = strline.replace(";TYPE:", "").lower().strip()

                    # Replace PrusaSlicer terms with CraftWare descriptions
                    # If desired.
                    if argscraftwaretypes:
                        for x_var, y_var in slicer_styles.craft_replace:
                            if strtype == str(y_var).lower():
                                strline = f";segType:{x_var}\n;TYPE:{y_var}\n"
                                break

                    # if sliced with OrcaSlicer, replace types
                    if argsorca:
                        for x_var, y_var in slicer_styles.orca_replace:
                            if strtype == str(x_var).lower():
                                # strline = f";TYPE:{x_var}\n;TYPE:{y_var}\n"
                                strline = f";TYPE:{y_var}\n"
                                break

                if (i + 1) > i_line_after_edit and argsremovecomments and b_start_remove_comments:
                    if strline.startswith("; prusaslicer_config"):
                        b_start_remove_comments = False
                    if not strline.lstrip().startswith(';'):
                        # remove tabs and strip spaces as well
                        strline = splitbychar(strline, ';').replace(
                            '\t', '').strip() + '\n'

                # Remove all lines starting with ; (comment)!
                if argsremoveallcomments:
                    if strline.lstrip().startswith(';') or strline.lstrip().startswith('\n'):
                        strline = ""
                    else:
                        # remove tabs and strip spaces as well
                        strline = splitbychar(strline, ';').replace(
                            '\t', '').strip() + '\n'

                #
                # Write line back to file
                writefile.write(strline)

    except Exception as exc:
        print("Oops! Something went wrong. " + str(exc))
        sys.exit(1)

    finally:
        writefile.close()
        # readfile.close()
        print("Done with post-processing.")
