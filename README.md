# blender-scripts

[![CI](https://github.com/aljazmc/blender-scripts/actions/workflows/ci.yml/badge.svg)](https://github.com/aljazmc/blender-scripts/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-bpy-e87d0d?logo=blender&logoColor=white)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-Blender's%20own-3776ab?logo=python&logoColor=white)](https://docs.blender.org/api/current/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-gif-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ShellCheck](https://img.shields.io/badge/ShellCheck-checked-4eaa25?logo=gnubash&logoColor=white)](https://www.shellcheck.net/)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196?logo=conventionalcommits&logoColor=white)](https://www.conventionalcommits.org/)

Animated 3D scenes written as code. Python scripts build every object,
material, light, camera and keyframe in Blender through its `bpy` API, and a
shell script renders and exports them to images, videos and 3D formats, 37
in all.

![cyberpunk-butterfly00: a neon butterfly flying over a synthwave grid](gallery/cyberpunk-butterfly00.gif)

## Features

- **Scenes from code.** A project builds its whole scene, from meshes and
  shaders to the camera's flight path, in Blender's empty startup file.
- **37 outputs.** Still images, videos, an animated GIF, 3D formats for
  other programs, and the `.blend` file to keep editing in Blender.
- **One command per output.** `./project.sh <project> <format>` runs
  Blender in the background and fails when the script fails.
- **Nothing else to install.** Blender brings its own Python; FFmpeg is
  needed only for the GIF.
- **One subject in three tools.** The butterfly is also an SVG drawing in
  [inkscape-scripts](https://github.com/aljazmc/inkscape-scripts) and a
  raster painting in [gimp-scripts](https://github.com/aljazmc/gimp-scripts),
  with the same coordinates.

## Quick start

```sh
git clone https://github.com/aljazmc/blender-scripts.git
cd blender-scripts
./project.sh cyberpunk-butterfly00 mp4
```

The video is written to `build/cyberpunk-butterfly00.mp4`.

## Requirements

| Requirement | Notes |
| --- | --- |
| Blender | `blender` on the `PATH`; the scenes use the EEVEE renderer |
| FFmpeg | `ffmpeg` on the `PATH`, for the `gif` output only |

## Usage

```sh
./project.sh <project> <format>        # build one format
./project.sh <project> all             # build every format
./project.sh all <format>              # build every project
./project.sh <project> <format> clean  # remove one output
./project.sh <project> clean           # remove all outputs of a project
./project.sh clean                     # remove build/ and blend/
```

Outputs go to `build/<project>.<format>`, and `blend` outputs to
`blend/<project>.blend`. Existing outputs are skipped, so clean them to
rebuild. Run `./project.sh` from the repository root. Without arguments, it
prints the usage with every format and the first ten projects.

### Formats

| Kind | Formats |
| --- | --- |
| Still images | `png` `png100` `jpg` `webp` `avif` `bmp` `tif` `tga` `jp2` `exr` `hdr` `dpx` `cin` `rgb` |
| Videos | `mp4` `mkv` `webm` `mov` `avi` `ogv` `flv` `mpg` `vob` `dv` `gif` |
| 3D scenes | `glb` `gltf` `fbx` `abc` `usd` `usda` `usdc` `usdz` `obj` `ply` `stl` |
| Blender | `blend` |

- **Still images** render one 1920×1080 frame: `png` the middle frame of
  the animation, the others frame 100 (`png100` is written as
  `build/<project>100.png`).
- **Videos** render the whole animation at 1920×1080, except `dv`, which is
  PAL DV at 720×576 and 25 fps. `gif` renders it at 640×360 and assembles
  the frames with FFmpeg, using a palette made from the animation itself.
- **3D scenes** export the scene for other 3D programs. `abc`, `fbx`, `glb`,
  `gltf` and the USD formats keep the animation, and `glb` and `gltf` bake
  it and include the camera. `obj`, `ply` and `stl` hold only the geometry
  of the first frame. `gltf` writes `build/<project>.bin` next to it and
  `obj` writes `build/<project>.mtl`.
- **`blend`** saves the generated scene, to open and edit it in Blender.

## How it works

```
project.sh ──> blender -b -P scripts/export<format>.py -- <project>
                                    │
                                    ▼
                             scripts/common.py
                                    │ load_project()
                                    ▼
           scripts/<project>/<name>.py: <name>() builds the scene
                                    │
                                    ▼
                bpy.ops.render.render() or a bpy.ops exporter
```

- `project.sh` checks the arguments and runs Blender in the background
  (`-b`) with `scripts/export<format>.py` (or `scripts/saveblend.py`),
  passing the project after `--`. `--python-exit-code 1` makes a failing
  script fail the build.
- `scripts/common.py` imports the project, calls its function to build the
  scene in Blender's empty startup file and returns the output path.
- Each `scripts/export<format>.py` sets the render settings or calls the
  exporter for one format.

## Projects

A project is a folder `scripts/<theme>-<name>/` holding `<name>.py` with a
function `<name>()`, which builds the whole scene (objects, materials,
lights, camera, world and animation) from code:

```
scripts/cyberpunk-butterfly00/
└── butterfly00.py   # butterfly00() clears the scene and builds it
```

The last part of the folder name is the module and function name, so it
must be a valid Python name. A project needs nothing outside its folder.

`cyberpunk-butterfly00` is a ten second, 30 fps flight of a neon butterfly
over a synthwave grid towards a striped sun. It is the 3D version of the
drawing in [inkscape-scripts](https://github.com/aljazmc/inkscape-scripts),
whose pixel coordinates it keeps: the wings are meshes that flap and bend,
the glow comes from emission shaders and bloom, and the camera follows a
smoothed flight path. The GIF above was exported with
`./project.sh cyberpunk-butterfly00 gif` and reduced to 480×270 at 15 fps
with FFmpeg to keep the file small.

Themes such as `cyberpunk`, `steampunk`, `nature` and historical eras are
work in progress and kept out of the repository by `.gitignore` until they
are ready.

## Tests

```sh
for test in tests/sh/test_*.sh; do bash "$test"; done   # project.sh
python3 -m unittest discover tests/py                   # the scripts and the scenes
```

The tests are split by language: `tests/sh/` tests `project.sh` with bash,
`tests/py/` tests the Python scripts and the scenes they build. None of them
writes outputs into the repository.

The tests of `project.sh` run it in a temporary sandbox, with a few fake
projects and stand-ins for `blender` and `ffmpeg` (see `tests/sh/lib.sh`),
so they render nothing and never touch `build/` or `blend/`:

- `tests/sh/test_project.sh` checks that `project.sh` rejects bad arguments
  with its usage and exit code 1.
- `tests/sh/test_formats.sh` checks that the formats of `project.sh`, the
  exporters in `scripts/` and this README agree: every format has an
  exporter that writes its own file, every exporter is listed, the Formats
  table names every format, and the count of outputs is right.
- `tests/sh/test_outputs.sh` checks the names of the outputs, as described
  under Usage, through the `clean` commands, with the files some exporters
  write next to them (`.bin` for `gltf`, `.mtl` for `obj`).
- `tests/sh/test_run.sh` checks that `project.sh` runs Blender in the
  background with `--python-exit-code 1`, the right exporter and the project
  after `--`, for one project and for `all`; that it skips existing outputs,
  reports a failed export with exit code 1 and stops when `blender` or
  `ffmpeg` is missing.

The Python tests run on plain Python. `tests/py/test_common.py` needs
nothing else; the others build every project in Blender in the background,
from its factory startup file, and are skipped when `blender` is not on the
`PATH`. Each builds the scene, measures it inside Blender and checks the
measurements outside it (see `tests/py/blender.py`); together they take
seconds per project:

- `tests/py/test_common.py` checks that `load_project()` stops with a message
  when the project is missing or unknown.
- `tests/py/test_scene.py` checks the scene: a camera, the EEVEE renderer at
  1920×1080, a common frame rate, valid meshes without NaN coordinates, a
  material on every mesh, shaders and a world connected to their outputs (an
  unconnected output renders black), no missing image files (they render
  magenta), no objects outside the scene (they are neither rendered nor
  exported), and the same scene on every build.
- `tests/py/test_animation.py` steps through every frame: keyframes stay in
  the frame range, nothing jumps (a step much longer than the usual ones),
  the camera never turns more than 15° from one frame to the next, and the
  subject (what is animated, apart from the camera and lights) stays in
  front of the camera, with its centre inside the picture and big enough to
  see.
- `tests/py/test_render.py` renders five frames across the animation at
  160×90 and checks the pixels: neither black nor washed out, few blown-out
  pixels, enough contrast, frames that differ from each other, and a subject
  that shows: hiding it must change the picture.

Lint the code with [ShellCheck](https://www.shellcheck.net/) and
[Ruff](https://docs.astral.sh/ruff/):

```sh
shellcheck project.sh tests/sh/*.sh
ruff check .
```

GitHub Actions runs both on every push and pull request, see
[.github/workflows/lint.yml](.github/workflows/lint.yml).

## License

The scripts are licensed under the [MIT License](LICENSE). The files in
`gallery/` were made with them and are under the same license.

The scripts drive software that is not part of this repository and has
licenses of its own:

- [Blender](https://www.blender.org/about/license/) is free software under
  the GNU General Public License, version 2 or later; the Blender binaries
  as a whole are distributed under version 3 or later. These scripts use
  the `bpy` API and run inside Blender; Blender's license FAQ treats such
  scripts as covered by the GPL when they are distributed together with
  Blender, and the MIT license is compatible with the GPL. Whatever you
  render or export with Blender is yours, and the GPL does not apply to it.
- [FFmpeg](https://ffmpeg.org/legal.html) is licensed under the GNU LGPL,
  version 2.1 or later, or the GNU GPL, version 2 or later, depending on
  how it was built.
