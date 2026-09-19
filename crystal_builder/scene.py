"""Blender geometry and glass materials; no changes to cameras or render settings."""
import colorsys
import math
from itertools import product

import bpy
from mathutils import Vector

from .core import ELEMENTS, cartesian

COLORS = {'H': (.85, .93, 1), 'C': (.18, .55, .7), 'N': (.15, .28, .95),
          'O': (1, .12, .18), 'Na': (.42, .23, .95), 'Cl': (.20, .85, .40),
          'Si': (.85, .58, .28), 'Ti': (.55, .65, .85), 'Fe': (.9, .38, .12)}
# Display radii, deliberately not a quantitative ionic-radius model.
RADII = {'H': .25, 'C': .42, 'N': .4, 'O': .42, 'Na': .55, 'Cl': .72,
         'Si': .52, 'Ti': .62, 'Fe': .55}
TAG = 'crystal_builder_owned'


def clean_glass_visibility(objects, enabled=True):
    """Keep direct glass shading, but suppress repeated atom images and shadows.

    This is a diagram-oriented Cycles visibility treatment, not physical glass.
    Apply to cell edges too so they do not become refracted stripes in atoms.
    """
    seen = set()
    for obj in objects:
        if obj.type in {'MESH', 'CURVE'}:
            obj.visible_glossy = not enabled
            obj.visible_transmission = not enabled
            obj.visible_shadow = not enabled
            if obj.get('element'):
                for mat in obj.data.materials:
                    if mat is not None and mat not in seen:
                        clean_glass_material(mat, enabled)
                        seen.add(mat)


def clean_glass_material(mat, enabled):
    """A straight-through component retains transparency without lens patterns."""
    if not mat.use_nodes:
        return
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    if principled is None or output is None:
        return
    base_key = 'crystal_clean_original_color'
    if not enabled:
        if base_key in mat:
            principled.inputs['Base Color'].default_value = tuple(mat[base_key])
            mat.diffuse_color = tuple(mat[base_key])
            del mat[base_key]
        links.new(principled.outputs['BSDF'], output.inputs['Surface'])
        return
    if base_key not in mat:
        mat[base_key] = list(principled.inputs['Base Color'].default_value)
    # Tint both light paths: white straight-through transmission was washing
    # out the element colors on the white publication background.
    base = mat[base_key]
    deep_color = tuple(.35 * max(0, float(c))**2.4 for c in base[:3]) + (1,)
    principled.inputs['Base Color'].default_value = deep_color
    mat.diffuse_color = deep_color
    transparent = nodes.get('Crystal Clean Transparency')
    if transparent is None:
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        transparent.name = 'Crystal Clean Transparency'
    mix = nodes.get('Crystal Clean Glass Mix')
    if mix is None:
        mix = nodes.new('ShaderNodeMixShader')
        mix.name = 'Crystal Clean Glass Mix'
    mix.inputs[0].default_value = .35
    transparent.inputs['Color'].default_value = deep_color
    links.new(principled.outputs['BSDF'], mix.inputs[1])
    links.new(transparent.outputs['BSDF'], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs['Surface'])


def material(element, roughness, ior, transmission):
    color = COLORS.get(element, colorsys.hsv_to_rgb((ELEMENTS.index(element)*.618) % 1, .58, .85))
    mat = bpy.data.materials.new(f'Crystal Glass | {element}')
    mat[TAG] = True
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['IOR'].default_value = ior
    bsdf.inputs['Transmission Weight'].default_value = transmission
    return mat


def remove_generated(collection):
    if collection and collection.get(TAG):
        for obj in list(collection.objects):
            if len(obj.users_collection) == 1:
                bpy.data.objects.remove(obj, do_unlink=True)
            else:
                collection.objects.unlink(obj)
        bpy.data.collections.remove(collection)
    for pool in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
        for item in list(pool):
            if item.get(TAG) and item.users == 0:
                pool.remove(item)


