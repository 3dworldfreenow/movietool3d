# 🧊 movietool3d - Stick 3D

The doodle 3D film engine of Stickman Studio, on its own: a story JSON goes in, a voiced MP4 comes out.

## Setup
1. Python 3.10+ and FFmpeg: `sudo apt install python3-pip ffmpeg libcairo2-dev pkg-config`
2. `pip install -r requirements.txt`
3. Voices (offline, ~0.7 GB): `python tools/get_piper_voices.py` (or use `--tts edge`: online, nothing to download)
4. Real sounds (optional): `python tools/get_sound_pack.py`

## Render
Command line:

    python main.py render stories/village_tales/bhediya_aaya.json --tts piper --resolution 1280x720 --no-hook

Web page:

    STICK3D_PASSWORD=your-secret python stick3d_server.py --host 0.0.0.0 --port 8000

Open `http://<server>:8000`, pick, paste or upload a story, Render, then watch or download the video.
With no `STICK3D_PASSWORD` the page only answers on the same computer.

## Writing stories
`prompts/story_to_json_prompt_stick3d.md` is the Stick 3D prompt: paste it into any AI with your idea, then paste
the JSON answer into the page (or save it under `stories/`).
