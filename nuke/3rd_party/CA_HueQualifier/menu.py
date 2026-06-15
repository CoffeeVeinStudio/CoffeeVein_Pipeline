import nuke
from pathlib import Path

_here = Path(__file__).parent

for sub in ["CompAcademy", "CompAcademy/tools", "CompAcademy/icons", "CompAcademy/graphics"]:
    nuke.pluginAddPath((_here / sub).as_posix())

import CA_QualifierWidget

toolbar = nuke.toolbar("Nodes")
m = toolbar.addMenu("Compositing Academy", icon="qf_logo.png")
m.addCommand("CA_HueQualifier", "nuke.createNode('CA_HueQualifier')", icon="qf_logo.png")
