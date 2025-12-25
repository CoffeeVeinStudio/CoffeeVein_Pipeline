#----------------------------------------------------------------------------------------------------------
#
# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX
#
# NAME: Bounding box B
#
#----------------------------------------------------------------------------------------------------------

for i in nuke.selectedNodes():
    print(i)
    if i.Class() == 'Merge2':
        i.knob('bbox').setValue(3)
    if i.Class() == 'Copy':
        i.knob('bbox').setValue(1)
    if i.Class() == 'Keymix':
        i.knob('bbox').setValue(1)