import sys
import os
import itertools

import shutil
import subprocess
import yaml
# import attr
import numpy as np
import collections

script_dir = os.path.dirname(os.path.realpath(__file__))
# sys.path.append(os.path.join(script_dir, './src/bgem/gmsh'))
# sys.path.append(os.path.join(script_dir, '../../dfn/src'))


from bgem.gmsh.gmsh import gmsh
# import gmsh_io
# import fracture


def create_box(nodes):
    ob_x = nodes[1][0] - nodes[0][0]
    ob_y = nodes[1][1] - nodes[0][1]
    ob_z = nodes[1][2] - nodes[0][2]
    box = gmsh.model.occ.addBox(nodes[0][0], nodes[0][1], nodes[0][2], ob_x, ob_y, ob_z)
    return 3, box


def create_volume(nodes):
    """
    Creates box with lower and upper base and sides.
    :param nodes: Nodes must be ordered: [lower_base_nodes, upper_base_nodes]
    :return:
    """
    n = int(len(nodes)/2)
    p_tags = []
    for p in nodes:
        p_tags.append(gmsh.model.occ.addPoint(p[0], p[1], p[2]))

    l_tags = []
    for i in range(0, n-1):
        l_tags.append(gmsh.model.occ.addLine(p_tags[i], p_tags[i+1]))
    l_tags.append(gmsh.model.occ.addLine(p_tags[n-1], p_tags[0]))
    for i in range(n, 2*n-1):
        l_tags.append(gmsh.model.occ.addLine(p_tags[i], p_tags[i+1]))
    l_tags.append(gmsh.model.occ.addLine(p_tags[2*n-1], p_tags[n]))
    for i in range(0, n):
        l_tags.append(gmsh.model.occ.addLine(p_tags[i], p_tags[n+i]))

    b = [l_tags[i] for i in range(0, n)]
    loop_down = gmsh.model.occ.addCurveLoop(b)
    base_down = gmsh.model.occ.addPlaneSurface([loop_down])

    b = [l_tags[i] for i in range(n, 2*n)]
    loop_up = gmsh.model.occ.addCurveLoop(b)
    base_up = gmsh.model.occ.addPlaneSurface([loop_up])
    sides = []
    for i in range(0, n-1):
        lines = [l_tags[i], l_tags[2*n+i+1], -l_tags[n+i], -l_tags[2*n+i]]
        loop_side = gmsh.model.occ.addCurveLoop(lines)
        sides.append(gmsh.model.occ.addPlaneSurface([loop_side]))
    lines = [l_tags[n-1], l_tags[2*n], -l_tags[2*n-1], -l_tags[3*n-1]]
    loop_side = gmsh.model.occ.addCurveLoop(lines)
    sides.append(gmsh.model.occ.addPlaneSurface([loop_side]))

    plane_loop = gmsh.model.occ.addSurfaceLoop([base_down, base_up, *sides])
    volume = gmsh.model.occ.addVolume([plane_loop])
    return 3, volume


def create_plane(nodes):
    p_tags = []
    for p in nodes:
        p_tags.append(gmsh.model.occ.addPoint(p[0], p[1], p[2]))

    l_tags = []
    for i in range(0, len(p_tags) - 1):
        l_tags.append(gmsh.model.occ.addLine(p_tags[i], p_tags[i + 1]))
    l_tags.append(gmsh.model.occ.addLine(p_tags[len(p_tags) - 1], p_tags[0]))

    loop = gmsh.model.occ.addCurveLoop(l_tags)
    polygon = gmsh.model.occ.addPlaneSurface([loop])
    return 2, polygon


