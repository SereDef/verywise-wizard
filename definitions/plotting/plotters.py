"""
Surface renderers
=================
VeryWiseSurfacePlotter       : shared scaffolding (scene box, cameras, ROI overlays)
VeryWiseStaticPlotter        : multi-view figure for PNG export (Kaleido)
VeryWiseInteractivePlotter   : the figure the app shows, with per-vertex hover

Both renderers build one trace set per *hemisphere* and reuse it across camera
angles: the hover text depends on the vertex, not on the direction you look at
it from, so nothing has to be rebuilt per view.
"""

import os
import warnings

import numpy as np
from nilearn.plotting import plot_surf

from .cameras import VeryWiseCameraPresets
from .panels import DENSITY, add_side_panel


class VeryWiseSurfacePlotter:
    """Shared scaffolding for the static and interactive renderers."""

    # The view used only to build the traces -- the real camera is set
    # afterwards from the presets. nilearn refuses hemi='both' with a
    # lateral/medial view, so whole-brain panels are built dorsally.
    CANONICAL_VIEW = {'left': 'lateral', 'right': 'lateral', 'both': 'dorsal'}

    # A hemisphere with nothing significant on it is just the background, and
    # that looks the same for every empty result. Building it costs a full
    # plot_surf (~0.5 s per hemisphere), so it is shared between plotters and
    # between results instead. Keyed by what the picture actually depends on.
    _EMPTY_TRACES = {}
    _EMPTY_TRACES_MAX = 16

    def __init__(self, mesh, colormap, layout, camera_presets=None, roi_names=None,
                 hover_roi=True):
        self.mesh = mesh
        self.colormap = colormap
        self.layout = layout
        self.surface = mesh.surface
        self.camera_presets = camera_presets
        self.roi_names = roi_names
        self.hover_roi = hover_roi

        self.mid, self.half = mesh.scene_bbox()

    # --- Scene ---------------------------------------------------------------

    def axis(self, i):
        """Axis range for dimension `i`, identical across every panel."""
        return dict(visible=False, showgrid=False, zeroline=False, showspikes=False,
                    range=[float(self.mid[i] - self.half),
                           float(self.mid[i] + self.half)])

    def camera(self, hemi, view):
        return VeryWiseCameraPresets.resolve(
            hemi, view, surface=self.surface, custom_presets=self.camera_presets)

    def scene(self, hemi, view, bgcolor='white'):
        return dict(aspectmode='cube', bgcolor=bgcolor,
                    xaxis=self.axis(0), yaxis=self.axis(1), zaxis=self.axis(2),
                    camera=self.camera(hemi, view))

    @staticmethod
    def _to_plotly(fp):
        """Unwrap nilearn's PlotlySurfaceFigure -> a plain plotly Figure."""
        return fp.figure if hasattr(fp, 'figure') else fp

    def _plot_hemi(self, hemi):
        """Run plot_surf for one hemisphere and return the nilearn figure."""
        with warnings.catch_warnings():
            # A map with no significant vertices is all-NaN by design
            warnings.filterwarnings('ignore', message='All-NaN slice encountered')

            return plot_surf(
                surf_mesh=None, surf_map=self.mesh.surf_img, hemi=hemi,
                view=self.CANONICAL_VIEW[hemi],
                cmap=self.colormap.cmap,
                vmin=self.colormap.eff_min, vmax=self.colormap.eff_max,
                threshold=None, symmetric_cmap=None, avg_method=None,
                bg_map=self.mesh.bg_img, bg_on_data=False,
                colorbar=False, engine='plotly')

    # --- ROI overlays --------------------------------------------------------

    def _add_roi_contours(self, fp):
        """Overlay ROI boundary contours for the requested region names."""
        if not self.roi_names:
            return

        levels, labels, colors = self.mesh.roi_levels(self.roi_names)
        if not levels:
            return

        fp.add_contours(roi_map=self.mesh.roi_img, levels=levels, labels=labels,
                        lines=[{'width': 5, 'color': c} for c in colors])

    def _add_roi_legend(self, fig):
        """Show each ROI name once in the legend, whatever panel it came from."""
        seen = set()
        for tr in fig.data:
            name = getattr(tr, 'name', None)
            if name is None:
                continue
            tr.update(showlegend=name not in seen, legendgroup=name)
            seen.add(name)

    # --- Side panel ----------------------------------------------------------

    def _add_side_panel(self, fig, cb_col, panel_col, label, mode, stats,
                        tick_text=None):
        add_side_panel(fig, self.colormap, cb_col=cb_col, panel_col=panel_col,
                       label=label, mode=mode, stats=stats, tick_text=tick_text)

    # --- Traces --------------------------------------------------------------

    def _hover_text(self, hemi):
        """Per-vertex hover strings for one hemisphere (None = no hover)."""
        data = self.mesh.data(hemi)

        roi_map, level_to_name = None, {}
        if self.hover_roi:
            # Reverse the lookup once per hemisphere, not once per vertex
            roi_map, roi_labels = self.mesh.roi[hemi]
            level_to_name = {level: name for name, (level, _c) in roi_labels.items()}

        # Only the significant vertices get a label; the rest stay blank, so
        # only those are worth building a string for.
        text = [''] * len(data)
        for i in np.flatnonzero(np.isfinite(data)):
            line = f'Vertex index: {i + 1}<br>Value: <b>{data[i]:.4g}</b>'
            if roi_map is not None:
                region = level_to_name.get(int(roi_map[i]), 'unknown')
                line += f'<br>Region: <b>{region}</b>'
            text[i] = line

        return text

    def _hemi_traces(self, hemi, with_hover=False):
        """Build the plotly traces for one hemisphere."""
        fp = self._plot_hemi(hemi)
        self._add_roi_contours(fp)
        raw = self._to_plotly(fp)

        text = self._hover_text(hemi) if with_hover else None

        for tr in raw.data:
            if text is not None and tr.type == 'mesh3d':
                tr.update(text=text, hovertemplate='%{text}<extra></extra>',
                          hoverlabel=dict(bgcolor='silver', font=dict(color='black')),
                          showlegend=False)
            else:
                tr.update(hoverinfo='skip')  # ROI contour lines, or nothing to show
            if 'showscale' in tr:
                tr.update(showscale=False)

        return list(raw.data)

    def _build_trace_cache(self, with_hover=False):
        """
        One trace set per hemisphere, reused across every camera angle: the
        hover text depends on the vertex, not on the direction you view it from.
        """
        if self.colormap.is_empty:
            # Nothing to draw on top, so reuse the plain background and skip
            # hover entirely -- there is nothing to hover over.
            cache = {}
            for hemi in self.layout.hemis_used():
                key = (self.mesh.fs_template, self.mesh.surface,
                       self.mesh.bg_map_type, tuple(self.roi_names or ()), hemi)

                if key not in self._EMPTY_TRACES:
                    if len(self._EMPTY_TRACES) >= self._EMPTY_TRACES_MAX:
                        self._EMPTY_TRACES.clear()
                    self._EMPTY_TRACES[key] = self._hemi_traces(hemi)

                cache[hemi] = self._EMPTY_TRACES[key]
            return cache

        return {hemi: self._hemi_traces(hemi, with_hover=with_hover)
                for hemi in self.layout.hemis_used()}


