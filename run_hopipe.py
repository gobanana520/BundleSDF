from bundlesdf import *
import argparse
import os, sys

PROJ_ROOT = os.path.dirname(os.path.realpath(__file__))
if PROJ_ROOT not in sys.path:
    sys.path.append(PROJ_ROOT)


def make_clean_folder(folder):
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)


def run_one_video(sequence_folder, serial, use_gui=False):
    reader = HoPipeReader(sequence_folder=sequence_folder)
    mask_folder = os.path.join(reader.mask_folder, serial)
    print(f"Mask folder: {mask_folder}")
    if not os.path.exists(mask_folder):
        print(f"Mask folder {mask_folder} does not exist, skip...")
        return

    set_seed(0)

    # make clean output folder
    out_folder = os.path.abspath(
        os.path.join(sequence_folder, f"data_processing/bundlesdf/one_video/{serial}")
    )
    make_clean_folder(out_folder)

    cfg_bundletrack = yaml.load(open(f"{PROJ_ROOT}/BundleTrack/config_ho3d.yml", "r"))
    cfg_bundletrack["SPDLOG"] = int(args.debug_level)
    cfg_bundletrack["depth_processing"]["zfar"] = 2
    cfg_bundletrack["depth_processing"]["percentile"] = 95
    cfg_bundletrack["erode_mask"] = 3
    cfg_bundletrack["debug_dir"] = out_folder + "/"
    cfg_bundletrack["bundle"]["max_BA_frames"] = 10
    cfg_bundletrack["bundle"]["max_optimized_feature_loss"] = 0.03
    cfg_bundletrack["feature_corres"]["max_dist_neighbor"] = 0.02
    cfg_bundletrack["feature_corres"]["max_normal_neighbor"] = 30
    cfg_bundletrack["feature_corres"]["max_dist_no_neighbor"] = 0.01
    cfg_bundletrack["feature_corres"]["max_normal_no_neighbor"] = 20
    cfg_bundletrack["feature_corres"]["map_points"] = True
    cfg_bundletrack["feature_corres"]["resize"] = 400
    cfg_bundletrack["feature_corres"]["rematch_after_nerf"] = True
    cfg_bundletrack["keyframe"]["min_rot"] = 5
    cfg_bundletrack["ransac"]["inlier_dist"] = 0.01
    cfg_bundletrack["ransac"]["inlier_normal_angle"] = 20
    cfg_bundletrack["ransac"]["max_trans_neighbor"] = 0.05
    cfg_bundletrack["ransac"]["max_rot_deg_neighbor"] = 30
    cfg_bundletrack["ransac"]["max_trans_no_neighbor"] = 0.01
    cfg_bundletrack["ransac"]["max_rot_no_neighbor"] = 10
    cfg_bundletrack["p2p"]["max_dist"] = 0.02
    cfg_bundletrack["p2p"]["max_normal_angle"] = 45
    cfg_track_dir = f"{out_folder}/config_bundletrack.yml"
    yaml.dump(cfg_bundletrack, open(cfg_track_dir, "w"))

    cfg_nerf = yaml.load(open(f"{PROJ_ROOT}/config.yml", "r"))
    cfg_nerf["continual"] = True
    cfg_nerf["trunc_start"] = 0.01
    cfg_nerf["trunc"] = 0.01
    cfg_nerf["mesh_resolution"] = 0.005
    cfg_nerf["down_scale_ratio"] = 1
    cfg_nerf["fs_sdf"] = 0.1
    cfg_nerf["far"] = cfg_bundletrack["depth_processing"]["zfar"]
    # cfg_nerf['sync_max_delay'] = np.inf
    cfg_nerf["datadir"] = f"{cfg_bundletrack['debug_dir']}/nerf_with_bundletrack_online"
    cfg_nerf["notes"] = ""
    cfg_nerf["expname"] = "nerf_with_bundletrack_online"
    cfg_nerf["save_dir"] = cfg_nerf["datadir"]
    cfg_nerf_dir = f"{out_folder}/config_nerf.yml"
    yaml.dump(cfg_nerf, open(cfg_nerf_dir, "w"))

    tracker = BundleSdf(
        cfg_track_dir=cfg_track_dir,
        cfg_nerf_dir=cfg_nerf_dir,
        start_nerf_keyframes=3,
        use_gui=use_gui,
    )
    for i in range(reader.num_frames):
        color = reader.get_color(serial, i)
        depth = reader.get_depth(serial, i)
        mask = reader.get_mask(serial, i)

        if cfg_bundletrack["erode_mask"] > 0:
            kernel = np.ones(
                (cfg_bundletrack["erode_mask"], cfg_bundletrack["erode_mask"]), np.uint8
            )
            mask = cv2.erode(mask.astype(np.uint8), kernel)

        id_str = f"{i:06d}"
        pose_in_model = np.eye(4)
        K = reader.Ks[serial]

        tracker.run(
            color,
            depth,
            K,
            id_str,
            mask=mask,
            occ_mask=None,
            pose_in_model=pose_in_model,
        )
    tracker.on_finish()

    # global refine nerf
    run_one_video_global_nerf(out_folder=out_folder)

    # postprocess mesh
    postprocess_mesh(out_folder=out_folder)


