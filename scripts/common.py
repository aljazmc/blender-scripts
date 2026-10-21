import importlib
import os
import sys

scripts_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(scripts_dir)


def load_project(target):
    """Build the scene of the project passed after "--" and return the output
    path (without extension) inside the root-level target directory.

    A project scripts/<theme>-<name>/ must provide <name>.py with a <name>()
    function, e.g. scripts/cyberpunk-butterfly00/butterfly00.py:butterfly00().
    """
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not args:
        sys.exit("usage: blender -b -P <script> -- <project>")

    project = args[0]
    project_dir = os.path.join(scripts_dir, project)
    if not os.path.isdir(project_dir):
        sys.exit(f"project not found: {project_dir}")

    name = project.rsplit("-", 1)[-1]
    sys.path.insert(0, project_dir)
    getattr(importlib.import_module(name), name)()

    target_dir = os.path.join(root_dir, target)
    os.makedirs(target_dir, exist_ok=True)

    return os.path.join(target_dir, project)
