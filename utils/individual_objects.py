# /usr/bin/python3
"""
    Split individual objects into junks of "nozzle to shroud clearance" junks.

    PrusaSlicer:    Print Settings
                        Output Options
                            Sequential Printing
                                Complete Individual Objects: check (True) -> Advanced Feature
                                Extruder Clearance:  -> Expert Feature
                                    Radius (NOZZLE radius, i.e. 4.5 mm (ø 8 Nozzle))
                                    Height (clearance from NOZZLE to SHROUD, i.e. 4 mm)
"""

#
# "cheat" pylint, because it can be annoying
# pylint: disable = line-too-long, invalid-name, broad-except
# noqa: E501
#

# import sys
import re
from decimal import Decimal
from utils import post_classes as pc


rgx = pc.MyRegex()
slcr = pc.Slic3rs()


def find_first_layer_height(lines):
    """
    Finds and returns first layer  height

    Args:
        lines (string): Line to check for  first_layer_height

    Returns:
        float: layer height
    """
    for _, item in enumerate(lines):
        if "first_layer_height" in item:
            _, value = item.split("=")
            return float(value.strip())
    return None


def is_valid_item(item, first_layer_height):
    """Check if ITEM is valid to split the gcode at

    Args:
        item (string): line of code
        first_layer_height (float): first layer height

    Returns:
        bool: True or False
    """

    return (f";Z:{first_layer_height}" in item.upper().strip()) or any(elmnt in item.strip() for elmnt in slcr.str_foothead)


def get_total_count(lst_objects):
    """ Get  total count of items in lst_objects.
        Total count over all objects.
    """
    # Count lines in lists
    total_count = 0
    for _, lst in enumerate(lst_objects):

        total_count += len(lst)

        # for _ in lst:
        #     total_count += 1
    return total_count


def sort_lists(lst_objects):
    """_summary_

    Args:
        lst_objects (_type_): _description_
    """

    sorting = []

    for c, lst in enumerate(lst_objects[1:]):

        for _, ln in reversed(list(enumerate(lst))):

            rgx_z = re.search(rgx.find_z, ln,
                              flags=re.IGNORECASE)
            if rgx_z:
                sorting.append({c, round(Decimal(rgx_z.group(1)), 8)})
                # goto_next_list = True
                break

    return sorting

    # # Enumerate over the list in reverse
    # for index, value in reversed(list(enumerate(lst_objects))):
    #     print(f"Index: {index}, Value: {value}")


def custom_sort(my_list, indices_order):
    """Sort my_list according to "template" in indices_order
    """
    return [my_list[i] for i in indices_order]


def sort_by_max_z_values(lst_objects, sort_reverse=False):
    """ Sort objects in lst_objects by height
    """

    rgx_z = re.compile(rgx.find_z, flags=re.IGNORECASE)
    sorting = []

    for c, lst in enumerate(lst_objects[1:], 1):
        q = c-1
        for ln in reversed(lst):
            regz = rgx_z.search(ln)
            if regz:
                sorting.append([q, round(Decimal(regz.group(1)), 8)])
                break

    sorting = sorted(sorting, key=lambda x: list(x)[1], reverse=sort_reverse)

    sorted_lists = custom_sort(
        lst_objects[1:], [sublist[0] for sublist in sorting])

    sorted_lists.insert(0, lst_objects[0])  # copy first list to new list

    return sorted_lists, sorting


def find_smallest_v_i(data):
    """ Find smalles value and its index in data
    """
    smallest_value = float('inf')
    smallest_index = None

    z_values = [float(re.search(r';Z:(inf|\d+\.\d+)', item).group(1))
                for item in data]

    smallest_value = min(z_values)
    smallest_index = z_values.index(smallest_value)

    return smallest_value, smallest_index