def run_one_video_global_nerf(out_folder):
    set_seed(0)

    cfg_bundletrack = yaml.load(open(f"{out_folder}/config_bundletrack.yml", "r"))
    cfg_bundletrack["debug_dir"] = out_folder + "/"
    cfg_track_dir = f"{out_folder}/config_bundletrack.yml"
    yaml.dump(cfg_bundletrack, open(cfg_track_dir, "w"))

    cfg_nerf = yaml.load(open(f"{out_folder}/config_nerf.yml", "r"))
    cfg_nerf["n_step"] = 1000
    cfg_nerf["N_samples"] = 64
    cfg_nerf["N_samples_around_depth"] = 256
    cfg_nerf["first_frame_weight"] = 1
    cfg_nerf["down_scale_ratio"] = 1
    cfg_nerf["finest_res"] = 256
    cfg_nerf["num_levels"] = 16
    cfg_nerf["mesh_resolution"] = 0.005
    cfg_nerf["n_train_image"] = 500
    cfg_nerf["fs_sdf"] = 0.1
    cfg_nerf["frame_features"] = 2
    cfg_nerf["rgb_weight"] = 100

    cfg_nerf["i_img"] = 200
    cfg_nerf["i_mesh"] = cfg_nerf["i_img"]
    cfg_nerf["i_nerf_normals"] = cfg_nerf["i_img"]
    cfg_nerf["i_save_ray"] = cfg_nerf["i_img"]

    cfg_nerf["datadir"] = f"{out_folder}/nerf_with_bundletrack_online"
    cfg_nerf["save_dir"] = copy.deepcopy(cfg_nerf["datadir"])

    os.makedirs(cfg_nerf["datadir"], exist_ok=True)

    cfg_nerf_dir = f"{cfg_nerf['datadir']}/config.yml"
    yaml.dump(cfg_nerf, open(cfg_nerf_dir, "w"))

    tracker = BundleSdf(
        cfg_track_dir=cfg_track_dir, cfg_nerf_dir=cfg_nerf_dir, start_nerf_keyframes=3
    )
    tracker.cfg_nerf = cfg_nerf
    tracker.run_global_nerf(get_texture=False, tex_res=512)
    tracker.on_finish()

    print(f"Done")


def postprocess_mesh(out_folder):
    mesh_files = sorted(
        glob.glob(f"{out_folder}/**/nerf/*normalized_space.obj", recursive=True)
    )
    print(f"Using {mesh_files[-1]}")
    os.makedirs(f"{out_folder}/mesh/", exist_ok=True)

    print(f"\nSaving meshes to {out_folder}/mesh/\n")

    mesh = trimesh.load(mesh_files[-1])
    with open(f"{os.path.dirname(mesh_files[-1])}/config.yml", "r") as ff:
        cfg = yaml.load(ff)
    tf = np.eye(4)
    tf[:3, 3] = cfg["translation"]
    tf1 = np.eye(4)
    tf1[:3, :3] *= cfg["sc_factor"]
    tf = tf1 @ tf
    mesh.apply_transform(np.linalg.inv(tf))
    mesh.export(f"{out_folder}/mesh/mesh_real_scale.obj")

    components = trimesh_split(mesh, min_edge=1000)
    best_component = None
    best_size = 0
    for component in components:
        dists = np.linalg.norm(component.vertices, axis=-1)
        if len(component.vertices) > best_size:
            best_size = len(component.vertices)
            best_component = component
    mesh = trimesh_clean(best_component)

    mesh.export(f"{out_folder}/mesh/mesh_biggest_component.obj")
    mesh = trimesh.smoothing.filter_laplacian(
        mesh,
        lamb=0.5,
        iterations=3,
        implicit_time_integration=False,
        volume_constraint=True,
        laplacian_operator=None,
    )
    mesh.export(f"{out_folder}/mesh/mesh_biggest_component_smoothed.obj")


def args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequence_folder", type=str, required=True)
    parser.add_argument("--serial", type=str, required=True)
    parser.add_argument("--use_gui", type=int, default=1, help="use gui or not")
    parser.add_argument(
        "--debug_level", type=int, default=2, help="higher means more logging"
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = args_parser()

    run_one_video(
        sequence_folder=args.sequence_folder,
        serial=args.serial,
        use_gui=args.use_gui,
    )