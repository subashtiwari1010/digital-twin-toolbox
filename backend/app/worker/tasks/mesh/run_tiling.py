"""Run mesh tiling in an isolated process so Blender teardown cannot kill the Celery worker."""
import json
import sys


def main() -> None:
    from app.worker.tasks.mesh import mesh_tiling

    params = json.loads(sys.argv[1])
    params['create_tileset_json'] = False
    mesh_tiling.run(params)


if __name__ == '__main__':
    main()
