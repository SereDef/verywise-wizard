"""
Desikan-Killiany (aparc) ROI labels
===================================
`data/fsaverage_aparc.npz` was packed once from the `aparc.annot` shipped with
the verywise R package (`R/sysdata.rda`), so the app needs neither a local
FreeSurfer installation nor a download. It holds, at full fsaverage resolution:

    lh, rh  : int16 label level per vertex (-1 = unlabelled, i.e. medial wall)
    names   : region name per level (index == level, names[0] == 'unknown')
    colors  : FreeSurfer hex colour per level

fsaverage meshes are nested -- fsaverage5 is the first 10242 vertices of
fsaverage -- so a lower resolution is just a crop of the full-resolution map.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np

ATLAS_FILE = Path(__file__).parent / 'data' / 'fsaverage_aparc.npz'

UNLABELLED = -1


@lru_cache(maxsize=1)
def _load_atlas():
    """Read the packed atlas once per session."""
    with np.load(ATLAS_FILE) as d:
        return (d['lh'], d['rh'],
                tuple(str(n) for n in d['names']),
                tuple(str(c) for c in d['colors']))


def region_names():
    """All DK region names, ordered by label level."""
    return _load_atlas()[2]


def roi_labels(hemi, n_vertices):
    """
    ROI labels for one hemisphere, cropped to `n_vertices`.

    Returns (roi_map, labels) where `roi_map` holds the label level per vertex
    and `labels` maps {region_name: (level, hex_colour)} -- the shape
    VeryWiseMesh.roi and VeryWiseMesh.roi_levels() expect.
    """
    lh, rh, names, colors = _load_atlas()

    full = lh if hemi == 'left' else rh
    if n_vertices > len(full):
        raise ValueError(f'The atlas only covers {len(full)} vertices, '
                         f'but {n_vertices} were requested.')

    labels = {name: (level, colors[level]) for level, name in enumerate(names)}

    return full[:n_vertices], labels
