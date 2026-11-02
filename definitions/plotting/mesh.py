"""
Surface geometry and vertex data
================================
VeryWiseMesh pairs vertex-wise data with an fsaverage mesh and background map,
and exposes the nilearn SurfaceImage objects that plot_surf() wants.

There is no local FreeSurfer branch: every template comes from nilearn's
fsaverage cache, which the app downloads once. Geometry is loaded through an
lru_cache keyed on (template, surface, background), so re-plotting after a
dropdown change never re-parses the meshes -- this is the main reason the app
feels responsive.
"""

from functools import lru_cache

import numpy as np
from nilearn.datasets import load_fsaverage, load_fsaverage_data
from nilearn.surface import SurfaceImage

from . import atlas
from .colormap import to_array

HEMIS = ('left', 'right')

# Vertex count per template, so data can be cropped without loading a mesh
FS_TEMPLATES = {
    'fsaverage': 163842,
    'fsaverage6': 40962,
    'fsaverage5': 10242,
    'fsaverage4': 2562,
    'fsaverage3': 642,
}

SURFACES = ('pial', 'inflated', 'white_matter', 'flat', 'sphere')

# Background map name -> nilearn data_type
BG_MAPS = {'sulc': 'sulcal', 'curv': 'curvature', 'none': None}


def _lighten(arr, darkness=0.3):
    """Compress a background map's dynamic range toward mid-grey.

    nilearn dropped plot_surf's `darkness` argument, so the background is
    flattened here instead: darkness=1 keeps the full range, 0 gives flat grey.
    """
    arr = np.asarray(arr, dtype=np.float32)

    lo, hi = np.nanmin(arr), np.nanmax(arr)
    if hi > lo:
        arr = (arr - lo) / (hi - lo)

    return 0.5 + (arr - 0.5) * darkness


@lru_cache(maxsize=16)
def load_geometry(fs_template, surface='pial', bg_map_type='sulc', darkness=0.3):
    """
    Load one template's mesh, background and bounding box (cached per session).

    Returns (poly_mesh, bg_img, mid, half) where `mid`/`half` describe a uniform
    cubic bounding box covering both hemispheres.
    """
    if fs_template not in FS_TEMPLATES:
        raise ValueError(f'Unknown fs_template {fs_template!r}. '
                         f'Choose one of {list(FS_TEMPLATES)}.')
    if surface not in SURFACES:
        raise ValueError(f'Unknown surface {surface!r}. Choose one of {list(SURFACES)}.')
    if bg_map_type not in BG_MAPS:
        raise ValueError(f'Unknown background {bg_map_type!r}. '
                         f'Choose one of {list(BG_MAPS)}.')

    poly_mesh = load_fsaverage(fs_template)[surface]

    bg_img = None
    if BG_MAPS[bg_map_type] is not None:
        bg = load_fsaverage_data(fs_template, mesh_type=surface,
                                 data_type=BG_MAPS[bg_map_type])
        bg_img = SurfaceImage(
            mesh=poly_mesh,
            data={h: _lighten(v, darkness) for h, v in bg.data.parts.items()})

    # Cubic bounding box, so every panel is scaled identically
    coords = np.vstack([np.asarray(p.coordinates) for p in poly_mesh.parts.values()])
    mid = (coords.max(axis=0) + coords.min(axis=0)) / 2.0
    half = (coords.max(axis=0) - coords.min(axis=0)).max() / 2.0 * 1.05

    return poly_mesh, bg_img, mid, half


class VeryWiseMesh:
    """
    Parameters
    ----------
    lh, rh : array-like or None
        Vertex-wise data per hemisphere. At least one is required.
    fs_template : str
        One of FS_TEMPLATES.
    surface : str
        One of SURFACES.
    bg_map_type : str
        One of BG_MAPS.

    Attributes
    ----------
    lh, rh : np.ndarray or None
        Validated arrays, cropped to the template's vertex count.
    hemi_present : list
        The hemispheres that actually carry data.
    hemis : 'left', 'right', or 'both'
    surf_img, bg_img : nilearn SurfaceImage
    roi, roi_img
        DK labels, loaded lazily -- untouched unless ROI names are requested.
    """

    def __init__(self, lh, rh, fs_template, surface='pial', bg_map_type='sulc',
                 darkness=0.3):
        self.fs_template = fs_template
        self.surface = surface
        self.bg_map_type = bg_map_type

        self.n_vertices = FS_TEMPLATES[fs_template]

        self.lh = self._match_mesh_size(to_array(lh), self.n_vertices)
        self.rh = self._match_mesh_size(to_array(rh), self.n_vertices)

        self.hemi_present = [h for h, d in zip(HEMIS, (self.lh, self.rh)) if d is not None]
        if not self.hemi_present:
            raise ValueError('No hemisphere data was given.')

        self.hemis = 'both' if len(self.hemi_present) > 1 else self.hemi_present[0]

        self.mesh, self.bg_img, self.mid, self.half = load_geometry(
            fs_template, surface, bg_map_type, darkness)

        # SurfaceImage needs a part per mesh part, so any absent hemisphere is
        # filled with NaN (which the colormap renders transparent anyway)
        self.surf_img = SurfaceImage(
            mesh=self.mesh,
            data={h: (self.data(h) if h in self.hemi_present
                      else np.full(self.n_vertices, np.nan, dtype=np.float32))
                  for h in HEMIS})

        self._roi = None
        self._roi_img = None

    def data(self, hemi):
        """Vertex data for one hemisphere."""
        return self.lh if hemi == 'left' else self.rh

    def scene_bbox(self):
        """Uniform cubic bounding box (mid, half) shared by every panel."""
        return self.mid, self.half

    # --- ROI labels (lazy: nothing is read unless regions are requested) -----

    @property
    def roi(self):
        if self._roi is None:
            self._roi = {h: atlas.roi_labels(h, self.n_vertices) for h in self.hemi_present}
        return self._roi

    @property
    def roi_img(self):
        if self._roi_img is None:
            self._roi_img = SurfaceImage(
                mesh=self.mesh,
                data={h: atlas.roi_labels(h, self.n_vertices)[0].astype(np.float32)
                      for h in HEMIS})
        return self._roi_img

    def roi_levels(self, roi_names):
        """Resolve DK region names to (levels, labels, colours)."""
        _, roi_labels = self.roi[self.hemi_present[0]]

        levels, labels, colors = [], [], []
        for name in roi_names:
            if name in roi_labels:
                level, color = roi_labels[name]
                levels.append(level)
                labels.append(name)
                colors.append(color)

        return levels, labels, colors

    # --- Convenience ---------------------------------------------------------

    @staticmethod
    def _match_mesh_size(data, target_len):
        """Crop data to the mesh vertex count (or raise if it is too short)."""
        if data is None:
            return None
        if len(data) > target_len:
            return data[:target_len]
        if len(data) < target_len:
            raise ValueError(f'The data has {len(data)} vertices, which is fewer '
                             f'than the {target_len} this resolution needs.')
        return data

    def __repr__(self):
        return (f'VeryWiseMesh({self.fs_template}, {self.surface}, '
                f'hemis={self.hemis}, n_vertices={self.n_vertices})')