def generate_mesh(config_dict):
    gmsh.initialize()
    file_name = "box_wells"
    gmsh.model.add(file_name)

    with open(os.path.join(script_dir, "geometry.yaml"), "r") as f:
        geometry_dict = yaml.safe_load(f)

    # box_outer = create_box(geometry_dict['outer_box']['nodes'])
    box_outer = create_volume(geometry_dict['outer_box']['nodes'])
    # box_inner = create_box(geometry_dict['inner_box']['nodes'])

    fract1 = create_plane(geometry_dict['fractures'][0]['nodes'])

    # rectangle, map = gmsh.model.occ.fragment([fract1_dt], [])
    rectangle = [fract1]
    # box = gmsh.model.occ.addBox(-1000, -1000, -1000, 2000, 2000, 2000)
    # rec1 = gmsh.model.occ.addRectangle(-800, -800, 0, 1600, 1600)
    # rec2 = gmsh.model.occ.addRectangle(-1200, -1200, 0, 2400, 2400)
    # rec1_dt = (2, rec1)
    # rec2_dt = (2, rec2)
    # gmsh.model.occ.rotate([rec2_dt], 0, 0, 0, 0, 1, 0, np.pi / 2)
    # rectangle, map = gmsh.model.occ.fragment([rec1_dt, rec2_dt], [])

    # box_diff = gmsh.model.occ.cut(box_outer, box_inner, removeObject=True, removeTool=False)
    # bc_inner = gmsh.model.getBoundary(box_inner, combined=False, oriented=False)

    # bc_frag, map = gmsh.model.occ.fragment(box_copy, dim_tags_copy)

    # box = [box_diff, box_inner]
    box = [box_outer]
    # box = [box_inner]

    box_copy = gmsh.model.occ.copy(box)
    dim_tags, map = gmsh.model.occ.intersect(rectangle, box_copy)
    gmsh.model.occ.synchronize()

    dim_tags_copy = gmsh.model.occ.copy(dim_tags)
    box_copy = gmsh.model.occ.copy(box)
    box_cut, map = gmsh.model.occ.fragment(box_copy, dim_tags_copy)
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()

    b = gmsh.model.addPhysicalGroup(3, [tag for dim, tag in box_cut])
    gmsh.model.setPhysicalName(3, b, "box")

    rect = gmsh.model.addPhysicalGroup(2, [tag for dim, tag in dim_tags])
    gmsh.model.setPhysicalName(2, rect, "rectangle")

    bc_tags = gmsh.model.getBoundary(dim_tags, combined=False, oriented=False)
    bc_nodes = gmsh.model.getBoundary(dim_tags, combined=False, oriented=False, recursive=True)
    # bc_box_nodes = gmsh.model.getBoundary(box_cut, combined=False, oriented=False, recursive=True)
    bc_rect = gmsh.model.addPhysicalGroup(1, [tag for dim, tag in bc_tags])
    gmsh.model.setPhysicalName(1, bc_rect, ".rectangle")
    gmsh.model.occ.setMeshSize(bc_nodes, 50)

    # gmsh.model.mesh.embed(2, [tag for dim, tag in dim_tags], 3, box_copy[0][1])
    # factory.synchronize()

    model = gmsh.model

    # generate mesh, write to file and output number of entities that produced error
    gmsh.option.setNumber("Mesh.CharacteristicLengthFromPoints", 1)
    gmsh.option.setNumber("Mesh.CharacteristicLengthFromCurvature", 0)
    gmsh.option.setNumber("Mesh.CharacteristicLengthExtendFromBoundary", 1)
    # gmsh.option.setNumber("Mesh.CharacteristicLengthMin", 100)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 300)

    gmsh.write(file_name + '.brep')
    gmsh.write(file_name + '.geo')
    model.mesh.generate(3)
    gmsh.model.mesh.removeDuplicateNodes()
    bad_entities = model.mesh.getLastEntityError()
    print(bad_entities)
    gmsh.write(file_name + ".msh")
    gmsh.fltk.run()
    gmsh.finalize()

    return len(bad_entities)

def to_polar(x, y, z):
    rho = np.sqrt(x ** 2 + y ** 2)
    phi = np.arctan2(y, x)
    if z > 0:
        phi += np.pi
    return phi, rho


