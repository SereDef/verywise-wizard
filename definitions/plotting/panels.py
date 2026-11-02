"""
Side panels: colorbar, density and cluster means
================================================
The panel that sits next to the brains. It always starts with a colorbar strip,
followed by either

  'density'  -- a kernel density of every observed value, coloured in where the
                values are significant (the default, for beta maps), or
  'clusters' -- mean beta per cluster with its min-max range, sharing the
                colorbar's y-axis so each row lines up with its colour.

`side_panel_figure()` returns the panel as a figure of its own, which is what
the app shows beside the brain card. `add_side_panel()` instead draws it into
an existing multi-panel figure, which is what the static PNG does.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DENSITY = 'density'
CLUSTERS = 'clusters'

# gaussian_kde costs O(n_values x n_eval_points), and n_values here is every
# vertex of both hemispheres (~290k at full resolution), so sampling it
# directly over the colour grid takes seconds on every redraw. Binning the
# values and passing the counts as weights keeps every value in the estimate --
# nothing is discarded -- while collapsing n_values to the number of bins.
# Evaluating on a coarse grid and interpolating does the rest. The result
# matches the direct estimate to within 0.1% of peak height.
KDE_BINS = 1000
KDE_GRID_POINTS = 256


def _blank_nan(z):
    """
    Hand plotly `None` rather than NaN for the cells that should stay empty.

    Both read as "no data" and look identical, but the figure also has to
    survive being serialised to JSON for the browser, and that is done with
    `allow_nan=False` -- a NaN anywhere in `z` raises
    "Out of range float values are not JSON compliant".
    """
    blanked = z.astype(object)
    blanked[np.isnan(z)] = None
    return blanked.tolist()


# ===== TRACES =================================================================

def colorbar_trace(colormap):
    """A vertical strip of the colormap, blanked where nothing is significant."""
    z = np.tile(colormap.y_grid.reshape(-1, 1), (1, 2)).astype(float)
    if colormap.band_mask.any():
        z[colormap.band_mask, :] = np.nan

    return go.Heatmap(
        x=[0, 1], y=colormap.y_grid, z=_blank_nan(z),
        zmin=colormap.eff_min, zmax=colormap.eff_max,
        colorscale=colormap.colorscale(),
        showscale=False, hoverinfo='skip', xgap=0, ygap=0)


def _weighted_kde(vals):
    """
    A gaussian_kde over `vals`, built from binned counts rather than the raw
    values. Every value still contributes, through its bin's weight; the
    bandwidth is pinned to the one the full sample would have produced
    (Scott's rule, n**(-1/5)), so the estimate is unchanged.
    """
    from scipy.stats import gaussian_kde

    if vals.size <= KDE_BINS:
        return gaussian_kde(vals)  # already small enough to use directly

    counts, edges = np.histogram(vals, bins=KDE_BINS)
    centres = (edges[:-1] + edges[1:]) / 2.0
    filled = counts > 0

    return gaussian_kde(centres[filled],
                        weights=counts[filled].astype(float),
                        bw_method=float(vals.size) ** (-1.0 / 5.0))


def density_traces(colormap, n_x=80):
    """(filled density, outline) of every observed value."""
    y_grid = colormap.y_grid
    vals = colormap.all_finite

    kde = None
    if not colormap.is_discrete and vals.size > 1 and np.ptp(vals) > 0:
        try:
            kde = _weighted_kde(vals)
            # Sample coarsely and interpolate: the curve is smooth, so the
            # fine grid gains nothing but costs a lot
            coarse = np.linspace(y_grid[0], y_grid[-1],
                                 min(KDE_GRID_POINTS, y_grid.size))
            density = np.interp(y_grid, coarse, kde(coarse))
        except np.linalg.LinAlgError:
            density = np.zeros_like(y_grid)
    else:
        density = np.zeros_like(y_grid)

    dmax = density.max() if density.max() > 0 else 1.0
    density = density / dmax

    # Do not draw outside the observed range
    outside = (y_grid < colormap.data_min) | (y_grid > colormap.data_max)

    fill = density.copy()
    fill[outside] = 0.0

    line = density.copy()
    line[outside] = np.nan

    y_line = y_grid
    if kde is not None:
        # Close the outline exactly on the observed extremes
        edges = kde([colormap.data_min, colormap.data_max]) / dmax
        y_line = np.concatenate([[colormap.data_min], y_grid, [colormap.data_max]])
        line = np.concatenate([[edges[0]], line, [edges[1]]])
        order = np.argsort(y_line)
        y_line, line = y_line[order], line[order]

    # Colour the filled area by value, clipped to the density outline
    x_grid = np.linspace(0, 1, n_x)
    z = np.tile(y_grid.reshape(-1, 1), (1, n_x)).astype(float)
    z[x_grid.reshape(1, -1) > fill.reshape(-1, 1)] = np.nan
    if colormap.band_mask.any():
        z[colormap.band_mask, :] = np.nan

    fill_trace = go.Heatmap(
        x=x_grid, y=y_grid, z=_blank_nan(z),
        zmin=colormap.eff_min, zmax=colormap.eff_max,
        colorscale=colormap.colorscale(),
        showscale=False, hoverinfo='skip', xgap=0, ygap=0)

    outline_trace = go.Scatter(
        x=_blank_nan(line), y=y_line, mode='lines',
        line=dict(color='black', width=1.5),
        hoverinfo='skip', showlegend=False)

    return fill_trace, outline_trace


def zero_line_trace(colormap, x_range=(0, 1)):
    """
    A dashed horizontal line at zero, for panels whose y-axis is the value
    scale (the density). Only drawn when the scale actually crosses zero.
    """
    if not (colormap.vmin < 0 < colormap.vmax):
        return None

    return go.Scatter(
        x=list(x_range), y=[0, 0], mode='lines',
        line=dict(color='grey', width=0.75, dash='dash'),
        hoverinfo='skip', showlegend=False)


def vertical_zero_line_trace(y_range):
    """
    A dashed vertical line at zero, for the cluster panel, whose x-axis is the
    beta scale. Always drawn: it is the null reference the means are read
    against, so the x-range is widened to keep it in view.
    """
    return go.Scatter(
        x=[0, 0], y=list(y_range), mode='lines',
        line=dict(color='grey', width=0.75, dash='dash'),
        hoverinfo='skip', showlegend=False)


def cluster_means_traces(colormap, stats):
    """
    Mean beta per cluster, with its min-max range, one marker per cluster.

    `stats` is the DataFrame from backend_results.cluster_stats(). Returns
    (traces, tick_vals, tick_text) so the shared y-axis can be labelled with
    the cluster number and size.
    """
    traces = []

    for row in stats.itertuples():
        color = colormap.color_at(row.cluster)

        traces.append(go.Scatter(
            x=[row.mean], y=[row.cluster],
            error_x=dict(type='data', symmetric=False,
                         array=[row.max - row.mean],
                         arrayminus=[row.mean - row.min],
                         color=color, thickness=1.5, width=5),
            mode='markers',
            marker=dict(color=color, size=9, symbol='diamond'),
            customdata=[[row.hemi, row.size, row.min, row.max]],
            hovertemplate=(f'<b>Cluster {int(row.cluster)}</b><br>'
                           '%{customdata[0]} hemisphere<br>'
                           'size: %{customdata[1]} vertices<br>'
                           'mean: %{x:.4g}<br>'
                           'range: [%{customdata[2]:.4g}, %{customdata[3]:.4g}]'
                           '<extra></extra>'),
            hoverlabel=dict(bgcolor=color, font=dict(color='white')),
            showlegend=False))

    tick_vals = stats['cluster'].tolist()
    # Name the hemisphere here too: the static PNG has no hover to fall back on
    tick_text = [f'{h[0].upper()}{int(c)}&nbsp;<i>(n={int(n)})</i>'
                 for c, n, h in zip(stats['cluster'], stats['size'], stats['hemi'])]

    return traces, tick_vals, tick_text


# ===== COMPOSITION ============================================================

def add_side_panel(fig, colormap, cb_col, panel_col, label=None, row=1,
                   mode=DENSITY, stats=None):
    """Draw the colorbar and its companion panel into `fig`."""
    fig.add_trace(colorbar_trace(colormap), row=row, col=cb_col)

    tick_vals, tick_text = colormap.tick_vals, colormap.tick_text
    panel_x_range = [0, 1.05]
    panel_visible = False

    # Beta scales read low-to-high upward; cluster lists read 1-to-n downward
    y_range = [colormap.vmin, colormap.vmax]

    if mode == CLUSTERS and stats is not None and len(stats):
        y_range = [colormap.vmax, colormap.vmin]
        traces, tick_vals, tick_text = cluster_means_traces(colormap, stats)

        # Give the error bars room on both sides, and always keep zero in view
        # so the reference line is visible even when every mean is one-sided.
        lo = min(float(stats['min'].min()), 0.0)
        hi = max(float(stats['max'].max()), 0.0)
        pad = (hi - lo) * 0.12 or 1.0
        panel_x_range = [lo - pad, hi + pad]
        panel_visible = True

        # Drawn first, so the markers sit on top of it
        fig.add_trace(vertical_zero_line_trace(y_range), row=row, col=panel_col)
        for tr in traces:
            fig.add_trace(tr, row=row, col=panel_col)

    elif mode == DENSITY:
        fill, outline = density_traces(colormap)
        fig.add_trace(fill, row=row, col=panel_col)
        fig.add_trace(outline, row=row, col=panel_col)

        zero = zero_line_trace(colormap, x_range=panel_x_range)
        if zero is not None:
            fig.add_trace(zero, row=row, col=panel_col)

    # --- colorbar axes ---
    fig.update_xaxes(range=[0, 1], visible=True, showgrid=False,
                     showticklabels=False, ticks='', showline=True,
                     linecolor='black', mirror=True, fixedrange=True,
                     row=row, col=cb_col)

    fig.update_yaxes(range=y_range, side='left',
                     showgrid=False, zeroline=False,
                     tickmode='array', tickvals=tick_vals, ticktext=tick_text,
                     title=dict(text=label or '', standoff=2),
                     ticks='outside', showline=True, linecolor='black',
                     mirror=True, automargin=True, row=row, col=cb_col)

    # --- companion panel axes ---
    fig.update_xaxes(range=panel_x_range, visible=panel_visible, showgrid=False,
                     zeroline=False, ticks='outside', showline=panel_visible,
                     linecolor='black', row=row, col=panel_col)

    fig.update_yaxes(range=y_range, visible=False,
                     showgrid=False, row=row, col=panel_col)

    return fig


def side_panel_figure(colormap, label=None, mode=DENSITY, stats=None,
                      width=260, height=420, x_title=None):
    """
    The side panel as a standalone figure, for the app to show next to the
    brain card (so that expanding the brains does not drag the legend along).
    """
    fig = make_subplots(rows=1, cols=2, column_widths=[0.28, 0.72],
                        shared_yaxes=True, horizontal_spacing=0.04)

    add_side_panel(fig, colormap, cb_col=1, panel_col=2, label=label, mode=mode,
                   stats=stats)

    if x_title is None and mode == CLUSTERS:
        x_title = 'Mean β per cluster'

    if x_title:
        fig.update_xaxes(title=dict(text=x_title, standoff=4), row=1, col=2)

    fig.update_layout(
        width=width, height=height,
        paper_bgcolor='white', plot_bgcolor='white',
        margin=dict(l=10, r=10, t=20, b=40),
        showlegend=False)

    return fig
