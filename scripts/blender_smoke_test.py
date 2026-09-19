"""Run in Blender background mode with --factory-startup --python-exit-code 1."""
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import crystal_builder
from crystal_builder.addon import configuration, load_configuration
from crystal_builder.core import generate
from crystal_builder.presets import PRESETS

crystal_builder.register()
props = bpy.context.scene.crystal_builder
unrelated = bpy.data.objects.get('Cube')
for key, count in [('NACL', 8), ('DIAMOND', 8), ('BCC', 2), ('RUTILE', 6)]:
    load_configuration(props, PRESETS[key])
    assert generate(configuration(props))['unit_count'] == count
    assert bpy.ops.crystal.generate() == {'FINISHED'}
    assert props.generated['unit_cell_atoms'] == count
    assert bpy.data.objects.get('Cube') == unrelated
    for obj in props.generated.objects:
        if obj.type == 'MESH':
            shader = obj.data.materials[0].node_tree.nodes.get('Principled BSDF')
            assert shader.inputs['Transmission Weight'].default_value == 1.0
            assert abs(shader.inputs['IOR'].default_value - 1.45) < 1e-5
load_configuration(props, PRESETS['NACL'])
props.bonds = True
props.repeats = (2, 1, 1)
assert bpy.ops.crystal.generate() == {'FINISHED'}
assert any(obj.name.startswith('Distance bonds') for obj in props.generated.objects)
assert len([c for c in bpy.data.collections if c.get('crystal_builder_owned')]) == 1
old = props.generated
try:
    load_configuration(props, {**PRESETS['NACL'], 'setting': 1})
    raise AssertionError('Invalid import accepted')
except ValueError:
    pass
assert props.generated == old
assert configuration(props)['space_group'] == 225
atom = next(o for o in props.generated.objects if o.type == 'MESH')
shader = atom.data.materials[0].node_tree.nodes.get('Principled BSDF')
before = tuple(shader.inputs[key].default_value for key in ('Roughness', 'IOR', 'Transmission Weight'))
for enabled in (False, True):
    props.clean_glass = enabled
    assert bpy.ops.crystal.apply_clean_glass() == {'FINISHED'}
    for obj in props.generated.objects:
        assert obj.visible_glossy == (not enabled)
        assert obj.visible_transmission == (not enabled)
        assert obj.visible_shadow == (not enabled)
        assert obj.visible_camera
    assert tuple(shader.inputs[key].default_value for key in ('Roughness', 'IOR', 'Transmission Weight')) == before
    material = atom.data.materials[0]
    output = next(n for n in material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
    surface = output.inputs['Surface'].links[0].from_node
    assert surface.type == ('MIX_SHADER' if enabled else 'BSDF_PRINCIPLED')
    if enabled:
        assert abs(surface.inputs[0].default_value - .35) < 1e-6
        assert surface.inputs[2].links[0].from_node.type == 'BSDF_TRANSPARENT'
        deep = tuple(shader.inputs['Base Color'].default_value)
        original = tuple(material['crystal_clean_original_color'])
        assert all(a < b for a, b in zip(deep[:3], original[:3]))
        assert tuple(surface.inputs[2].links[0].from_node.inputs['Color'].default_value) == deep
        bpy.ops.crystal.apply_clean_glass()
        assert tuple(shader.inputs['Base Color'].default_value) == deep
props.clean_glass = False
bpy.ops.crystal.apply_clean_glass()
assert tuple(shader.inputs['Base Color'].default_value) == original
crystal_builder.unregister()
crystal_builder.register()
crystal_builder.unregister()
print('BLENDER_SMOKE_TEST_OK')
