"""
Kaleido compatibility shims
===========================
Only needed for the PNG download; `patch_kaleido()` is called lazily, right
before `write_image()`, so nothing here runs unless someone asks for a figure.

Two problems are patched:

1. kaleido v1 serialises figures with orjson, which refuses the big-endian
   numpy arrays that come out of FreeSurfer surface files. The shim swaps in a
   stdlib-json drop-in that converts them on the way out.
2. Headless Chrome needs explicit flags to run inside a container (no GPU, no
   sandbox), which is how the app is deployed.

Trimmed from the verywise R package's patch_kaleido.py, dropping the HPC/Xvfb
handling that only applies when driving kaleido from R on a cluster.
"""

import importlib
import json
import pathlib
import platform
import os
import shutil
import sys
from functools import lru_cache

import numpy as np

_PATCHED = False

# kaleido v1 does not ship a browser (v0.2.1 did, but plotly >= 6 refuses to use
# it). It drives an installed Chrome/Chromium through choreographer, or one
# choreographer downloaded earlier. A container built from requirements.txt
# alone has neither, and pip cannot supply one -- so the app has to be able to
# tell, and say so, rather than fail obscurely on the download button.
CHROME_BINARIES = ('chromium', 'chromium-browser', 'google-chrome',
                   'google-chrome-stable', 'chrome')

CHROME_APP_PATHS = (
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
)


@lru_cache(maxsize=1)
def chrome_available():
    """Whether a browser kaleido can drive is present on this machine."""
    if os.environ.get('KALEIDO_CHROME_PATH'):  # explicit override
        return True

    if any(shutil.which(name) for name in CHROME_BINARIES):
        return True

    if any(os.path.exists(path) for path in CHROME_APP_PATHS):
        return True

    # choreographer's own download cache, if Chrome was fetched before
    cache = pathlib.Path.home() / '.local' / 'share' / 'choreographer'
    return cache.is_dir() and any(cache.rglob('chrome*'))


class _OrjsonShim:
    """Minimal stdlib-json stand-in for the parts of orjson kaleido uses."""

    OPT_NON_STR_KEYS = 1
    OPT_SERIALIZE_NUMPY = 2
    OPT_INDENT_2 = 4

    class JSONDecodeError(ValueError):
        pass

    @staticmethod
    def dumps(obj, *args, option=None, **kwargs):
        def _default(o):
            if isinstance(o, np.ndarray):
                # Force native byte order, which is what orjson choked on
                return o.astype(o.dtype.newbyteorder('='), copy=False).tolist()
            if isinstance(o, np.generic):
                return o.item()
            raise TypeError(f'Object of type {type(o).__name__} is not JSON serializable')

        return json.dumps(obj, default=_default).encode()

    @staticmethod
    def loads(s):
        return json.loads(s)


def _patch_orjson():
    try:
        import orjson  # noqa: F401  (imported only to check it is there)
    except ImportError:
        return  # kaleido will fall back to stdlib json on its own

    sys.modules['orjson'] = _OrjsonShim()

    # kaleido may already hold a reference to the real orjson
    try:
        from kaleido._kaleido_tab import _tab
        importlib.reload(_tab)
    except (ImportError, ModuleNotFoundError, AttributeError):
        pass


def _patch_chrome_args():
    if 'KALEIDO_CHROME_ARGS' in os.environ:
        return  # respect an explicit override

    if platform.system() == 'Darwin':
        os.environ['KALEIDO_CHROME_ARGS'] = '--headless=new --no-sandbox'
    elif platform.system() == 'Linux':
        # Software rendering, for a container with no GPU
        os.environ['KALEIDO_CHROME_ARGS'] = (
            '--headless=new --no-sandbox --disable-dev-shm-usage '
            '--use-gl=angle --use-angle=swiftshader --ignore-gpu-blocklist')
    # On Windows, leave kaleido's defaults alone


def patch_kaleido():
    """Apply both shims once per session."""
    global _PATCHED
    if _PATCHED:
        return

    _patch_orjson()
    _patch_chrome_args()

    _PATCHED = True
