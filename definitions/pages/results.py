"""The MAIN RESULTS tab: one map, drawn as beta values or as clusters."""
from shiny import Inputs, Outputs, Session, module, reactive, render, req, ui

import definitions.layout_styles as styles
from definitions.backend_results import extract_results
from definitions.pages.common import (
    button_column, display_args, figure_outputs, figures_row, info_row,
    nav_title, roi_choice, selection_pane, set_if_changed,
)
from definitions.pages.download import (
    DOWNLOAD_TRIGGER_JS, download_buttons, wire_download,
)
from definitions.pages.selectors import map_selector_server, map_selector_ui


def main_results_page(tab_name):
    return ui.nav_panel(
        nav_title('brain', 'Plot results'),
        ui.markdown('</br>Select the map you want to see, adjust settings and hit'
                 ' **GO** to visualize the 3D brains.<br>Note: it can take up to a few seconds'
                 ' for the brain maps to render, use your patience or our `verywise` plotting functions directly.</br>'),
        DOWNLOAD_TRIGGER_JS,
        single_result_ui('result1'),
        ' ',  # spacer
        value=tab_name)


@module.ui
def single_result_ui():
    return ui.div(
        # Selection pane, with the buttons stacked in the narrow column beside
        # it: GO on top, then one download button per format
        ui.layout_columns(
            selection_pane(
                *map_selector_ui('selector'),
                ui.input_selectize(id='select_output', label='Display',
                                   choices=styles.OUTPUT_NAMES, selected='betas',
                                   width='100%'),
                roi_choice('select_roi'),
                col_widths=(4, 5, 3, 2, 10),
            ),
            button_column(*download_buttons()),
            col_widths=(11, 1)
        ),
        info_row(),
        figures_row())


@module.server
def update_single_result(input: Inputs, output: Outputs, session: Session,
                         all_results) -> None:

    selection = map_selector_server('selector', all_results=all_results)

    # --- Settings ---------------------------------------------------------
    # Snapshotted when GO is pressed, split by what they can actually affect.
    # Changing only the surface, resolution or ROI contours leaves
    # `data_settings` and `display_setting` untouched, so the legend is never
    # rebuilt or re-sent for it -- the one already on screen still fits.

    data_settings = reactive.Value(None)     # model / term / measure
    display_setting = reactive.Value(None)   # beta values or clusters
    brain_settings = reactive.Value(None)    # surface / resolution / ROI contours

    @reactive.Calc
    def selected_roi():
        # A tuple, so it can be compared by value when snapshotting settings
        return tuple(input.select_roi())

    @reactive.Effect
    @reactive.event(input.update_button, ignore_none=True)
    def snapshot_settings():
        set_if_changed(data_settings, selection())
        set_if_changed(display_setting, input.select_output())
        set_if_changed(brain_settings, (input.select_surface(),
                                        input.select_resolution(),
                                        selected_roi()))

    @reactive.Calc
    def figure_title():
        which_model, _which_term, which_meas = req(data_settings())
        return f'{which_model} ({which_meas})'

    # --- Results and figures ---------------------------------------------

    @reactive.Calc
    def result_data():
        which_model, which_term, which_meas = req(data_settings())

        with ui.Progress(min=0, max=1) as p:
            p.set(0, message='Loading results...')

            return extract_results(all_results=all_results(),
                                   which_model=which_model,
                                   which_term=which_term,
                                   which_meas=which_meas)

    @reactive.Calc
    def plot_args():
        return display_args(result_data(), req(display_setting()))

    @render.text
    def info():
        result = result_data()

        l_nc = result.n_clusters['left']
        r_nc = result.n_clusters['right']

        if result.is_empty:
            return ui.markdown(
                '**0** clusters identified (in the left or the right hemisphere).')

        min_beta, mean_beta, max_beta = result.beta_summary()

        return ui.markdown(
            f'**{l_nc + r_nc}** clusters identified ({l_nc} in the left and {r_nc} in the right hemisphere).<br />'
            f'Mean beta value [range] = **{mean_beta:.2f}** [{min_beta:.2f}; {max_beta:.2f}]')

    figure_outputs(plot_args, brain_settings)

    wire_download(input, output, session, plot_args, brain_settings, figure_title)
