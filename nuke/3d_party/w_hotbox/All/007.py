#----------------------------------------------------------------------------------------------------------
#
# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX
#
# NAME: Mix Toggle
#
#----------------------------------------------------------------------------------------------------------

for i in nuke.selectedNodes():
    i.knob('mix').setAnimated() 
    if i.knob('mix').value() == 1:
        i.knob('mix').setValue(0)
    else:       
        i.knob('mix').setValue(1)