# def plot_fr_orientation(fractures):
#     family_dict = collections.defaultdict(list)
#     for fr in fractures:
#         x, y, z = fracture.FisherOrientation.rotate(np.array([0,0,1]), axis=fr.rotation_axis, angle=fr.rotation_angle)[0]
#         family_dict[fr.region].append([
#             to_polar(z, y, x),
#             to_polar(z, x, -y),
#             to_polar(y, x, z)
#             ])
#
#     import matplotlib.pyplot as plt
#     fig, axes = plt.subplots(1, 3, subplot_kw=dict(projection='polar'))
#     for name, data in family_dict.items():
#         # data shape = (N, 3, 2)
#         data = np.array(data)
#         for i, ax in enumerate(axes):
#             phi = data[:, i, 0]
#             r = data[:, i, 1]
#             c = ax.scatter(phi, r, cmap='hsv', alpha=0.75, label=name)
#     axes[0].set_title("X-view, Z-north")
#     axes[1].set_title("Y-view, Z-north")
#     axes[2].set_title("Z-view, Y-north")
#     for ax in axes:
#         ax.set_theta_zero_location("N")
#         ax.set_theta_direction(-1)
#         ax.set_ylim(0, 1)
#     fig.legend(loc = 1)
#     fig.savefig("fracture_orientation.pdf")
#     plt.close(fig)
#     #plt.show()
#
#
# def generate_fractures(config_dict):
#     geom = config_dict["geometry"]
#     dimensions = geom["box_dimensions"]
#     well_z0, well_z1 = geom["well_openning"]
#     well_length = well_z1 - well_z0
#     well_r = geom["well_effective_radius"]
#     well_dist = geom["well_distance"]
#
#     # generate fracture set
#     fracture_box = [1.5 * well_dist, 1.5 * well_length, 1.5 * well_length]
#     volume = np.product(fracture_box)
#     pop = fracture.Population(volume)
#     pop.initialize(geom["fracture_stats"])
#     pop.set_sample_range([1, well_dist], max_sample_size=geom["n_frac_limit"])
#     print("total mean size: ", pop.mean_size())
#     connected_position = geom.get('connected_position_distr', False)
#     if connected_position:
#         eps = well_r / 2
#         left_well_box = [-well_dist/2-eps, -eps, well_z0, -well_dist/2+eps, +eps, well_z1]
#         right_well_box = [well_dist/2-eps, -eps, well_z0, well_dist/2+eps, +eps, well_z1]
#         pos_gen = fracture.ConnectedPosition(
#             confining_box=fracture_box,
#             init_boxes=[left_well_box, right_well_box])
#     else:
#         pos_gen = fracture.UniformBoxPosition(fracture_box)
#     fractures = pop.sample(pos_distr=pos_gen, keep_nonempty=True)
#     #fracture.fr_intersect(fractures)
#
#     for fr in fractures:
#         fr.region = "fr"
#     used_families = set((f.region for f in fractures))
#     for model in ["hm_params", "th_params", "th_params_ref"]:
#         model_dict = config_dict[model]
#         model_dict["fracture_regions"] = list(used_families)
#         model_dict["left_well_fracture_regions"] = [".{}_left_well".format(f) for f in used_families]
#         model_dict["right_well_fracture_regions"] = [".{}_right_well".format(f) for f in used_families]
#     return fractures
#
#
# def create_fractures_rectangles(gmsh_geom, fractures, base_shape: 'ObjectSet'):
#     # From given fracture date list 'fractures'.
#     # transform the base_shape to fracture objects
#     # fragment fractures by their intersections
#     # return dict: fracture.region -> GMSHobject with corresponding fracture fragments
#     shapes = []
#     for i, fr in enumerate(fractures):
#         shape = base_shape.copy()
#         print("fr: ", i, "tag: ", shape.dim_tags)
#         shape = shape.scale([fr.rx, fr.ry, 1]) \
#             .rotate(axis=fr.rotation_axis, angle=fr.rotation_angle) \
#             .translate(fr.centre) \
#             .set_region(fr.region)
#
#         shapes.append(shape)
#
#     fracture_fragments = gmsh_geom.fragment(*shapes)
#     return fracture_fragments
#
#
# def create_fractures_polygons(gmsh_geom, fractures):
#     # From given fracture date list 'fractures'.
#     # transform the base_shape to fracture objects
#     # fragment fractures by their intersections
#     # return dict: fracture.region -> GMSHobject with corresponding fracture fragments
#     frac_obj = fracture.Fractures(fractures)
#     frac_obj.snap_vertices_and_edges()
#     shapes = []
#     for fr, square in zip(fractures, frac_obj.squares):
#         shape = gmsh_geom.make_polygon(square).set_region(fr.region)
#         shapes.append(shape)
#
#     fracture_fragments = gmsh_geom.fragment(*shapes)
#     return fracture_fragments


