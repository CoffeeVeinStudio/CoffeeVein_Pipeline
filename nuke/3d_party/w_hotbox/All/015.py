#----------------------------------------------------------------------------------------------------------
#
# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX
#
# NAME: Bookmark
#
#----------------------------------------------------------------------------------------------------------

for i in nuke.selectedNodes():
    if i.knob('bookmark').value():
        i.knob('bookmark').setValue(0)
    else:
        i.knob('bookmark').setValue(1)
