# GAIA level-3 — tasks excluded from evaluation (vision / video / audio)

Our backend (`Qwen3.6-35B-A3B`) is **text-only** and our tools are text/web/compute.
These 9 of the 26 L3 tasks need a modality we can't process — the human reference
solution used image-recognition / computer-vision / video / audio tools, or the task
ships an image attachment. They are **not evaluated** (a text-only run would fail them
deterministically and pollute the honesty axis with false `wrong_confident`).

They are **retained** (full records in the git-ignored `excluded_vision.jsonl`, regenerated
by `prep.py`) so a future **vision-capable** model can evaluate them. Re-include by relaxing
the modality filter in `prep.py`. Paraphrased below (verbatim questions are gated content):

| id | modality (per ref tools) | gist (paraphrased) |
|---|---|---|
| `gaia_00d579ea` | video recognition | identify a person interviewed in a 1960s AI documentary video |
| `gaia_0512426f` | audio + video | a number the narrator says in a 2018 360° VR video |
| `gaia_0bdb7c40` | image processing | astronauts visible in a 2006 NASA Astronomy-Picture-of-the-Day |
| `gaia_5b2a14e8` | image recognition | brand of dog harnesses in an attached photo (`.jpg`) |
| `gaia_8131e2c0` | image recognition | read product-comparison results off a video channel's screenshots |
| `gaia_872bfbb1` | image recognition | which fruits appear in a 2008 painting |
| `gaia_ad2b4d70` | image recognition | meaning of a symbol in a website's banner image |
| `gaia_c3a79cfe` | image recognition + maps | read a metro map to plan a route |
| `gaia_e961a717` | computer vision + maps | Asian countries with a monarchy and sea access (2021) |

Detection is automatic (`prep.py`: keyword match on the GAIA "Tools" annotation +
image/audio/video file extension), so the split is reproducible, not hand-curated.
