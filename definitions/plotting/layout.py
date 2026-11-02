"""
Panel grid
==========
VeryWiseLayout turns a `hemis` + `views` spec into a (rows, cols, panels) grid
and builds the plotly subplot figure for it.

Two modes:
  'static'      -- the downloadable figure: six views, 4 columns when bilateral,
                   with the colorbar and density as extra columns of the same
                   figure.
  'interactive' -- what the app shows: hemispheres side by side, one row per
                   view, and *no* colorbar columns. The side panel is a
                   separate figure there (see panels.side_panel_figure), so the
                   brain card can be expanded on its own.
"""

import math

from plotly.subplots import make_subplots

from .cameras import WHOLE_BRAIN_VIEWS


class VeryWiseLayout:
    """
    Attributes
    ----------
    n_rows, n_cols : int
        Size of the brain grid (excluding any colorbar columns).
    panels : list of (row, col, hemi, view, title_or_None)
    """

    DEFAULT_LAYOUT = {
        'static': {
            'views': ['lateral', 'dorsal', 'anterior',    # L lateral | R lateral | dorsal  | anterior
                      'medial', 'ventral', 'posterior'],  # L medial  | R medial  | ventral | posterior
            'panel_size': (400, 440),  # brain panel width, height in px
            'panel_width': 0.40,
            'panel_layout': [('spacer', 0.39), ('colorbar', 0.17),
                             ('spacer', 0.03), ('panel', 0.41)],
        },
        'interactive': {
            'views': ['lateral'],
            'panel_size': (420, 380),
            'panel_width': 0.20,
            'panel_layout': [('colorbar', 0.40), ('panel', 0.60)],
        },
    }

    def __init__(self, hemis, views='all', n_cols=None, mode='static'):
        self.mode = mode
        self.config = self.DEFAULT_LAYOUT[mode]

        if views == 'all':
            views = self.config['views']
        elif isinstance(views, str):
            views = [views]

        if not views:
            raise ValueError('No views were requested.')

        self.views = list(views)

        if mode == 'static':
            self._build_static_panels(hemis, self.views, n_cols)
        else:
            self._build_interactive_panels(hemis, self.views)

    def _build_static_panels(self, hemis, views, n_cols):
        bilateral = hemis == 'both'

        # Expand each view into one or two (hemi, view) pairs
        expanded = []
        for v in views:
            if bilateral and v not in WHOLE_BRAIN_VIEWS:
                expanded.extend([('left', v), ('right', v)])
            else:
                expanded.append((hemis, v))

        # 4 columns for bilateral, 3 for a single hemisphere
        self.n_cols = (min(4 if bilateral else 3, len(expanded))
                       if n_cols is None else n_cols)
        self.n_rows = math.ceil(len(expanded) / self.n_cols)

        # Title logic:
        #   left/right -> 'Left'/'Right' as a column header, on first appearance
        #   both       -> the view name (each panel is a distinct view)
        col_hemi_seen = set()
        self.panels = []

        for i, (hemi, view) in enumerate(expanded):
            row, col = divmod(i, self.n_cols)

            if hemi in ('left', 'right'):
                key = f'{col}_{hemi}'
                title = hemi.capitalize() if key not in col_hemi_seen else None
                col_hemi_seen.add(key)
            else:
                title = view.capitalize()

            self.panels.append((row, col, hemi, view, title))

    def _build_interactive_panels(self, hemis, views):
        """Hemispheres across the columns, one row per view."""
        hemi_order = ['left', 'right'] if hemis == 'both' else [hemis]

        self.n_rows, self.n_cols = len(views), len(hemi_order)

        self.panels = [
            (r, c, hemi, view,
             # Name the hemisphere on the top row, and the view when there are several
             f'{hemi.capitalize()} hemisphere' if r == 0 else
             (view.capitalize() if c == 0 and len(views) > 1 else None))
            for r, view in enumerate(views)
            for c, hemi in enumerate(hemi_order)
        ]

    def hemis_used(self):
        return {h for _, _, h, _, _ in self.panels}

    # --- Figure --------------------------------------------------------------

    def _panel_columns(self, panel_width=None):
        """(col_widths, specs, colorbar_col, panel_col) for the side columns."""
        panel_width = panel_width or self.config['panel_width']
        tags = self.config['panel_layout']

        col_widths = [panel_width * frac for _, frac in tags]

        cb_col = self.n_cols + next(i for i, (t, _) in enumerate(tags)
                                    if t == 'colorbar') + 1
        panel_col = self.n_cols + next(i for i, (t, _) in enumerate(tags)
                                       if t == 'panel') + 1

        # The side columns span every row, so only the first row holds a spec
        specs = [[{'type': 'xy', 'rowspan': self.n_rows}] * len(tags)]
        specs += [[None] * len(tags) for _ in range(1, self.n_rows)]

        return col_widths, specs, cb_col, panel_col

    def build_figure(self, side_panel=True, panel_width=None,
                     horizontal_spacing=0.0, vertical_spacing=0.04):
        """
        Build the subplot figure.

        `side_panel=False` builds the brain grid alone, which is what the app
        uses -- the colorbar then lives in its own figure.
        """
        if side_panel:
            cb_widths, side_specs, cb_col, panel_col = self._panel_columns(panel_width)
        else:
            cb_widths, side_specs, cb_col, panel_col = [], None, None, None

        col_widths = [1.0] * self.n_cols + cb_widths
        total_cols = len(col_widths)

        specs = [[{'type': 'scene'}] * self.n_cols + (side_specs[r] if side_specs else [])
                 for r in range(self.n_rows)]

        subplot_titles = [''] * (self.n_rows * total_cols)
        for row, col, _, _, title in self.panels:
            if title:
                subplot_titles[row * total_cols + col] = title

        fig = make_subplots(
            rows=self.n_rows, cols=total_cols, specs=specs,
            column_widths=col_widths, subplot_titles=subplot_titles,
            horizontal_spacing=horizontal_spacing,
            vertical_spacing=vertical_spacing)

        return fig, cb_col, panel_col

    def figure_size(self, side_panel=True, panel_width=None, cell_px=None,
                    roi_names=None, legend_extra_px=None):
        """
        Resolve (width, height, right margin) for this layout.

        cell_px : (width, height), a single number, or None
            Overrides the mode's default panel size. A single number keeps the
            default aspect ratio.
        """
        default_w, default_h = self.config['panel_size']

        if cell_px is None:
            w_unit, h_unit = default_w, default_h
        elif isinstance(cell_px, (tuple, list)):
            w_unit, h_unit = cell_px
        else:
            w_unit = cell_px
            h_unit = cell_px * (default_h / default_w)

        width = w_unit * self.n_cols
        height = h_unit * self.n_rows

        if side_panel:
            width += w_unit * (panel_width or self.config['panel_width'])

        if legend_extra_px is None:
            legend_extra_px = (80 + max(len(n) for n in roi_names) * 7) if roi_names else 0

        width += legend_extra_px

        return width, height, max(legend_extra_px, 10)

    @staticmethod
    def scene_key(row, col, n_cols):
        """Plotly's scene name for a grid position ('scene', 'scene2', ...)."""
        idx = row * n_cols + col
        return 'scene' if idx == 0 else f'scene{idx + 1}'

    def __repr__(self):
        return (f'VeryWiseLayout(mode={self.mode}, {self.n_rows}x{self.n_cols}, '
                f'views={self.views}, n_panels={len(self.panels)})')