class VeryWiseStaticPlotter(VeryWiseSurfacePlotter):
    """Multi-view figure composed for PNG export through Kaleido."""

    def render(self, side_panel=True, colorbar_label=None, title=None,
               mode=DENSITY, stats=None, tick_text=None, cell_px=None,
               panel_width=None, output_file=None, dpi=150):

        fig, cb_col, panel_col = self.layout.build_figure(side_panel, panel_width)

        width, height, margin_r = self.layout.figure_size(
            side_panel=side_panel, panel_width=panel_width, cell_px=cell_px,
            roi_names=None)  # the ROI legend is anchored at the bottom here

        # Nudge the panel titles down onto the panels
        for ann in fig.layout.annotations:
            ann.update(y=ann.y - 0.02, yanchor='bottom')

        trace_cache = self._build_trace_cache()

        for row, col, hemi, view, _ in self.layout.panels:
            for tr in trace_cache[hemi]:
                fig.add_trace(tr, row=row + 1, col=col + 1)

            sk = self.layout.scene_key(row, col, self.layout.n_cols)
            fig.update_layout(**{sk: self.scene(hemi, view)})

        if side_panel:
            self._add_side_panel(fig, cb_col, panel_col, colorbar_label, mode,
                                 stats, tick_text)

        self._add_roi_legend(fig)

        fig.update_layout(
            title=dict(text=title or '', font=dict(size=25, weight='bold')),
            paper_bgcolor='white', plot_bgcolor='white',
            width=width, height=height,
            margin=dict(l=10, r=margin_r, t=max(60 if title else 30, 45), b=10),
            legend=dict(orientation='h', yanchor='top', y=-0.05, xanchor='left',
                        x=0.02, title=None, font=dict(size=18)))

        if output_file:
            from .kaleido_patch import patch_kaleido
            patch_kaleido()

            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            fig.write_image(output_file, scale=dpi / 72.0)
            return output_file

        return fig


class VeryWiseInteractivePlotter(VeryWiseSurfacePlotter):
    """The figure the app shows, with per-vertex hover text."""

    def render(self, side_panel=False, colorbar_label=None, title=None,
               mode=DENSITY, stats=None, tick_text=None, cell_px=None,
               panel_width=None,
               output_html=None):

        fig, cb_col, panel_col = self.layout.build_figure(
            side_panel, panel_width, horizontal_spacing=0.02)

        width, height, margin_r = self.layout.figure_size(
            side_panel=side_panel, panel_width=panel_width, cell_px=cell_px,
            roi_names=self.roi_names if self.roi_names else None)

        trace_cache = self._build_trace_cache(with_hover=True)

        for row, col, hemi, view, _ in self.layout.panels:
            for tr in trace_cache[hemi]:
                fig.add_trace(tr, row=row + 1, col=col + 1)

            sk = self.layout.scene_key(row, col, self.layout.n_cols)
            fig.update_layout(**{sk: self.scene(hemi, view, bgcolor='rgba(0,0,0,0)')})

        if side_panel:
            self._add_side_panel(fig, cb_col, panel_col, colorbar_label, mode,
                                 stats, tick_text)

        self._add_roi_legend(fig)

        fig.update_layout(
            title=dict(text=title or '', font=dict(size=14)),
            paper_bgcolor='white', plot_bgcolor='white', hovermode='closest',
            width=width, height=height,
            margin=dict(l=5, r=margin_r, t=30 if title else 20, b=5),
            legend=dict(orientation='v', yanchor='top', y=1, xanchor='left',
                        x=1.02, title=None, font=dict(size=12), tracegroupgap=4))

        if output_html:
            os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
            fig.write_html(output_html, include_plotlyjs='cdn', full_html=True,
                           auto_open=False)
            return output_html

        return fig