# def make_mesh(config_dict, fractures, mesh_name, mesh_file):
#     geom = config_dict["geometry"]
#     fracture_mesh_step = geom['fracture_mesh_step']
#     dimensions = geom["box_dimensions"]
#     well_z0, well_z1 = geom["well_openning"]
#     well_length = well_z1 - well_z0
#     well_r = geom["well_effective_radius"]
#     well_dist = geom["well_distance"]
#     print("load gmsh api")
#
#     from gmsh_api import gmsh
#     from gmsh_api import options
#     from gmsh_api import field
#
#     factory = gmsh.GeometryOCC(mesh_name, verbose=True)
#     gopt = options.Geometry()
#     gopt.Tolerance = 0.0001
#     gopt.ToleranceBoolean = 0.001
#     # gopt.MatchMeshTolerance = 1e-1
#
#     # Main box
#     box = factory.box(dimensions).set_region("box")
#     side_z = factory.rectangle([dimensions[0], dimensions[1]])
#     side_y = factory.rectangle([dimensions[0], dimensions[2]])
#     side_x = factory.rectangle([dimensions[2], dimensions[1]])
#     sides = dict(
#         side_z0=side_z.copy().translate([0, 0, -dimensions[2] / 2]),
#         side_z1=side_z.copy().translate([0, 0, +dimensions[2] / 2]),
#         side_y0=side_y.copy().translate([0, 0, -dimensions[1] / 2]).rotate([-1, 0, 0], np.pi / 2),
#         side_y1=side_y.copy().translate([0, 0, +dimensions[1] / 2]).rotate([-1, 0, 0], np.pi / 2),
#         side_x0=side_x.copy().translate([0, 0, -dimensions[0] / 2]).rotate([0, 1, 0], np.pi / 2),
#         side_x1=side_x.copy().translate([0, 0, +dimensions[0] / 2]).rotate([0, 1, 0], np.pi / 2)
#     )
#     for name, side in sides.items():
#         side.modify_regions(name)
#
#     b_box = box.get_boundary().copy()
#
#     # two vertical cut-off wells, just permeable part
#     left_center = [-well_dist/2, 0, 0]
#     right_center = [+well_dist/2, 0, 0]
#     left_well = factory.cylinder(well_r, axis=[0, 0, well_z1 - well_z0]) \
#         .translate([0, 0, well_z0]).translate(left_center)
#     right_well = factory.cylinder(well_r, axis=[0, 0, well_z1 - well_z0]) \
#         .translate([0, 0, well_z0]).translate(right_center)
#     b_right_well = right_well.get_boundary()
#     b_left_well = left_well.get_boundary()
#
#     print("n fractures:", len(fractures))
#     fractures = create_fractures_rectangles(factory, fractures, factory.rectangle())
#     #fractures = create_fractures_polygons(factory, fractures)
#     fractures_group = factory.group(*fractures)
#     #fractures_group = fractures_group.remove_small_mass(fracture_mesh_step * fracture_mesh_step / 10)
#
#     # drilled box and its boundary
#     box_drilled = box.cut(left_well, right_well)
#
#     # fractures, fragmented, fractures boundary
#     print("cut fractures by box without wells")
#     fractures_group = fractures_group.intersect(box_drilled.copy())
#     print("fragment fractures")
#     box_fr, fractures_fr = factory.fragment(box_drilled, fractures_group)
#     print("finish geometry")
#     b_box_fr = box_fr.get_boundary()
#     b_left_r = b_box_fr.select_by_intersect(b_left_well).set_region(".left_well")
#     b_right_r = b_box_fr.select_by_intersect(b_right_well).set_region(".right_well")
#
#     box_all = []
#     for name, side_tool in sides.items():
#         isec = b_box_fr.select_by_intersect(side_tool)
#         box_all.append(isec.modify_regions("." + name))
#     box_all.extend([box_fr, b_left_r, b_right_r])
#
#     b_fractures = factory.group(*fractures_fr.get_boundary_per_region())
#     b_fractures_box = b_fractures.select_by_intersect(b_box).modify_regions("{}_box")
#     b_fr_left_well = b_fractures.select_by_intersect(b_left_well).modify_regions("{}_left_well")
#     b_fr_right_well = b_fractures.select_by_intersect(b_right_well).modify_regions("{}_right_well")
#     b_fractures = factory.group(b_fr_left_well, b_fr_right_well, b_fractures_box)
#     mesh_groups = [*box_all, fractures_fr, b_fractures]
#
#     print(fracture_mesh_step)
#     #fractures_fr.set_mesh_step(fracture_mesh_step)
#
#     factory.keep_only(*mesh_groups)
#     factory.remove_duplicate_entities()
#     factory.write_brep()
#
#     min_el_size = fracture_mesh_step / 10
#     fracture_el_size = np.max(dimensions) / 20
#     max_el_size = np.max(dimensions) / 8
#
#
#     fracture_el_size = field.constant(fracture_mesh_step, 10000)
#     frac_el_size_only = field.restrict(fracture_el_size, fractures_fr, add_boundary=True)
#     field.set_mesh_step_field(frac_el_size_only)
#
#     mesh = options.Mesh()
#     #mesh.Algorithm = options.Algorithm2d.MeshAdapt # produce some degenerated 2d elements on fracture boundaries ??
#     #mesh.Algorithm = options.Algorithm2d.Delaunay
#     #mesh.Algorithm = options.Algorithm2d.FrontalDelaunay
#     #mesh.Algorithm3D = options.Algorithm3d.Frontal
#     #mesh.Algorithm3D = options.Algorithm3d.Delaunay
#     mesh.ToleranceInitialDelaunay = 0.01
#     #mesh.ToleranceEdgeLength = fracture_mesh_step / 5
#     mesh.CharacteristicLengthFromPoints = True
#     mesh.CharacteristicLengthFromCurvature = True
#     mesh.CharacteristicLengthExtendFromBoundary = 2
#     mesh.CharacteristicLengthMin = min_el_size
#     mesh.CharacteristicLengthMax = max_el_size
#     mesh.MinimumCirclePoints = 6
#     mesh.MinimumCurvePoints = 2
#
#
#     #factory.make_mesh(mesh_groups, dim=2)
#     factory.make_mesh(mesh_groups)
#     factory.write_mesh(format=gmsh.MeshFormat.msh2)
#     os.rename(mesh_name + ".msh2", mesh_file)
#     #factory.show()
#
#
# def prepare_mesh(config_dict, fractures):
#     mesh_name = config_dict["mesh_name"]
#     mesh_file = mesh_name + ".msh"
#     if not os.path.isfile(mesh_file):
#         make_mesh(config_dict, fractures, mesh_name, mesh_file)
#
#     mesh_healed = mesh_name + "_healed.msh"
#     if not os.path.isfile(mesh_healed):
#         import heal_mesh
#         hm = heal_mesh.HealMesh.read_mesh(mesh_file, node_tol=1e-4)
#         hm.heal_mesh(gamma_tol=0.01)
#         hm.stats_to_yaml(mesh_name + "_heal_stats.yaml")
#         hm.write()
#         assert hm.healed_mesh_name == mesh_healed
#     return mesh_healed



if __name__ == "__main__":
    sample_dir = sys.argv[1]
    with open(os.path.join(script_dir, "config.yaml"), "r") as f:
        config_dict = yaml.safe_load(f)

    os.chdir(sample_dir)
    print("generate mesh")
    generate_mesh(config_dict)
    print("finished")

    # prepare_th_input(config_dict)
    # np.random.seed()
    # sample(config_dict)