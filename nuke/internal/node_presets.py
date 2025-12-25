import nuke
def nodePresetsStartup():
  nuke.setUserPreset("Expression", "ST_map", {'expr0': '(x+0.5)/width', 'expr1': '(y+0.5)/height', 'selected': 'true'})
  nuke.setUserPreset("Expression", "ceil_alpha", {'expr3': 'ceil(a)', 'selected': 'true'})
  nuke.setUserPreset("Expression", "floor_alpha", {'expr3': 'floor(a)', 'selected': 'true'})
  nuke.setUserPreset("Write", "Filepath without extension", {'file': '[file\xa0rootname\xa0[value\xa0[topnode].file]]', 'colorspace': 'rec709', 'create_directories': 'true', 'checkHashOnRead': 'false', 'in_colorspace': 'scene_linear', 'out_colorspace': 'scene_linear', 'ocioColorspace': 'scene_linear', 'selected': 'true'})
