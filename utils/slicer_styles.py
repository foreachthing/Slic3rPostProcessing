"""
    These are the different Slicer-Types

    Create a new one for each different Slicer

"""

# replace OrcaSlicer Types with PrusaSlicer Types as well
orca_replace = [
    ("Skirt", "Skirt/Brim"),
    ("Brim", "Skirt/Brim"),
    ("Support interface", "Support material interface"),
    ("Support", "Support material"),
    ("Sparse infill", "Internal infill"),
    ("Internal solid infill", "Solid infill"),
    ("Bridge", "Bridge infill"),
    ("Overhang wall", "Overhang perimeter"),
    ("Bottom surface", "Solid infill"),
    ("Top surface", "Top solid infill"),
    ("Outer wall", "External perimeter"),
    ("Inner wall", "Perimeter"),
]

# add CraftWare Types to PrusaSlicer Types
craft_replace = [
    ("Skirt/Brim", "Skirt"),
    ("Support material interface", "SoftSupport"),
    ("Support material", "Support"),
    ("Solid infill", "Infill"),
    ("Internal solid infill", "Solid infill"),
    ("Gap fill", "Perimeter"),
    ("External perimeter", "Perimeter"),
    ("Perimeter", "Loop")
]
