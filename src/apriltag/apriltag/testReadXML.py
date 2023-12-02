import os
import xml.etree.ElementTree as ET

# Get the current working directory
current_dir = os.getcwd()

# Specify the relative path to the file
relative_path = "src/apriltag/apriltag/apriltag_location_ucf.urdf.xarco"

# Join the current directory with the relative path to get the full file path
file_path = os.path.join(current_dir, relative_path)

tree = ET.parse(file_path)

root = tree.getroot()

print(root.tag)

# Find the XYZ information
# tag = root.find("link.tag = base_tag_1" + "/visual/origin[@xyz]")
# print(tag.attrib["xyz"])
root = root[0]
xyz_elements = root.findall(".//origin[@rpy]")
xyz_values = [element.attrib["rpy"] for element in xyz_elements]

# Print the XYZ information
for xyz in xyz_values:
    print(xyz.split(" ")[0])
