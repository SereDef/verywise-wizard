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
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np

# How long to wait for the probe render or the browser download before giving
# up. A browser that cannot launch sometimes hangs rather than failing, and
# that must not block the app.
PROBE_TIMEOUT = 180

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


# ===== CAN THIS MACHINE ACTUALLY PRODUCE A PNG? ===============================

def _run_bounded(fn):
    """Run `fn` in a worker, so a hung browser cannot block the app forever."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return bool(pool.submit(fn).result(timeout=PROBE_TIMEOUT))
    except Exception:
        # A timeout, a crash, a missing browser -- all mean "no" here
        return False
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _probe_png():
    """Render a tiny PNG, to prove the whole chain really works."""
    import plotly.graph_objects as go

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = os.path.join(tmp_dir, 'probe.png')

        # 10x10 is plotly's smallest allowed figure size
        go.Figure(layout={'width': 10, 'height': 10}).write_image(out_file, format='png')

        return os.path.getsize(out_file) > 0


def _fetch_chrome():
    """Download the headless Chrome kaleido drives (~150 MB), once per machine."""
    from plotly.io import get_chrome

    get_chrome()
    chrome_available.cache_clear()

    return True


@lru_cache(maxsize=1)
def png_export_ready(allow_download=True):
    """
    Whether a PNG can actually be produced here.

    Looking for a chrome binary is not enough: a container may carry one that
    cannot launch, and then `write_image` fails only once the user has already
    asked for the download. The sole reliable check is to render something tiny
    and see whether bytes come out. Cached, so it costs one browser start-up
    per process.
    """
    patch_kaleido()

    if _run_bounded(_probe_png):
        return True

    if not allow_download:
        return False

    # kaleido ships no browser and pip cannot install one, so fetch the
    # headless Chrome it drives and try once more.
    if not _run_bounded(_fetch_chrome):
        return False

    return _run_bounded(_probe_png)
