"""Create a ready-to-open .blend and a Cycles preview. Use --factory-startup."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import crystal_builder
from crystal_builder.addon import load_configuration
from crystal_builder.presets import PRESETS

crystal_builder.register()
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene = bpy.context.scene
props = scene.crystal_builder
load_configuration(props, {**PRESETS['NACL'], 'name': 'NaCl | Glass crystal', 'repeats': [2, 2, 2]})
props.radius_scale = 1.12
bpy.ops.crystal.generate()
center = Vector((5.64, 5.64, 5.64))

def aim(obj, point):
    obj.rotation_euler = (Vector(point)-obj.location).to_track_quat('-Z', 'Y').to_euler()

bpy.ops.object.camera_add(location=center+Vector((21, -29, 20)))
camera = bpy.context.object
camera.name = 'Camera | Crystal portrait'
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 24
aim(camera, center)
scene.camera = camera
for name, location, energy, size, color in [
    ('Key softbox', (3, -6, 20), 3200, 10, (1, .91, .8)),
    ('Rim softbox', (12, 15, 18), 4200, 9, (.65, .82, 1)),
    ('Fill softbox', (-10, 4, 9), 2200, 8, (.8, 1, .95)),
]:
    bpy.ops.object.light_add(type='AREA', location=location)
    lamp = bpy.context.object
    lamp.name = name
    lamp.data.energy, lamp.data.shape, lamp.data.size, lamp.data.color = energy, 'DISK', size, color
    aim(lamp, center)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.86))
floor = bpy.context.object
floor.name = 'Studio floor'
mat = bpy.data.materials.new('Studio | Midnight blue')
mat.use_nodes = True
shader = mat.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value = (.018, .032, .052, 1)
shader.inputs['Roughness'].default_value = .28
floor.data.materials.append(mat)
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.18, .24, .34, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .5
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 12
scene.cycles.transmission_bounces = 10
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
            area.spaces.active.overlay.show_overlays = False
readme = bpy.data.texts.new('START HERE')
readme.write('Crystal Builder | NaCl glass demo\n\n125 displayed atoms, 8 atoms per conventional unit cell.\nInstall dist/crystal_builder-1.1.0.zip, enable the add-on, then open the Crystal sidebar.\nRender: F12. Atom meshes and materials are stored in this file.\nCoordinates: 1 Blender unit = 1 angstrom.\n')
output = ROOT / 'output'
output.mkdir(exist_ok=True)
scene.render.filepath = str(output / 'nacl_glass.png')
bpy.ops.wm.save_as_mainfile(filepath=str(output / 'nacl_glass.blend'))
bpy.ops.render.render(write_still=True)
print('DEMO_OK')