def curve_segments(collection, name, segments, radius, mat):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve[TAG] = True
    curve.dimensions = '3D'
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    for start, end in segments:
        spline = curve.splines.new('POLY')
        spline.points.add(1)
        spline.points[0].co = (*start, 1)
        spline.points[1].co = (*end, 1)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    curve.materials.append(mat)
    return obj


def bond_segments(atoms, cutoff):
    """Distance cutoff in the displayed supercell, using spatial bins."""
    bins = {}
    segments = []
    for atom in atoms:
        p = atom['position']
        key = tuple(math.floor(v / cutoff) for v in p)
        for delta in product((-1, 0, 1), repeat=3):
            for q in bins.get(tuple(a+b for a, b in zip(key, delta)), []):
                if 1e-12 < sum((a-b)**2 for a, b in zip(p, q)) <= cutoff**2:
                    segments.append((p, q))
                    if len(segments) > 100000:
                        raise ValueError('Too many bonds; reduce cutoff or supercell size')
        bins.setdefault(key, []).append(p)
    return segments


def build(context, result, options):
    collection = bpy.data.collections.new(options.get('name', 'Crystal'))
    collection[TAG] = True
    context.scene.collection.children.link(collection)
    try:
        import bmesh
        materials, meshes = {}, {}
        scale = options.get('radius_scale', 1.0)
        for element in sorted({a['element'] for a in result['atoms']}):
            mat = material(element, options.get('roughness', .12), options.get('ior', 1.45),
                           options.get('transmission', 1.0))
            materials[element] = mat
            mesh = bpy.data.meshes.new(f'Crystal Sphere | {element}')
            mesh[TAG] = True
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16,
                                     radius=RADII.get(element, .5)*scale)
            bm.to_mesh(mesh)
            bm.free()
            for face in mesh.polygons:
                face.use_smooth = True
            mesh.materials.append(mat)
            meshes[element] = mesh
        for i, atom in enumerate(result['atoms']):
            obj = bpy.data.objects.new(f"{atom['element']} | {i+1:04d}", meshes[atom['element']])
            collection.objects.link(obj)
            obj.location = atom['position']
            obj['element'] = atom['element']
            obj['fractional'] = atom['fractional']
            obj['site_index'] = atom['site']
        if options.get('show_cell', True) or options.get('bonds', False):
            edge_mat = bpy.data.materials.new('Crystal | Frame')
            edge_mat[TAG] = True
            edge_mat.diffuse_color = (.24, .48, .60, 1)
            edge_mat.use_nodes = True
            shader = edge_mat.node_tree.nodes.get('Principled BSDF')
            shader.inputs['Base Color'].default_value = (.24, .48, .60, 1)
            shader.inputs['Metallic'].default_value = .55
            shader.inputs['Roughness'].default_value = .24
            if options.get('show_cell', True):
                segments = []
                repeats = result['repeats']
                for axis in range(3):
                    other = [i for i in range(3) if i != axis]
                    for values in product((0, 1), repeat=2):
                        start = [0, 0, 0]
                        for idx, value in zip(other, values):
                            start[idx] = repeats[idx]*value
                        end = start.copy()
                        end[axis] = repeats[axis]
                        segments.append((cartesian(start, result['vectors']), cartesian(end, result['vectors'])))
                curve_segments(collection, 'Supercell edges', segments, .025, edge_mat)
            if options.get('bonds', False):
                cutoff = float(options.get('bond_cutoff', 3.0))
                if not math.isfinite(cutoff) or cutoff <= 0:
                    raise ValueError('Bond cutoff must be positive')
                curve_segments(collection, 'Distance bonds', bond_segments(result['atoms'], cutoff), .045, edge_mat)
        collection['space_group'] = result['setting'].number
        collection['setting'] = result['setting'].serial
        collection['unit_cell_atoms'] = result['unit_count']
        clean_glass_visibility(collection.objects, options.get('clean_glass', True)
                               and options.get('transmission', 1.0) > 0)
        return collection
    except Exception:
        remove_generated(collection)
        raise