def process_split_by_block(lines, slicer, max_height=5, first_layers_first=False):
    """
        Main processing of splitting GCode into junks of max_height
    """

    print('Starting with segmenting individual objects.\nThis might take a while ...')

    lst_split_code = []
    temp_list = []
    bool_config_test = False

    first_layer_height = find_first_layer_height(lines)

    for _, item in enumerate(lines):

        if item.strip() == slcr.str_config_start[slicer]:
            bool_config_test = True

        # find "first_layer_height = ???" and use value to split gcode into objects

        if is_valid_item(item, first_layer_height):

            if not bool_config_test:
                lst_split_code.append(temp_list)
                temp_list = []
                temp_list.append(item)
            else:
                temp_list.append(item)

        else:
            temp_list.append(item)

    lst_split_code.append(temp_list)

    # create master_list with the new content
    # and add header info to master_list
    master_list = lst_split_code.pop(0)

    # get only the blocks with the parts
    # lst_objects contanins the gcode of each object as a list
    lst_objects = []
    while len(lst_split_code) > 1:
        lst_objects.append(lst_split_code.pop(0))

    #
    #
    # get max_z of each object ... and then sort shortest to tallest
    lst_objects, sorting = sort_by_max_z_values(lst_objects)

    # If max_height > than the talles object, reduce max_height = talles object + 1
    if max_height > sorting[len(sorting)-1][1]:
        max_height = float(sorting[len(sorting)-1][1]) + 1

    #

    # just make sure skip_object_id is more than objects on plate
    # don't remember why i did this....?!
    # skip_object_id = len(lst_objects) + 1

    current_z = 0.0

    # all the regex
    regx_z = re.compile(rgx.find_z, flags=re.IGNORECASE)
    regx_z_value = re.compile(rgx.find_z_value, flags=re.IGNORECASE)
    regx_safe = re.compile(rgx.pattern_safezone,  flags=re.IGNORECASE)

    while True:

        # we're done, if get_total_count(lst_objects) == 0
        if get_total_count(lst_objects) == 0:
            break

        # enum all in this list lst_objects
        # for each line in each objects "block"
        for idx, mainblocks in enumerate(lst_objects):

            # continue, if list is empty
            if len(mainblocks) == 0:
                continue

            # if skip_object_id == idx:
            #     # just make sure skip_object_id is more than objects on plate
            #     skip_object_id = len(lst_objects) + 1
            #     continue

            # find first Z in this this block
            # just to find max allowed height
            temp_z = get_new_max_height(mainblocks)

            # get index of next NONE-EMPTY object
            next_object = (idx % (len(lst_objects) - 1)) + 1

            # copy list and use temp_list
            temp_mainblocks = mainblocks.copy()

            h_factor = 1

            # Get next shorter object
            #

            # sublist of next z-values and lowest value found
            first_elements = [sublist[0]
                              if sublist else f";Z:{float('inf')}\n" for sublist in lst_objects[1:]]

            smallest_value, next_object = find_smallest_v_i(first_elements)
            next_object += 1

            ###########################

            # copy next_object list to temp_next_block
            temp_next_block = lst_objects[next_object].copy()

            # if current object is the "shortes", then h_factor = 2
            #

            ######################################################

            # wanna print first layer of all pbjects first, donntcha!?
            if first_layers_first:
                temp_max_height = temp_z
                h_factor = 1
            else:
                temp_max_height = max_height
                # TO-DO:
                # Z-factor, so we can print longer on the last object
                # this does not really work yet.

                # if idx == len(lst_objects) - 1:
                #     h_factor = 2
                #     skip_object_id = idx

            while len(temp_mainblocks) > 0:

                line = temp_mainblocks[0]

                rgx_z = regx_z.search(line)
                if rgx_z:
                    # Found ;Z:
                    current_z = round(Decimal(rgx_z.group(1)), 8)

                    if (current_z - temp_z) >= temp_max_height * h_factor:
                        # we're ready to leave this block!

                        # Inject line with a move to a safe zone!!
                        # This is the next G1 X? Y? line from the _NEXT_ object

                        s = 0

                        while True:

                            # rgz = regx_z.search(temp_next_block[0])
                            # if rgz:
                            #     asdf = rgz.group(0)
                            #     asdf = asdf.replace(";", "").replace(":", "")
                            #     print(asdf)

                            # safezone = "move to first perimeter point":
                            safezone = regx_safe.search(temp_next_block[s])

                            if safezone:
                                ln_prev = temp_next_block[s-1]
                                ln = temp_next_block[s]

# G1 X105.991 Y118.715 F9000 ; move inwards before travel
# ;LAYER_CHANGE
# ;Z:19
# ;HEIGHT:0.200001
# ;BEFORE_LAYER_CHANGE
# ;layer:94;
# M117 Layer 94;

# G1 E.61904 F3000 ; retract
# G92 E0 ; reset extrusion distance
# G1 Z19 F9000 ; move to next layer (94)             <- only, if current z is LOWER!!!
# G1 X102.944 Y117.192 ; move to first infill point   <---------------------- ?
# G1 E6 F3000 ;  ; unretract
# ;TYPE:Solid infill
# G1 F600


# TODO: Orca still crashes.... if the current object is finished before moving to the next object.
# need to find next Z of next object and move there to avoid crashes!!!!
# sometimes it moves in -Z, then to new position and this causes a crash as well ....

                                #  NOT YET WORKING - AAAAARGGHHHhhhhh
                                rgx_z1 = regx_z_value.search(ln_prev)
                                if rgx_z1:
                                    ln1 = "; injected by foreachthing\n"
                                    # ln1 += "G0 " + asdf + '\n'

                                    ln = ln.replace(
                                        rgx_z1.group(0) + " ", "") + '\n'
                                    ln += 'G1 ' + \
                                        rgx_z1.group(
                                            0) + '; move to next layer of next object\n'

                                    ln = ln1 + ln

                                master_list.append(ln)
                                break
                            s += 1

                        break

                # remove (pop) line from temp_mainblocks and append it to master_list
                master_list.append(temp_mainblocks.pop(0))

                # # finished _this_ object to the last line
                # make sure we're above the next object, becaus it could be taller!
                if idx > 0 and len(temp_mainblocks) == 1:
                    nln = "; finished this object and now move in Z some extra:"
                    extra = float(current_z)+max_height
                    nln += '\nG0 Z' + str(extra) + '\n'

                    master_list.append(nln)

            lst_objects[idx] = temp_mainblocks

        #
        # done loopging throught first round so,
        # reset first_layers_first
        first_layers_first = False

    # add rest of file. Config and so on.
    # lst_split_code.append(lst_split_code[0])

    if len(lst_split_code) > 0:
        for _, item in enumerate(lst_split_code[0]):
            master_list.append(item)

    master_list.insert(
        2, "; this file has been modded to print individual objects in blocks.\n")

    lines = master_list

    print('Done with segmented individual objects.')

    return lines


def get_new_max_height(mainblocks):
    """ get new max height in mainblocks

    Args:
        mainblocks (list): list with gcode
        temp_z (float): _description_

    Returns:
        float: _description_
    """
    temp_z = 0
    c = 0

    while True:
        rgx_z = re.search(rgx.find_z, mainblocks[c],
                          flags=re.IGNORECASE)
        if rgx_z:
            # Found ;Z:0.2
            current_z = round(Decimal(rgx_z.group(1)), 8)
            # store first current_z in temp_z
            if temp_z == 0:
                temp_z = current_z
                break
        c += 1
        if c >= len(mainblocks):
            break

    return temp_z
    #
