import json
import os
import shutil

from app.worker.tasks.mesh.create_tileset import run as create_tileset_run


def finalize_mesh_3dtiles_output(tiles_dir: str, depth: int, max_geometric_error: float) -> None:
    """Build tileset.json and zip without loading Blender (safe after mesh_tiling.run)."""
    tileset_path = os.path.join(tiles_dir, 'tileset.json')
    if os.path.isfile(tileset_path):
        return

    tileset_info = {}
    meta_path = os.path.join(tiles_dir, '_mesh_tileset_meta.json')
    root_info_path = os.path.join(tiles_dir, '0_0_0.json')

    if os.path.isfile(meta_path):
        with open(meta_path) as f:
            tileset_info = json.load(f)
    elif os.path.isfile(root_info_path):
        with open(root_info_path) as f:
            tileset_info = json.load(f)

    tileset = create_tileset_run({
        **tileset_info,
        'depth': depth,
        'output_dir': tiles_dir,
        'max_geometric_error': max_geometric_error,
    })
    with open(tileset_path, 'w') as f:
        json.dump(tileset, f)
