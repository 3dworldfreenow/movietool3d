# Rules for AI coding agents

movietool3d is Stick 3D on its own (split out of Stickman Studio in October 2026).

## Where things are
- `main.py`: the command line (`render`, `validate`, `storyboard` ...); `stick3d_server.py`: the web page.
- `engine/stick3d.py` (renderer), `stick3d_places.py`, `stick3d_animals.py`, `stick3d_props.py`, `stick3d_fx.py`,
  `stick3d_screens.py`; the rest of `engine/` is the shared timeline, voices, sound and video.
- `stories/`, `prompts/story_to_json_prompt_stick3d.md`, `tools/`.

## Rules
1. Python on the server; plain JavaScript in the browser. No Node.js, npm, bundlers or build steps.
2. Never commit `config.json` (keys), `assets/voices/`, `output/`, `cache/`, `logs/` or `stories/mine/`.
3. Tests that write data use a temporary folder.
4. Match the code style around you: short comments that explain the physics, the same naming.
