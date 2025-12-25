#----------------------------------------------------------------------------------------------------------
#
# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX
#
# NAME: Chain TransformMasked
#
#----------------------------------------------------------------------------------------------------------

def deselectAll():
    for i in nuke.selectedNodes():
        i.knob('selected').setValue(False)

deselectAll()


#creation
transformMaskedNode=nuke.createNode('TransformMasked', inpanel=False)
deselectAll()
rotoNode=nuke.createNode('Roto', inpanel=True)
blurNode=nuke.createNode('Blur', inpanel=False)


#Connection
transformMaskedNode.setInput(1, blurNode)
rotoNode.setInput(0, None)
blurNode.setInput(0, rotoNode)


tmXpos = transformMaskedNode.xpos()
tmYpos = transformMaskedNode.ypos()

blurNode.setXYpos(tmXpos--110, tmYpos)
rotoNode.setXYpos(tmXpos--110, tmYpos-+39)


#Settings
blurNode.knob('size').setValue(5)


#Selection
blurNode.knob('selected').setValue(True)
rotoNode.knob('selected').setValue(True)
transformMaskedNode.knob('selected').setValue(True)

