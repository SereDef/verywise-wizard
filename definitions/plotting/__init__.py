"""
verywise wizard surface plotting
================================
A fork of the plotting engine in the verywise R package
(`inst/python/plot_vw_surf.py`), split into modules and adapted for the app:
no local FreeSurfer is required, geometry is cached between redraws, and the
side panel can be detached from the brains.

Modules
-------
atlas      : Desikan-Killiany ROI labels, packed as an npz
mesh       : VeryWiseMesh      -- vertex data + fsaverage geometry (cached)
colormap   : VeryWiseColormap  -- colour scale, limits, ticks, band mask
cameras    : VeryWiseCameraPresets
layout     : VeryWiseLayout    -- the (rows, cols, panels) grid
panels     : colorbar / density / cluster-means traces
plotters   : VeryWiseStaticPlotter, VeryWiseInteractivePlotter

Public API
----------
surf_figure   -> plotly Figure of the brains (what the app shows)
panel_figure  -> plotly Figure of the colorbar + density / cluster means
surf_png      -> multi-view PNG file path
surf_html     -> standalone interactive HTML file path
"""

from .cameras import VIEWS, VeryWiseCameraPresets
from .colormap import VeryWiseColormap, threshold, to_array
from .layout import VeryWiseLayout
from .mesh import BG_MAPS, FS_TEMPLATES, SURFACES, VeryWiseMesh
from .panels import CLUSTERS, COLORBAR, DENSITY, side_panel_figure
from .plotters import VeryWiseInteractivePlotter, VeryWiseStaticPlotter

__all__ = [
    'BG_MAPS', 'CLUSTERS', 'COLORBAR', 'DENSITY', 'FS_TEMPLATES', 'SURFACES', 'VIEWS',
    'VeryWiseCameraPresets', 'VeryWiseColormap', 'VeryWiseInteractivePlotter',
    'VeryWiseLayout', 'VeryWiseMesh', 'VeryWiseStaticPlotter',
    'panel_figure', 'surf_figure', 'surf_html', 'surf_png', 'threshold', 'to_array',
]


def _build(lh, rh, lh_mask=None, rh_mask=None, cmap=None, vmin=None, vmax=None,
           discrete=None, fs_template='fsaverage6', surface='pial',
           bg_map_type='sulc', views='all', mode='static'):
    """Shared set-up: resolve the colour scale, then the mesh and the grid."""
    lh_arr, rh_arr = to_array(lh), to_array(rh)

    colormap = VeryWiseColormap(lh_arr, rh_arr, lh_mask=lh_mask, rh_mask=rh_mask,
                                cmap=cmap, vmin=vmin, vmax=vmax, discrete=discrete)

    # The colormap sees every observed value; the surface only shows the
    # significant ones.
    mesh = VeryWiseMesh(threshold(lh_arr, lh_mask), threshold(rh_arr, rh_mask),
                        fs_template, surface, bg_map_type)

    layout = VeryWiseLayout(mesh.hemis, views, mode=mode)

    return mesh, colormap, layout


def surf_figure(lh, rh, lh_mask=None, rh_mask=None, cmap=None, vmin=None, vmax=None,
                discrete=None, fs_template='fsaverage6', surface='pial',
                bg_map_type='sulc', views='lateral', title=None, roi_names=None,
                hover_roi=True, cell_px=None, side_panel=False,
                colorbar_label=None, mode=DENSITY, stats=None):
    """
    Interactive figure of the brains, for the app.

    By default the colorbar is *not* included: use `panel_figure()` for that, so
    the brain card can be expanded on its own.
    """
    mesh, colormap, layout = _build(
        lh, rh, lh_mask, rh_mask, cmap, vmin, vmax, discrete,
        fs_template, surface, bg_map_type, views, mode='interactive')

    plotter = VeryWiseInteractivePlotter(mesh, colormap, layout,
                                         roi_names=roi_names, hover_roi=hover_roi)

    return plotter.render(side_panel=side_panel, colorbar_label=colorbar_label,
                          title=title, mode=mode, stats=stats, cell_px=cell_px)


def panel_figure(lh, rh, lh_mask=None, rh_mask=None, cmap=None, vmin=None, vmax=None,
                 discrete=None, label=None, mode=DENSITY, stats=None,
                 width=260, height=420, tick_text=None):
    """
    The colorbar plus either the density of observed values or the per-cluster
    means, as a figure of its own.

    Takes the same data as `surf_figure()` so the two always agree on the scale.
    """
    colormap = VeryWiseColormap(to_array(lh), to_array(rh),
                                lh_mask=lh_mask, rh_mask=rh_mask,
                                cmap=cmap, vmin=vmin, vmax=vmax, discrete=discrete)

    return side_panel_figure(colormap, label=label, mode=mode, stats=stats,
                             width=width, height=height, tick_text=tick_text)


def surf_png(lh, rh, output_file, lh_mask=None, rh_mask=None, cmap=None,
             vmin=None, vmax=None, discrete=None, fs_template='fsaverage6',
             surface='pial', bg_map_type='sulc', views='all', title=None,
             roi_names=None, colorbar_label=None, mode=DENSITY, stats=None,
             tick_text=None, cell_px=None, dpi=150):
    """Render a static multi-view PNG. Returns the file path."""
    mesh, colormap, layout = _build(
        lh, rh, lh_mask, rh_mask, cmap, vmin, vmax, discrete,
        fs_template, surface, bg_map_type, views, mode='static')

    plotter = VeryWiseStaticPlotter(mesh, colormap, layout, roi_names=roi_names)

    return plotter.render(side_panel=True, colorbar_label=colorbar_label,
                          title=title, mode=mode, stats=stats,
                          tick_text=tick_text, cell_px=cell_px,
                          output_file=output_file, dpi=dpi)


def surf_html(lh, rh, output_html, lh_mask=None, rh_mask=None, cmap=None,
              vmin=None, vmax=None, discrete=None, fs_template='fsaverage6',
              surface='pial', bg_map_type='sulc', views='all', title=None,
              roi_names=None, hover_roi=True, colorbar_label=None,
              mode=DENSITY, stats=None, tick_text=None, cell_px=None):
    """Render a standalone interactive HTML file. Returns the file path."""
    mesh, colormap, layout = _build(
        lh, rh, lh_mask, rh_mask, cmap, vmin, vmax, discrete,
        fs_template, surface, bg_map_type, views, mode='interactive')

    plotter = VeryWiseInteractivePlotter(mesh, colormap, layout,
                                         roi_names=roi_names, hover_roi=hover_roi)

    return plotter.render(side_panel=True, colorbar_label=colorbar_label,
                          title=title, mode=mode, stats=stats,
                          tick_text=tick_text, cell_px=cell_px,
                          output_html=output_html)
