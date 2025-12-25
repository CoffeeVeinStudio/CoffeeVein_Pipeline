#----------------------------------------------------------------------------------------------------------
#
# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX
#
# NAME: Toggle Input Process
#
#----------------------------------------------------------------------------------------------------------

#Author: Christoffer von Sydow | Coffee Vein Studio AB | 2025-05-12 | v1.0

viewer_node = nuke.activeViewer().node()
if viewer_node['input_process'].value() == False:
    viewer_node['input_process'].setValue(True)
else:
    viewer_node['input_process'].setValue(False)