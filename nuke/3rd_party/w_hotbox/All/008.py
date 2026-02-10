#----------------------------------------------------------------------------------------------------------
#
# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX
#
# NAME: Link Knobs
#
#----------------------------------------------------------------------------------------------------------

import nukescripts
global nukescripts
global SelectedNodes
global KnobListParent
global KnobListChild

def deselectAll():
    for i in nuke.selectedNodes():
        i.knob('selected').setValue(False)


SelectedNodes = nuke.selectedNodes()
excludedKnobs = ['lifetimeEnd', 'disable', 'enable', 'help', 'selected', 'dope_sheet', 'hide_input', 'note_font_color', 'note_font', 'note_font_size', 'knobChanged', 'onCreate', 'onDestroy', 'updateUI', 'panel', 'tile_color', 'bookmark', 'autolabel', 'label', 'lifetimeStart', 'indicators', 'icon', 'cached', 'inject', 'postage_stamp_frame', 'postage_stamp', 'gl_color', 'fringe', 'process_mask', 'xpos', 'ypos', 'useLifetime', 'Mask']

KnobListParent = []
KnobListChild = []
for i in range(0, len(SelectedNodes)):
        if i == 0:
            KnobsParent = SelectedNodes[0].knobs().keys()
            for a in KnobsParent:
                if a not in KnobListParent and a not in excludedKnobs:
                    KnobListParent.append(a)
        else:
            KnobsChild = SelectedNodes[i].knobs().keys()
            for b in KnobsChild:
                if b not in KnobListChild and b not in excludedKnobs:
                    KnobListChild.append(b)

KnobListParent.sort()
KnobListChild.sort()

class KnobsOfSelected(nukescripts.PythonPanel):
    def __init__(self, foo=None):
        nukescripts.PythonPanel.__init__( self, 'Knobs of Selected Nodes', 'net.dshng.Knobs')
        self.create_gui()

    def create_gui(self):
        if len(SelectedNodes) <= 2:
            self.knobListLeft = nuke.Enumeration_Knob("KnobsChild", 'From(' + SelectedNodes[1].knob('name').value() +')', KnobListChild)
            self.knobListRight = nuke.Enumeration_Knob("KnobsParent", 'To(' + SelectedNodes[0].knob('name').value() +')', KnobListParent)
        else:
            self.knobListLeft = nuke.Enumeration_Knob("KnobsChild", 'From(Selection)', KnobListChild)
            self.knobListRight = nuke.Enumeration_Knob("KnobsParent", 'To(' + SelectedNodes[0].knob('name').value() +')', KnobListParent)
        self.addKnob(self.knobListLeft)
        self.addKnob(self.knobListRight)

    def knobChanged(self, knob):
        global ControlKnob
        global SlaveKnob
        if knob is self.knobListLeft:
            SlaveKnob = knob.value()
            if SlaveKnob in KnobListParent:
                self.knobListRight.setValue(SlaveKnob)
                ControlKnob = self.knobListRight.value()
        if knob is self.knobListRight:
            ControlKnob = knob.value()

if KnobsOfSelected('').showModalDialog():    
    for i in range(0, len(SelectedNodes)):
        if i != 0:
            SelectedNodes[i].knob(SlaveKnob).setExpression(SelectedNodes[0].knob('name').value() + '.' + ControlKnob)
    
deselectAll()