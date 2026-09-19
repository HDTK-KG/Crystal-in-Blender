import json

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       IntProperty, IntVectorProperty, PointerProperty, StringProperty)
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .core import database, generate, get_setting
from .presets import PRESETS
from .scene import build, remove_generated, clean_glass_visibility
from .publication import create_publication_scene

# Persistent strings are required for dynamic Blender enum items.
SETTING_ITEMS = {}
for entry in database().values():
    SETTING_ITEMS.setdefault(entry.number, []).append(
        (str(entry.serial), f'{entry.symbol} | {entry.choice or "standard"} | #{entry.serial}',
         f'Hall: {entry.hall}; database setting {entry.serial}'))


def setting_items(self, context):
    return SETTING_ITEMS[self.space_group]


def group_changed(self, context):
    self.setting = SETTING_ITEMS[self.space_group][0][0]


class CRYSTAL_Site(bpy.types.PropertyGroup):
    element: StringProperty(name='Element', default='C')
    wyckoff: StringProperty(name='Wyckoff', default='a', description='Letter or multiplicity+letter, e.g. a or 4a; case-sensitive')
    x: StringProperty(name='x', default='0', description='Free parameter; decimal or fraction (e.g. 1/3)')
    y: StringProperty(name='y', default='0')
    z: StringProperty(name='z', default='0')


class CRYSTAL_Settings(bpy.types.PropertyGroup):
    name: StringProperty(name='Name', default='Crystal')
    space_group: IntProperty(name='Space group (ITA)', default=225, min=1, max=230, update=group_changed)
    setting: EnumProperty(name='Axes / origin', items=setting_items)
    a: FloatProperty(name='a (A)', default=5.64, min=.01)
    b: FloatProperty(name='b (A)', default=5.64, min=.01)
    c: FloatProperty(name='c (A)', default=5.64, min=.01)
    alpha: FloatProperty(name='Alpha', default=90, min=.01, max=179.99)
    beta: FloatProperty(name='Beta', default=90, min=.01, max=179.99)
    gamma: FloatProperty(name='Gamma', default=90, min=.01, max=179.99)
    repeats: IntVectorProperty(name='Repeat a / b / c', size=3, default=(1, 1, 1), min=1, max=20)
    boundary: BoolProperty(name='Show atoms on outer faces', default=True)
    sites: CollectionProperty(type=CRYSTAL_Site)
    active_site: IntProperty(default=0)
    preset: EnumProperty(name='Example', items=[(k, v['name'], '') for k, v in PRESETS.items()])
    radius_scale: FloatProperty(name='Atom radius scale', default=1.0, min=.05, max=3)
    roughness: FloatProperty(name='Roughness', default=.12, min=0, max=1)
    ior: FloatProperty(name='Glass IOR', default=1.45, min=1, max=3)
    transmission: FloatProperty(name='Transmission', default=1, min=0, max=1)
    clean_glass: BoolProperty(name='Clean glass (no repeated atom images)', default=True,
                             description='Cycles: retain glass highlights and transmission shading while hiding atoms from mutual reflection, refraction and shadow rays')
    show_cell: BoolProperty(name='Supercell frame', default=True)
    bonds: BoolProperty(name='Distance bonds', default=False)
    bond_cutoff: FloatProperty(name='Bond cutoff (A)', default=3, min=.01, max=20)
    generated: PointerProperty(type=bpy.types.Collection)
    paper_width: IntProperty(name='Width (px)', default=2400, min=256, max=12000)
    paper_height: IntProperty(name='Height (px)', default=2400, min=256, max=12000)
    paper_samples: IntProperty(name='Samples', default=128, min=16, max=4096)
    paper_margin: FloatProperty(name='Margin per side', default=.12, min=.02, max=.35, subtype='FACTOR')
    paper_opaque: BoolProperty(name='Opaque atoms for readability', default=False,
                              description='Use solid colors only in the new paper scene; otherwise keep glass')
    status: StringProperty(default='Load an example or add atomic sites.')


def configuration(props):
    return {'name': props.name, 'space_group': props.space_group, 'setting': int(props.setting),
            'cell': [getattr(props, key) for key in ('a', 'b', 'c', 'alpha', 'beta', 'gamma')],
            'repeats': list(props.repeats), 'boundary': props.boundary,
            'sites': [{'element': s.element, 'wyckoff': s.wyckoff, 'xyz': [s.x, s.y, s.z]} for s in props.sites]}


