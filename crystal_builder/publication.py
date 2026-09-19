"""Create an independent, white-background scene for publication figures."""
import bpy
from mathutils import Vector

from .scene import TAG, clean_glass_visibility


def create_publication_scene(context, source, width=2400, height=2400, samples=128,
                             margin=.12, opaque=False, clean_glass=True):
    objects = [obj for obj in source.all_objects if obj.type in {'MESH', 'CURVE'}]
    if not objects:
        raise ValueError('Generate a crystal before creating a paper scene')
    context.view_layer.update()
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    lower = Vector([min(p[i] for p in points) for i in range(3)])
    upper = Vector([max(p[i] for p in points) for i in range(3)])
    center = (lower + upper) / 2
    size = max((upper - lower).length, .1)
    scene = bpy.data.scenes.new('Crystal | Paper White')
    collection = bpy.data.collections.new('Paper | Crystal')
    collection[TAG] = True
    scene.collection.children.link(collection)
    # Copy geometry and materials so either scene can be edited independently.
    meshes, materials = {}, {}
    for obj in objects:
        clone = obj.copy()
        transform = obj.matrix_world.copy()
        clone.parent = None
        clone.animation_data_clear()
        clone.constraints.clear()
        clone.matrix_world = transform
        if obj.data not in meshes:
            data = obj.data.copy()
            meshes[obj.data] = data
            for index, mat in enumerate(data.materials):
                if mat is None:
                    continue
                if mat not in materials:
                    copy = mat.copy()
                    materials[mat] = copy
                    if opaque and copy.use_nodes:
                        for node in copy.node_tree.nodes:
                            if node.type == 'BSDF_PRINCIPLED':
                                node.inputs['Transmission Weight'].default_value = 0
                                node.inputs['Roughness'].default_value = .32
                data.materials[index] = materials[mat]
        clone.data = meshes[obj.data]
        clone.hide_render = False
        collection.objects.link(clone)
    clean_glass_visibility(collection.objects, clean_glass and not opaque)
    for key in ('space_group', 'setting', 'unit_cell_atoms'):
        if key in source:
            collection[key] = source[key]

    world = bpy.data.worlds.new('Paper | White background')
    world.use_nodes = True
    scene.world = world
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputWorld')
    lighting = nodes.new('ShaderNodeBackground')
    lighting.inputs['Color'].default_value = (1, 1, 1, 1)
    lighting.inputs['Strength'].default_value = .45
    backdrop = nodes.new('ShaderNodeBackground')
    backdrop.inputs['Color'].default_value = (1, 1, 1, 1)
    # Headroom keeps camera-only white at RGB 255 even with sampling/denoising
    # fluctuations. Lighting and transmission use the separate .45 background.
    backdrop.inputs['Strength'].default_value = 2
    rays = nodes.new('ShaderNodeLightPath')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(rays.outputs['Is Camera Ray'], mix.inputs[0])
    links.new(lighting.outputs[0], mix.inputs[1])
    links.new(backdrop.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs['Surface'])

    rig = bpy.data.collections.new('Paper | Camera and lighting')
    scene.collection.children.link(rig)
    camera_data = bpy.data.cameras.new('Paper | Orthographic camera')
    camera = bpy.data.objects.new(camera_data.name, camera_data)
    rig.objects.link(camera)
    camera.location = center + Vector((1.2, -1.65, 1.1)).normalized()*size*2.5
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.type = 'ORTHO'
    camera_data.clip_start = max(size/10000, .0001)
    camera_data.clip_end = size*10
    rotation = camera.rotation_euler.to_matrix().transposed()
    projected = [rotation @ (p-center) for p in points]
    span_x = 2*max(abs(p.x) for p in projected)
    span_y = 2*max(abs(p.y) for p in projected)
    aspect = width/height
    # Blender's ortho_scale spans the larger image dimension (AUTO sensor fit).
    camera_data.ortho_scale = max(span_x, span_y*aspect) / (1-2*margin) if aspect >= 1 else max(span_x/aspect, span_y) / (1-2*margin)
    scene.camera = camera
    for name, offset, power, extent in [
        ('Key', (1, -1.3, 1.8), 24, .8),
        ('Fill', (-1.3, -.4, .7), 12, 1.0),
        ('Rim', (.3, 1.4, 1.2), 18, .7),
    ]:
        data = bpy.data.lights.new(f'Paper | {name}', 'AREA')
        data.energy = power*size*size
        data.shape = 'DISK'
        data.size = size*extent
        light = bpy.data.objects.new(data.name, data)
        rig.objects.link(light)
        light.location = center + Vector(offset)*size
        light.rotation_euler = (center-light.location).to_track_quat('-Z', 'Y').to_euler()

    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 10
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.filepath = '//crystal_paper.png'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene['publication_note'] = 'White RGB background; orthographic camera; no floor; independent crystal snapshot.'
    return scene, collection
