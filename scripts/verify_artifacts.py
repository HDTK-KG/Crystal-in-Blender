"""Verify the distributed ZIP and saved demo in an isolated Blender process."""
from pathlib import Path
import sys
import tempfile
import zipfile
import bpy

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='crystal-package-') as directory:
    with zipfile.ZipFile(ROOT / 'dist/crystal_builder-1.2.1.zip') as archive:
        archive.extractall(directory)
    sys.path.insert(0, directory)
    import crystal_builder
    from crystal_builder.core import database, generate
    from crystal_builder.addon import configuration
    assert str(Path(crystal_builder.__file__)).startswith(directory)
    assert len(database()) == 530
    crystal_builder.register()
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'output/nacl_glass.blend'))
    props = bpy.context.scene.crystal_builder
    assert props.space_group == 225
    assert props.setting == '523'
    assert tuple(props.repeats) == (2, 2, 2)
    assert len(generate(configuration(props))['atoms']) == 125
    assert props.generated is not None
    assert len([o for o in props.generated.objects if o.type == 'MESH']) == 125
    assert bpy.ops.crystal.generate() == {'FINISHED'}
    assert bpy.context.scene.camera is not None
    crystal_builder.unregister()
print('ARTIFACTS_OK')
