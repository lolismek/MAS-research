"""Import-priority shim: makes `import utils` resolve to ChatDev's own
ecl/utils.py no matter what gets installed into the conda env.

ChatDev's Test phase auto-pip-installs missing modules reported by the
generated software (chat_env.py fix_module_not_found). If a generated game
imports `utils`, ChatDev installs the PyPI `utils` package, which then
shadows ecl/utils.py for every later run — ecl/memory.py only *appends*
ecl/ to sys.path (after site-packages). This dir is put on PYTHONPATH, which
precedes site-packages, and contains only this file, so it wins the import
race and simply re-exports the real module. (Original MAST runs were
containerized per task, so the contamination could not occur there.)
"""
import importlib.util as _ilu
import os as _os

# chatdev_repo lives one level up from this shim dir (chatdev/harness/chatdev_repo);
# honor CHATDEV_REPO so the shim and run_task.py resolve to the same clone.
_repo = _os.environ.get('CHATDEV_REPO') or _os.path.join(
    _os.path.dirname(__file__), '..', 'chatdev_repo')
_real = _os.path.abspath(_os.path.join(_repo, 'ecl', 'utils.py'))
_spec = _ilu.spec_from_file_location('utils', _real)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith('__')})
