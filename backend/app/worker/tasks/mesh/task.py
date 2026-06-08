import json
import os
import shutil
import subprocess
import sys

from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.common.utils import get_asset_upload_path, setup_output_directory


@celery.task(name="inspect_glb", base=AssetDatabaseTask)
def inspect_glb(options):
    return {
        'asset_type': None,
        'geometry_type': None,
        'payload': {'metadata': False, 'stats': False, 'sample': False, 'epsg': None, 'horizontal_epsg': None, 'vertical_epsg': None}
    }


# Skip full Blender import during inspection for very large OBJ files (extracted size).
_INSPECT_BLENDER_MAX_BYTES = 50 * 1024 * 1024


@celery.task(name="inspect_mesh", base=AssetDatabaseTask)
def inspect_mesh(options):
    from app.worker.tasks.mesh.utils import (
        estimate_mesh_size_from_obj,
        resolve_mesh_input_file,
    )

    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']

    input_file = resolve_mesh_input_file(asset_id, extension)
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Mesh file not found: {input_file}")

    obj_size_bytes = os.path.getsize(input_file)
    blender_verified = False
    mesh_size = None
    if input_file.lower().endswith(".obj"):
        mesh_size = estimate_mesh_size_from_obj(input_file)

    if obj_size_bytes <= _INSPECT_BLENDER_MAX_BYTES:
        import app.worker.tasks.mesh.mesh_tiling as mesh_tiling

        mesh_tiling.clean_up()
        merged, info = mesh_tiling.import_mesh(input_file)
        mesh_size = info.get('size') or mesh_size
        mesh_tiling.remove_obj(merged)
        mesh_tiling.clean_up()
        blender_verified = True

    payload = {
        'metadata': False,
        'stats': False,
        'sample': False,
        'epsg': None,
        'horizontal_epsg': None,
        'vertical_epsg': None,
        'obj_path': input_file,
        'obj_size_bytes': obj_size_bytes,
        'blender_verified': blender_verified,
    }
    if mesh_size:
        payload['size'] = mesh_size

    return {
        'asset_type': 'Mesh',
        'geometry_type': None,
        'payload': payload,
    }


@celery.task(name="create_mesh_3dtiles", base=PipelineDatabaseTask)
def create_mesh_3dtiles(pipeline_extended):
    asset = pipeline_extended['asset']
    asset_id = asset['id']
    pipeline_id = pipeline_extended['id']
    asset_extension = asset.get('extension', '.obj')

    pipeline_config = pipeline_extended.get('data') or {}

    default_config = {
        'latitude': 0,
        'longitude': 0,
        'altitude': 0,
        'depth': 4,
        'tile_faces_target': 10000,
        'texture_image_size': 512,
        'max_geometric_error': 256,
        'decimate_last_depth_level': False,
    }

    config = {**default_config, **pipeline_config}

    from app.worker.tasks.mesh.utils import resolve_mesh_input_file

    input_file = resolve_mesh_input_file(asset_id, asset_extension)
    output_paths = setup_output_directory(pipeline_id)
    os.makedirs(output_paths['output_path_3dtiles'], exist_ok=True)

    tiles_dir = output_paths['output_path_3dtiles']

    tiling_params = {
        'input_file': input_file,
        'output_dir': tiles_dir,
        'latitude': config['latitude'],
        'longitude': config['longitude'],
        'altitude': config['altitude'],
        'depth': config['depth'],
        'tile_faces_target': config['tile_faces_target'],
        'texture_image_size': config['texture_image_size'],
        'max_geometric_error': config['max_geometric_error'],
        'apply_transform': True,
        'decimate_last_depth_level': config['decimate_last_depth_level'],
        'create_tileset_json': False,
        'start_x': 0,
        'start_y': 0,
        'start_z': 0,
    }

    subprocess.run(
        [sys.executable, '-m', 'app.worker.tasks.mesh.run_tiling', json.dumps(tiling_params)],
        check=True,
    )

    from app.worker.tasks.mesh.finalize import finalize_mesh_3dtiles_output

    finalize_mesh_3dtiles_output(
        tiles_dir,
        config['depth'],
        config['max_geometric_error'],
    )

    shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', tiles_dir)

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip'],
    }
