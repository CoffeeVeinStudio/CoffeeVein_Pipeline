import nuke


######## INPUTS ########
def ingest(x:float):
    nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/ingest.nk')
    for node in nuke.selectedNodes():
        node['xpos'].setValue(node['xpos'].value()+x)
        node['selected'].setValue(False)
    x=x+2500
    y=-900
    return(x,y)

def denoise(x:float, y:float):
   nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/denoise.nk')
   for node in nuke.selectedNodes():
       node['xpos'].setValue(node['xpos'].value()+x)
       node['ypos'].setValue(node['ypos'].value()+y)
       node['selected'].setValue(False)
   x=x+1100
   y=800
   return(x,y)

def camAndScene(x:float, y:float):
   nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/3D.nk')
   for node in nuke.selectedNodes():
       node['xpos'].setValue(node['xpos'].value()+x)
       node['ypos'].setValue(node['ypos'].value()+y)
       node['selected'].setValue(False)
   x=x+1000
   y=800
   return(x,y)

def elements(x:float):
    nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/elements.nk')
    for node in nuke.selectedNodes():
        node['xpos'].setValue(node['xpos'].value()+x)
        node['selected'].setValue(False)
    x=x+2800
    return(x)

def tracking(x:float):
    nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/tracking.nk')
    for node in nuke.selectedNodes():
        node['xpos'].setValue(node['xpos'].value()+x)
        node['selected'].setValue(False)
    x=x+2600
    return(x)

def masking(x:float):
   nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/masking.nk')
   for node in nuke.selectedNodes():
       node['xpos'].setValue(node['xpos'].value()+x)
       node['selected'].setValue(False)
   x=x+2800
   return(x)

def reference(x:float):
   nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/reference.nk')
   for node in nuke.selectedNodes():
       node['xpos'].setValue(node['xpos'].value()+x)
       node['selected'].setValue(False)
   x=x+2800
   y=y+800
   return(x,y)

######## OUTPUTS ########
def output(y:float):
   nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/output.nk')
   for node in nuke.selectedNodes():
       node['ypos'].setValue(node['ypos'].value()+y)
       node['selected'].setValue(False)
   y=y+800
   return(y)

def dasgrain(y:float):
    nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/dasgrain.nk')
    for node in nuke.selectedNodes():
        node['ypos'].setValue(node['ypos'].value()+y)
        node['selected'].setValue(False)
    y=y+600
    return(y)

def dalivaryformat(y:float):
    nuke.scriptReadFile('C:/Users/chris/.nuke/Cinegrace/_tools/studio/ScriptSetup/dalivaryformat.nk')
    for node in nuke.selectedNodes():
        node['ypos'].setValue(node['ypos'].value()+y)
        node['selected'].setValue(False)
    y=y+350
    return(y)

inputRow1X=0.0
inputRow1Y=0.0
inputRow2X=0.0
inputRow2Y=900
inputSideX=0.0


#Inputs
ret=ingest(inputRow1X)
inputRow1X=max(inputRow1X,ret[0])
inputRow1Y=max(inputRow1Y,ret[1])

ret=denoise(inputRow2X,inputRow2Y)
inputRow2X=max(inputRow2X,ret[0])
inputRow2Y=max(inputRow2Y,ret[1])

ret=camAndScene(inputRow2X,inputRow2Y)
inputRow2X=max(inputRow2X,ret[0])
inputRow2Y=max(inputRow2Y,ret[1])

inputSideX=max(inputRow1X,inputRow2X)

ret=elements(inputSideX)
inputSideX=max(inputSideX,ret)

ret=tracking(inputSideX)
inputSideX=max(inputSideX,ret)

ret=masking(inputSideX)
inputSideX=max(inputSideX,ret[0])


#Outputs
outputY=5000
ret=dasgrain(outputY)
outputY=max(outputY,ret)

ret=dalivaryformat(outputY)
outputY=max(outputY,ret)

ret=output(outputY)
outputY=max(outputY,ret)
