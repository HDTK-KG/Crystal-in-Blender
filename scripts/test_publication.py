"""Background Blender integration checks for publication scenes."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import crystal_builder
from crystal_builder.addon import load_configuration
from crystal_builder.presets import PRESETS

crystal_builder.register()
source = bpy.context.scene
props = source.crystal_builder
load_configuration(props, PRESETS['NACL'])
bpy.ops.crystal.generate()
source_camera, source_world = source.camera, source.world
source_objects = set(source.objects)
original_mesh = next(o for o in props.generated.objects if o.type == 'MESH')
original_mat = original_mesh.data.materials[0]
for width, height, opaque in [(1800, 900, False), (900, 1800, True), (1200, 1200, False)]:
    bpy.context.window.scene = source
    props.paper_width, props.paper_height = width, height
    props.paper_opaque = opaque
    assert bpy.ops.crystal.publication_scene() == {'FINISHED'}
    paper = bpy.context.scene
    assert paper != source and paper.camera.data.type == 'ORTHO'
    assert (paper.render.resolution_x, paper.render.resolution_y) == (width, height)
    assert paper.world != source_world
    assert source.camera == source_camera and source.world == source_world
    assert set(source.objects) == source_objects
    assert paper.crystal_builder.setting == props.setting
    assert paper.crystal_builder.generated != props.generated
    bpy.context.view_layer.update()
    for obj in paper.crystal_builder.generated.objects:
        assert obj.visible_glossy == opaque
        assert obj.visible_transmission == opaque
        assert obj.visible_shadow == opaque
        if obj.type == 'MESH':
            assert obj.data != original_mesh.data
            shader = obj.data.materials[0].node_tree.nodes.get('Principled BSDF')
            assert shader.inputs['Transmission Weight'].default_value == (0 if opaque else 1)
        for corner in obj.bound_box:
            p = world_to_camera_view(paper, paper.camera, obj.matrix_world @ Vector(corner))
            assert .11 <= p.x <= .89 and .11 <= p.y <= .89, (width, height, p)
    assert original_mat.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value == 1
paper.render.resolution_x = paper.render.resolution_y = 256
paper.cycles.samples = 16
paper.render.filepath = str(ROOT / 'output' / 'paper_test.png')
bpy.ops.render.render(write_still=True)
image = bpy.data.images.load(paper.render.filepath, check_existing=False)
pixels = list(image.pixels)
for x, y in [(0, 0), (255, 0), (0, 255), (255, 255)]:
    start = 4*(y*256+x)
    assert all(abs(v-1) < 1e-6 for v in pixels[start:start+4]), pixels[start:start+4]
bpy.data.images.remove(image)
Path(paper.render.filepath).unlink()
print('PUBLICATION_TEST_OK: square/landscape/portrait framing, isolation, glass/opaque, pure white PNG')
