"""Create white-background versions of the existing glass demo."""
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import crystal_builder

crystal_builder.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'output/nacl_glass.blend'))
props = bpy.context.scene.crystal_builder
props.paper_width = props.paper_height = 1800
props.paper_samples = 64
bpy.ops.crystal.publication_scene()
scene = bpy.context.scene
scene.render.filepath = str(ROOT / 'output/nacl_paper_white.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'output/nacl_paper_white.blend'))
bpy.ops.render.render(write_still=True)
print('PAPER_DEMO_OK')
