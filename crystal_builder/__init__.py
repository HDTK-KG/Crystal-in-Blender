bl_info = {
    'name': 'Crystal Builder — Wyckoff & Glass',
    'author': 'Crystal-in-Blender contributors',
    'version': (1, 2, 1),
    'blender': (4, 2, 0),
    'location': 'View3D > Sidebar > Crystal',
    'description': 'Build crystals from space groups and Wyckoff sites with glass materials',
    'category': 'Add Mesh',
}

# Keep the crystallography engine importable outside Blender for tests and scripts.
try:
    import bpy
except ModuleNotFoundError:
    bpy = None

if bpy is not None:
    from .addon import register, unregister
