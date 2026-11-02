"""
The COMPARE tab.

Two maps are chosen here, independently of the results page, and compared
either as a difference or as a cluster overlap.
"""
import numpy as np
from shiny import Inputs, Outputs, Session, module, reactive, render, req, ui

import definitions.layout_styles as styles
from definitions import plotting as vwp
from definitions.backend_results import (
    compute_difference, compute_overlap, extract_results,
)
from definitions.pages.common import (
    button_column, figure_outputs, figures_row, info_row, nav_title,
    roi_choice, selection_pane, set_if_changed,
)
from definitions.pages.download import (
    DOWNLOAD_TRIGGER_JS, download_buttons, wire_download,
)
from definitions.pages.selectors import map_selector_server, map_selector_ui


def compare_page(tab_name):
    return ui.nav_panel(
        nav_title('scale-unbalanced', 'Compare maps'),
        DOWNLOAD_TRIGGER_JS,
        compare_ui('compare'),
        ' ',  # spacer
        value=tab_name)


def map_band(letter, selector_id):
    """
    One map's three dropdowns on a band of their own, with the letter that
    names it on the left -- so the dropdowns themselves can keep the same
    labels as on the results page.
    """
    return ui.div(
        ui.div(letter, style=styles.MAP_BADGE),
        # min-width: 0 so the dropdowns take what is left of the band and
        # shrink with it, instead of pushing the letter out
        ui.div(ui.layout_columns(*map_selector_ui(selector_id),
                                 col_widths=(4, 4, 4), gap='20px'),
               style='flex: 1; min-width: 0'),
        style=styles.MAP_ROW)


@module.ui
def compare_ui():
    return ui.div(
        # Selection pane: one band per map, each badged with its letter, then
        # the comparison mode and the ROI contours (surface and resolution live
        # in the brains card header)
        ui.layout_columns(
            selection_pane(
                map_band('A', 'map_a'),
                map_band('B', 'map_b'),
                ui.input_selectize(id='compare_mode', label='Comparison',
                                   choices=styles.COMPARE_MODES,
                                   selected='difference', width='100%'),
                roi_choice('select_roi'),
                col_widths=(12, 12, 2, 10),
            ),
            button_column(*download_buttons()),
            col_widths=(11, 1)
        ),
        info_row(),
        figures_row())


@module.server
def update_compare(input: Inputs, output: Outputs, session: Session,
                   all_results) -> None:

    selection_a = map_selector_server('map_a', all_results=all_results)
    selection_b = map_selector_server('map_b', all_results=all_results)

    # Split the same way as the results page: changing the surface must not
    # rebuild the legend, and must not re-read the result files.
    maps_settings = reactive.Value(None)   # (selection A, selection B, mode)
    view_settings = reactive.Value(None)   # (surface, resolution, ROI contours)

    @reactive.Calc
    def selected_roi():
        return tuple(input.select_roi())

    @reactive.Effect
    @reactive.event(input.update_button, ignore_none=True)
    def snapshot_settings():
        set_if_changed(maps_settings, (selection_a(), selection_b(),
                                       input.compare_mode()))
        set_if_changed(view_settings, (input.select_surface(),
                                       input.select_resolution(),
                                       selected_roi()))

    @reactive.Calc
    def both_results():
        (model_a, term_a, meas_a), (model_b, term_b, meas_b), mode = req(maps_settings())

        with ui.Progress(min=0, max=2) as p:
            p.set(0, message='Loading the first map...')
            result_a = extract_results(all_results(), model_a, term_a, meas_a)

            p.set(1, message='Loading the second map...')
            result_b = extract_results(all_results(), model_b, term_b, meas_b)

        return mode, result_a, result_b

    @reactive.Calc
    def compare_args():
        """What to draw, in the same shape display_args() returns."""
        mode, result_a, result_b = both_results()

        if mode == 'difference':
            difference = compute_difference(result_a, result_b)

            # No mask: the difference is shown at every vertex, so the colour
            # scale spans the whole cortex rather than the clusters alone.
            return dict(lh=difference['left'], rh=difference['right'],
                        lh_mask=None, rh_mask=None,
                        cmap=None, discrete=None,
                        label='β difference (A − B)',
                        mode=vwp.DENSITY, tick_text=None)

        info, maps = compute_overlap(result_a, result_b)

        # Codes are 1 = A only, 2 = B only, 3 = both, matching OVLP_COLORS
        return dict(lh=maps['left'].astype(float), rh=maps['right'].astype(float),
                    lh_mask=maps['left'] > 0, rh_mask=maps['right'] > 0,
                    cmap=styles.OVLP_COLORS, discrete=True,
                    label='Cluster overlap',
                    mode=vwp.COLORBAR, tick_text=styles.OVERLAP_TICK_LABELS,
                    overlap_info=info)

    @render.text
    def info():
        mode, result_a, result_b = both_results()
        (model_a, _, meas_a), (model_b, _, meas_b), _ = maps_settings()

        if mode == 'difference':
            difference = compute_difference(result_a, result_b)
            both = np.concatenate([difference[h] for h in ('left', 'right')])

            warning = ''
            if meas_a != meas_b:
                # Subtracting different measures is not meaningful, but the
                # overlap of their clusters still is -- so only warn here.
                warning = (f'</br>⚠️ **A** is <ins>{styles.measure_names[meas_a]}</ins> '
                           f'but **B** is <ins>{styles.measure_names[meas_b]}</ins>: '
                           'their difference is not interpretable.')

            return ui.markdown(
                f'**{model_a}** − **{model_b}**</br>'
                f'Mean difference [range] = **{np.nanmean(both):.2f}** '
                f'[{np.nanmin(both):.2f}; {np.nanmax(both):.2f}]'
                f'{warning}')

        ovlp_info = compare_args()['overlap_info']

        text, legend = {}, {}
        for key in [1, 2, 3]:
            text[key] = (f'**{ovlp_info[key][1]}%** ({ovlp_info[key][0]} vertices)'
                         if key in ovlp_info else '**0%** (0 vertices)')
            color = styles.OVLP_COLORS[key - 1]
            legend[key] = f'<span style = "background-color: {color}; color: {color}"> oo</span>'

        return ui.markdown(
            f'There was a {text[3]} {legend[3]} **overlap** between the maps selected:</br>'
            f'{text[1]} was unique to {legend[1]} **A** — {model_a} (<ins>{meas_a}</ins>)</br>'
            f'{text[2]} was unique to {legend[2]} **B** — {model_b} (<ins>{meas_b}</ins>)')

    @reactive.Calc
    def figure_title():
        """The title the downloaded figure carries: both maps, and the mode."""
        (model_a, _, meas_a), (model_b, _, meas_b), mode = req(maps_settings())

        if mode == 'difference':
            return f'{model_a} ({meas_a}) − {model_b} ({meas_b})'

        return f'Cluster overlap: {model_a} ({meas_a}) vs {model_b} ({meas_b})'

    figure_outputs(compare_args, view_settings)

    wire_download(input, output, session, compare_args, view_settings,
                  figure_title)
