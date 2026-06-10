import os
import zipfile
from pathlib import Path

from app.worker.common.utils import get_asset_upload_path
from app.worker.tasks.citygml.processes import run_citygml_tools_merge

GML_ARCHIVE_EXTENSIONS = {".gml.zip"}


def _is_gml_candidate(relative_path: str) -> bool:
    if not relative_path.lower().endswith(".gml"):
        return False
    parts = Path(relative_path).parts
    if any(part == "__MACOSX" for part in parts):
        return False
    basename = Path(relative_path).name
    if basename.startswith("._") or basename.startswith("."):
        return False
    return True


def find_gml_paths(directory: str) -> list[str]:
    candidates = []
    for root, _, files in os.walk(directory):
        for name in files:
            relative = os.path.relpath(os.path.join(root, name), directory)
            if _is_gml_candidate(relative):
                candidates.append(os.path.join(root, name))
    candidates.sort()
    return candidates


def extract_gml_archive(archive_path: str, extract_dir: str) -> list[str]:
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(extract_dir)
    gml_paths = find_gml_paths(extract_dir)
    if not gml_paths:
        raise FileNotFoundError(f"No .gml file found under {extract_dir}")
    return gml_paths


def resolve_citygml_input_file(asset_id: str, extension: str) -> str:
    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")
    if extension not in GML_ARCHIVE_EXTENSIONS:
        return asset_file_path

    extract_dir = get_asset_upload_path(f"{asset_id}/extracted")
    marker = os.path.join(extract_dir, ".resolved_gml")
    if os.path.isfile(marker):
        with open(marker) as handle:
            resolved = handle.read().strip()
        if os.path.isfile(resolved):
            return resolved

    if os.path.isdir(extract_dir):
        for root, dirs, files in os.walk(extract_dir, topdown=False):
            for name in files:
                if name == ".resolved_gml":
                    continue
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

    gml_paths = extract_gml_archive(asset_file_path, extract_dir)
    if len(gml_paths) == 1:
        resolved = gml_paths[0]
    else:
        merged_path = os.path.join(extract_dir, "merged.gml")
        run_citygml_tools_merge(gml_paths, merged_path)
        resolved = merged_path

    with open(marker, "w") as handle:
        handle.write(resolved)
    return resolved