def load_configuration(props, config):
    result = generate(config)  # Validate before changing the user's inputs.
    props.name = str(config.get('name', 'Crystal'))
    props.space_group = result['setting'].number
    props.setting = str(result['setting'].serial)
    for key, value in zip(('a', 'b', 'c', 'alpha', 'beta', 'gamma'), config['cell']):
        setattr(props, key, float(value))
    props.repeats = config.get('repeats', [1, 1, 1])
    props.boundary = config.get('boundary', True)
    props.sites.clear()
    for site in config['sites']:
        row = props.sites.add()
        row.element, row.wyckoff = site['element'], site['wyckoff']
        row.x, row.y, row.z = [str(v) for v in site.get('xyz', [0, 0, 0])]
    props.active_site = 0
    props.status = 'Inputs loaded. Click Generate / Update.'


class CRYSTAL_OT_preset(bpy.types.Operator):
    bl_idname = 'crystal.load_preset'
    bl_label = 'Load Example'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.crystal_builder
        load_configuration(props, PRESETS[props.preset])
        return {'FINISHED'}


class CRYSTAL_OT_site(bpy.types.Operator):
    bl_idname = 'crystal.edit_site'
    bl_label = 'Edit Atomic Sites'
    bl_options = {'REGISTER', 'UNDO'}
    remove: BoolProperty(default=False)

    def execute(self, context):
        props = context.scene.crystal_builder
        if self.remove and props.sites:
            props.sites.remove(min(props.active_site, len(props.sites)-1))
            props.active_site = max(0, min(props.active_site, len(props.sites)-1))
        elif not self.remove:
            props.sites.add()
            props.active_site = len(props.sites)-1
        return {'FINISHED'}


class CRYSTAL_OT_generate(bpy.types.Operator):
    bl_idname = 'crystal.generate'
    bl_label = 'Generate / Update Crystal'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.crystal_builder
        try:
            config = configuration(props)
            result = generate(config)
            options = {key: getattr(props, key) for key in
                       ('name', 'radius_scale', 'roughness', 'ior', 'transmission', 'clean_glass', 'show_cell', 'bonds', 'bond_cutoff')}
            collection = build(context, result, options)
            old = props.generated
            props.generated = collection
            remove_generated(old)
            props.status = f"{result['unit_count']} atoms/cell | {len(result['atoms'])} displayed"
            self.report({'INFO'}, props.status)
            return {'FINISHED'}
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            props.status = str(error)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class CRYSTAL_OT_clean_glass(bpy.types.Operator):
    bl_idname = 'crystal.apply_clean_glass'
    bl_label = 'Apply Glass Visibility'
    bl_description = 'Apply the clean-glass option to the current crystal without rebuilding it'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.crystal_builder.generated is not None

    def execute(self, context):
        props = context.scene.crystal_builder
        clean_glass_visibility(props.generated.all_objects, props.clean_glass and props.transmission > 0)
        self.report({'INFO'}, 'Glass visibility updated. Render with Cycles to see the result.')
        return {'FINISHED'}


class CRYSTAL_OT_publication(bpy.types.Operator):
    bl_idname = 'crystal.publication_scene'
    bl_label = 'Create White Paper Scene'
    bl_description = 'Copy the generated crystal into a new scene with white background, camera and lights'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.crystal_builder.generated is not None

    def execute(self, context):
        props = context.scene.crystal_builder
        try:
            scene, collection = create_publication_scene(
                context, props.generated, props.paper_width, props.paper_height,
                props.paper_samples, props.paper_margin, props.paper_opaque, props.clean_glass)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        # Copy saved inputs without regenerating: the snapshot matches visible geometry.
        target = scene.crystal_builder
        for prop in props.bl_rna.properties:
            key = prop.identifier
            if key not in {'rna_type', 'sites', 'generated'} and not prop.is_readonly:
                value = getattr(props, key)
                setattr(target, key, tuple(value) if getattr(prop, 'is_array', False) else value)
        for site in props.sites:
            row = target.sites.add()
            for key in ('element', 'wyckoff', 'x', 'y', 'z'):
                setattr(row, key, getattr(site, key))
        target.generated = collection
        if props.paper_opaque:
            target.transmission = 0
            target.roughness = .32
        target.status = 'Paper scene ready. F12 to render; Image > Save As.'
        if context.window:
            context.window.scene = scene
            for area in context.window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.region_3d.view_perspective = 'CAMERA'
        self.report({'INFO'}, target.status)
        return {'FINISHED'}


