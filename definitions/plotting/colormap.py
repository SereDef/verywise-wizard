"""
Colour scale, limits and ticks
==============================
VeryWiseColormap resolves a colormap + colour limits + colorbar ticks + the
"band mask" (the stretch of the scale where nothing is significant, which gets
blanked out) from vertex-wise hemisphere data.

This module is pure scale logic -- the plotly traces that draw the colorbar,
the density and the cluster means all live in `panels.py`.
"""

import matplotlib
import matplotlib.colors as mcolors
import numpy as np
from matplotlib.ticker import MaxNLocator


def to_array(x):
    """Coerce an array-like into a flat float32 array with proper NaNs."""
    if x is None:
        return None
    arr = np.asarray(x, dtype=np.float32).ravel()
    arr[~np.isfinite(arr)] = np.nan
    return arr


def threshold(arr, mask):
    """Blank out everything outside `mask` (None = keep everything)."""
    if mask is None or arr is None:
        return arr
    return np.where(np.asarray(mask, dtype=bool), arr, np.nan)


class VeryWiseColormap:
    """
    Parameters
    ----------
    lh, rh : np.ndarray or None
        Hemisphere value arrays. NaNs are ignored.
    lh_mask, rh_mask : np.ndarray or None
        Boolean significance masks, same shape as lh/rh. None = all significant.
    cmap : str, list, Colormap, or None
        None picks a default from the sign of the significant values.
    vmin, vmax : float or None
        User-specified panel axis edges. When None the axis spans all observed
        values, while the colormap itself is normalised to the significant ones.
    discrete : bool or None
        None auto-detects (integer-valued with few unique levels). Pass True to
        force the discrete path -- cluster maps may well have more than
        `max_discrete` clusters but must still be coloured categorically.
    max_discrete : int
        Auto-detection cut-off, ignored when `discrete` is given.
    n_y : int
        Vertical resolution of the colorbar / density grid.

    Attributes
    ----------
    cmap : Colormap
    vmin, vmax : float
        Panel axis extent (y_grid, ticks, colorbar/density range).
    sig_min, sig_max : float
        Range of the significant values.
    eff_min, eff_max : float
        Colormap normalisation edges.
    norm : matplotlib.colors.Normalize or BoundaryNorm
    is_discrete, is_empty : bool
    tick_vals, tick_text : list
    y_grid : np.ndarray
    band_mask : np.ndarray of bool
        True where the scale should be blanked (nothing significant there).
    all_finite : np.ndarray
        Every finite observed value, for the density estimate.
    """

    def __init__(self, lh, rh=None, lh_mask=None, rh_mask=None, cmap=None,
                 vmin=None, vmax=None, discrete=None, max_discrete=20, n_y=1000):

        all_vals, sig_vals = self._masked_concat(lh, rh, lh_mask, rh_mask)

        # +/- Inf have already been turned into NaN by to_array()
        self.data_min = float(np.nanmin(all_vals))
        self.data_max = float(np.nanmax(all_vals))

        self.vmin = self.data_min if vmin is None else vmin
        self.vmax = self.data_max if vmax is None else vmax

        self.all_finite = all_vals[np.isfinite(all_vals)]
        self.is_empty = bool(np.all(np.isnan(sig_vals)))

        if self.is_empty:
            self.cmap = self._nan_transparent(matplotlib.colormaps['binary'])
            self.sig_min, self.sig_max = self.vmin, self.vmax
            self.eff_min, self.eff_max = self.vmin, self.vmax
            self.norm = mcolors.Normalize(vmin=self.vmin, vmax=self.vmax)
            self.is_discrete = False
            self.tick_vals, self.tick_text = self._colorbar_ticks(self.vmin, self.vmax)
            self.y_grid = np.linspace(self.vmin, self.vmax, n_y)
            self.band_mask = np.ones_like(self.y_grid, dtype=bool)
            return

        sig_finite = sig_vals[np.isfinite(sig_vals)]
        self.sig_min = float(sig_finite.min())
        self.sig_max = float(sig_finite.max())

        self.is_discrete = (self._detect_discrete(sig_finite, max_discrete)
                            if discrete is None else bool(discrete))

        self.cmap, self.eff_min, self.eff_max, self.norm = self._build_cmap(
            cmap, self.is_discrete, vmin, vmax, self.sig_min, self.sig_max)

        if self.is_discrete:
            # One tick per level, placed at the centre of its colour band
            self.tick_vals = list(range(1, int(self.sig_max) + 1))
            self.tick_text = [str(v) for v in self.tick_vals]
            self.vmin, self.vmax = self.eff_min, self.eff_max
        else:
            self.tick_vals, self.tick_text = self._colorbar_ticks(self.vmin, self.vmax)

        self.y_grid = np.linspace(self.vmin, self.vmax, n_y)

        # A discrete scale has one band per level and no "nothing is significant
        # here" gap to blank out: every level between vmin and vmax is a real
        # category, so the strip is filled edge to edge. Masking it the
        # continuous way would blank the outer half-band of the first and last
        # level, leaving white space at both ends of the colorbar.
        self.band_mask = (np.zeros_like(self.y_grid, dtype=bool) if self.is_discrete
                          else self._resolve_band_mask(sig_finite, self.y_grid))

    # --- Data ----------------------------------------------------------------

    @staticmethod
    def _masked_concat(lh, rh, lh_mask, rh_mask):
        """(all values, values outside the masks blanked) across both hemispheres."""
        pairs = [(a, m) for a, m in ((lh, lh_mask), (rh, rh_mask)) if a is not None]
        if not pairs:
            raise ValueError('No hemisphere data was given.')

        all_vals = np.concatenate([a for a, _ in pairs])
        sig_vals = np.concatenate([threshold(a, m) for a, m in pairs])

        if np.all(np.isnan(all_vals)):
            raise ValueError('Hemisphere data contains no finite values.')

        return all_vals, sig_vals

    @staticmethod
    def _detect_discrete(vals, max_discrete=20):
        if vals.size == 0:
            return False
        if len(np.unique(vals)) > max_discrete:
            return False
        return bool(np.allclose(vals, np.round(vals)))

    # --- Colormap ------------------------------------------------------------

    @classmethod
    def _build_cmap(cls, cmap, is_discrete, vmin, vmax, sig_min, sig_max):
        if is_discrete:
            n_levels = int(sig_max)
            palette = cmap if cmap is not None else ('tab10' if n_levels <= 10 else 'tab20')

            resolved_min = 0.5 if vmin is None else vmin
            resolved_max = n_levels + 0.5 if vmax is None else vmax

            # n_levels colour bands need n_levels + 1 boundaries, centred on the
            # integer levels: [0.5, 1.5, ..., n_levels + 0.5]
            boundaries = np.arange(0.5, n_levels + 1.5)
            norm = mcolors.BoundaryNorm(boundaries, ncolors=n_levels)

            return cls._discrete_cmap(n_levels, palette), resolved_min, resolved_max, norm

        if cmap is not None:
            base = cls._resolve_cmap_obj(cmap)
        elif sig_min >= 0:  # all positive associations
            base = matplotlib.colormaps['hot_r']
        elif sig_max <= 0:  # all negative associations
            base = matplotlib.colormaps['viridis']
        else:
            base = cls._diverging_cmap()

        resolved_min = sig_min if vmin is None else vmin
        resolved_max = sig_max if vmax is None else vmax

        norm = mcolors.Normalize(vmin=resolved_min, vmax=resolved_max)

        return cls._nan_transparent(base), resolved_min, resolved_max, norm

    @staticmethod
    def _resolve_cmap_obj(cmap):
        if isinstance(cmap, list):
            return mcolors.ListedColormap(cmap)
        if isinstance(cmap, mcolors.Colormap):
            return cmap
        return matplotlib.colormaps[cmap]

    @staticmethod
    def _nan_transparent(cmap_obj):
        c = cmap_obj.copy()
        c.set_bad(alpha=0.0)
        return c

    # A ListedColormap with more entries than this is a continuous palette
    # (turbo and viridis both ship 256 colours) rather than a qualitative one,
    # so its colours must be sampled across the range, not taken from the start.
    MAX_QUALITATIVE = 32

    @classmethod
    def _discrete_cmap(cls, n_levels, palette):
        palette_obj = cls._resolve_cmap_obj(palette)
        listed = getattr(palette_obj, 'colors', None)

        if listed is not None and len(listed) <= cls.MAX_QUALITATIVE:
            # Qualitative palette: take its colours in order, cycling if needed
            colors = [listed[i % len(listed)] for i in range(n_levels)]
        else:
            # Spread the levels evenly over the whole palette
            colors = [palette_obj(i / max(n_levels - 1, 1)) for i in range(n_levels)]

        if len(colors) == 1:
            # A single-colour colormap is what one level means, but matplotlib
            # cannot build a lookup table from one entry (and nilearn rebuilds
            # every colormap that way), so repeat it to get a constant one.
            colors = colors * 2

        return cls._nan_transparent(mcolors.ListedColormap(colors, name='discrete'))

    @staticmethod
    def _diverging_cmap():
        """viridis (negative) -> hot_r (positive), joined in the middle."""
        hot_r = matplotlib.colormaps['hot_r']
        viridis = matplotlib.colormaps['viridis']

        colors = [viridis(0.0), viridis(0.5), viridis(1.0),
                  hot_r(0.5), hot_r(0.75), hot_r(1.0)]
        nodes = [0.0, 0.25, 0.5, 0.6, 0.75, 1.0]

        return mcolors.LinearSegmentedColormap.from_list(
            'hot_r_viridis', list(zip(nodes, colors)))

    def colorscale(self, n=256):
        """The colormap as a plotly colorscale."""
        return [[i / (n - 1), f'rgba({int(r * 255)},{int(g * 255)},{int(b * 255)},{a:.3f})']
                for i, (r, g, b, a) in enumerate(self.cmap(np.linspace(0, 1, n)))]

    def color_at(self, level):
        """Hex colour for one discrete level (1-based), for the cluster panel."""
        if not self.is_discrete:
            return mcolors.to_hex(self.cmap(0.5))
        # BoundaryNorm maps level -> band index, which indexes the listed colours
        return mcolors.to_hex(self.cmap(int(self.norm(level))))

    # --- Ticks ---------------------------------------------------------------

    @classmethod
    def _colorbar_ticks(cls, vmin, vmax, n_ticks=10):
        data_range = vmax - vmin
        if data_range == 0:
            return [vmin], [cls._fmt_tick(vmin)]

        is_integer = (float(vmin).is_integer() and float(vmax).is_integer()
                      and data_range <= 2 * n_ticks)

        locator = MaxNLocator(nbins=n_ticks - 1, integer=is_integer,
                             steps=[1, 2, 2.5, 5, 10])
        vals = locator.tick_values(vmin, vmax)

        tol = data_range * 1e-9
        vals = vals[(vals >= vmin - tol) & (vals <= vmax + tol)]
        vals = np.where(np.abs(vals) < tol, 0.0, vals)

        # Always label the extremes, and zero for diverging scales
        for v in [vmin, vmax] + ([0.0] if vmin < 0 < vmax else []):
            if not np.any(np.abs(vals - v) < tol):
                vals = np.sort(np.append(vals, v))

        return vals.tolist(), [cls._fmt_tick(v, vmin, vmax) for v in vals]

    @staticmethod
    def _fmt_tick(v, vmin=None, vmax=None):
        if v == 0.0:
            return '0'

        magnitude = abs(v)
        if magnitude >= 1e4 or magnitude < 1e-3:
            return f'{v:.2e}'
        if float(v).is_integer():
            return str(int(v))

        data_range = abs(vmax - vmin) if (vmin is not None and vmax is not None) else magnitude
        if data_range != 0:
            decimals = min(max(0, -int(np.floor(np.log10(data_range))) + 2), 4)
            return f'{v:.{decimals}f}'.rstrip('0').rstrip('.')

        return f'{v:.3g}'

    # --- Band mask -----------------------------------------------------------

    def _resolve_band_mask(self, sig_vals, y_grid):
        """True where `y_grid` holds no significant values, so it can be blanked."""
        if sig_vals.size == 0:
            return np.ones_like(y_grid, dtype=bool)

        pos_sig = sig_vals[sig_vals > 0]
        neg_sig = sig_vals[sig_vals < 0]

        # The gap between the largest negative and smallest positive finding
        lo = neg_sig.max() if neg_sig.size else self.vmin
        hi = pos_sig.min() if pos_sig.size else self.vmax

        gap = (y_grid >= lo) & (y_grid <= hi)
        outside = (y_grid < self.sig_min) | (y_grid > self.sig_max)

        return gap | outside

    def __repr__(self):
        if self.is_empty:
            return 'VeryWiseColormap(empty=True, nothing significant)'
        mode = 'discrete' if self.is_discrete else 'continuous'
        return (f'VeryWiseColormap(mode={mode}, '
                f'axis=[{self.vmin:.3g}, {self.vmax:.3g}], '
                f'cmap=[{self.eff_min:.3g}, {self.eff_max:.3g}], '
                f'n_ticks={len(self.tick_vals)})')
