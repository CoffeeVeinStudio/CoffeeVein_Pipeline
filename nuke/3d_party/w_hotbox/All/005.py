#----------------------------------------------------------------------------------------------------------
#
# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX
#
# NAME: Read/Write
#
#----------------------------------------------------------------------------------------------------------

SelectedNodes = nuke.selectedNodes()

def deselectAll():
    for i in nuke.selectedNodes():
        i.knob('selected').setValue(False)

deselectAll()

for i in range(0, len(SelectedNodes)):
    if SelectedNodes[i].Class() == 'Read':
        Path = SelectedNodes[i].knob('file').value()
        fileName = Path.split('/')[-1]
        ParentPath = Path.rstrip(fileName)
        fileName = fileName.split('.')[0]
        for seq in nuke.getFileNameList(ParentPath):
            seqExt = seq.split('.')[-1]
            seqName = seq.rstrip('.'+ seqExt)
            if ('.nk' not in seq) and (fileName in seqName) and ('.mov' in seq or '.dpx' in seq or '.exr' in seq or '.jpg' in seq):
                SelectedNodes[i].knob('selected').setValue(True)
                newWrite = nuke.createNode('Write') 
                newWrite['file'].fromUserText(ParentPath + seq)
            deselectAll()
    elif SelectedNodes[i].Class() == 'Write':
        Path = SelectedNodes[i].knob('file').value()
        fileName = Path.split('/')[-1]
        ParentPath = Path.rstrip(fileName)
        fileName = fileName.split('.')[0]
        for seq in nuke.getFileNameList(ParentPath):
            SelectedNodes[i].knob('selected').setValue(True)
            xPos = SelectedNodes[i].knob('xpos').value()
            yPos = SelectedNodes[i].knob('ypos').value()
            seqExt = seq.split('.')[-1]
            seqName = seq.rstrip('.'+ seqExt)
            print(seqName)
            if ('.nk' not in seq) and (fileName in seqName) and ('.mov' in seq or '.dpx' in seq or '.exr' in seq or '.jpg' in seq):
                newRead = nuke.createNode('Read') 
                newRead['file'].fromUserText(ParentPath + seq)
                newRead['xpos'].setValue(xPos)
                newRead['ypos'].setValue(yPos + 60)
            deselectAll()