class CRYSTAL_OT_import(bpy.types.Operator, ImportHelper):
    bl_idname = 'crystal.import_json'
    bl_label = 'Import Crystal JSON'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = '.json'
    filter_glob: StringProperty(default='*.json', options={'HIDDEN'})

    def execute(self, context):
        try:
            with open(self.filepath, encoding='utf-8') as stream:
                load_configuration(context.scene.crystal_builder, json.load(stream))
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class CRYSTAL_OT_export(bpy.types.Operator, ExportHelper):
    bl_idname = 'crystal.export_json'
    bl_label = 'Export Crystal JSON'
    filename_ext = '.json'
    filter_glob: StringProperty(default='*.json', options={'HIDDEN'})

    def execute(self, context):
        try:
            config = configuration(context.scene.crystal_builder)
            generate(config)
            with open(self.filepath, 'w', encoding='utf-8') as stream:
                json.dump(config, stream, indent=2, ensure_ascii=False)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class CRYSTAL_UL_sites(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, 'element', text='', emboss=False)
        row.prop(item, 'wyckoff', text='', emboss=False)


class CRYSTAL_PT_main(bpy.types.Panel):
    bl_label = 'Crystal Builder'
    bl_idname = 'CRYSTAL_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Crystal'

    def draw(self, context):
        layout = self.layout
        props = context.scene.crystal_builder
        row = layout.row(align=True)
        row.prop(props, 'preset', text='')
        row.operator('crystal.load_preset', text='Load')
        layout.prop(props, 'name')
        box = layout.box()
        box.label(text='01  Symmetry', icon='ORIENTATION_GLOBAL')
        box.prop(props, 'space_group')
        box.prop(props, 'setting', text='Setting')
        box = layout.box()
        box.label(text='02  Unit cell | Angstrom / degrees')
        row = box.row(align=True)
        for key in ('a', 'b', 'c'): row.prop(props, key)
        row = box.row(align=True)
        for key in ('alpha', 'beta', 'gamma'): row.prop(props, key)
        box = layout.box()
        box.label(text='03  Atomic sites', icon='OUTLINER_DATA_MESH')
        row = box.row()
        row.template_list('CRYSTAL_UL_sites', '', props, 'sites', props, 'active_site', rows=3)
        col = row.column(align=True)
        col.operator('crystal.edit_site', text='', icon='ADD')
        col.operator('crystal.edit_site', text='', icon='REMOVE').remove = True
        setting = get_setting(props.space_group, int(props.setting))
        if props.sites and props.active_site < len(props.sites):
            site = props.sites[props.active_site]
            row = box.row(align=True)
            row.prop(site, 'element')
            row.prop(site, 'wyckoff')
            letter = site.wyckoff.lstrip('0123456789')
            position = setting.positions.get(letter)
            if position:
                box.label(text=f'{position.label}: ({position.expressions[0]})')
                row = box.row(align=True)
                for key in ('x', 'y', 'z'):
                    col = row.column()
                    col.enabled = key in position.variables
                    col.prop(site, key)
            else:
                box.label(text='Choose a valid Wyckoff letter below', icon='ERROR')
        flow = box.column_flow(columns=3, align=True)
        for pos in setting.positions.values(): flow.label(text=pos.label)
        box = layout.box()
        box.label(text='04  Display & glass', icon='MATERIAL')
        box.prop(props, 'repeats')
        box.prop(props, 'boundary')
        box.prop(props, 'show_cell')
        box.prop(props, 'radius_scale')
        box.prop(props, 'roughness')
        box.prop(props, 'ior')
        box.prop(props, 'transmission')
        box.prop(props, 'clean_glass')
        box.operator('crystal.apply_clean_glass')
        box.prop(props, 'bonds')
        if props.bonds: box.prop(props, 'bond_cutoff')
        row = layout.row()
        row.scale_y = 1.6
        row.operator('crystal.generate', icon='MESH_UVSPHERE')
        layout.label(text=props.status)
        layout.label(text='Glass: use Material Preview or Cycles.')
        row = layout.row(align=True)
        row.operator('crystal.import_json', text='Import JSON', icon='IMPORT')
        row.operator('crystal.export_json', text='Export JSON', icon='EXPORT')
        box = layout.box()
        box.label(text='05  Publication / White background', icon='RENDER_STILL')
        row = box.row(align=True)
        row.prop(props, 'paper_width')
        row.prop(props, 'paper_height')
        box.prop(props, 'paper_samples')
        box.prop(props, 'paper_margin')
        box.prop(props, 'paper_opaque')
        box.operator('crystal.publication_scene', icon='SCENE_DATA')
        box.label(text='Creates a new scene. F12 to render.')


CLASSES = (CRYSTAL_Site, CRYSTAL_Settings, CRYSTAL_OT_preset, CRYSTAL_OT_site,
           CRYSTAL_OT_generate, CRYSTAL_OT_clean_glass, CRYSTAL_OT_publication, CRYSTAL_OT_import, CRYSTAL_OT_export, CRYSTAL_UL_sites, CRYSTAL_PT_main)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.crystal_builder = PointerProperty(type=CRYSTAL_Settings)


def unregister():
    del bpy.types.Scene.crystal_builder
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
