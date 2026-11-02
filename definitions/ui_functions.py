import os
import tempfile

from shiny import Inputs, Outputs, Session, module, reactive, render, req, ui
from shinywidgets import output_widget, render_plotly

import definitions.layout_styles as styles
from definitions import plotting as vwp
from definitions.backend_results import cluster_stats, detect_terms, extract_results
from definitions.plotting.atlas import region_names
from definitions.plotting.kaleido_patch import chrome_available


# ------------------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------------------

def display_args(result, which_output):
    """
    Translate a VWResult into the arguments the plotting engine needs, for
    either display mode. Both the brains and the legend are built from these,
    so the two can never disagree about the colour scale.
    """
    if which_output == 'clusters':
        return dict(lh=result.clusters['left'].astype(float),
                    rh=result.clusters['right'].astype(float),
                    lh_mask=result.mask['left'],
                    rh_mask=result.mask['right'],
                    cmap=styles.CLUSTER_COLORMAP,
                    discrete=True,
                    label='Cluster',
                    mode=vwp.CLUSTERS,
                    stats=cluster_stats(result))

    return dict(lh=result.betas['left'],
                rh=result.betas['right'],
                lh_mask=result.mask['left'],
                rh_mask=result.mask['right'],
                cmap=None,
                discrete=None,
                label=styles.BETA_LABEL,
                mode=vwp.DENSITY,
                stats=None)


def fill_width(fig):
    """Let a figure follow the width of the card it sits in."""
    fig.update_layout(width=None, autosize=True)
    return fig


def set_if_changed(value, new):
    """
    Update a reactive value only when it really differs.

    reactive.Value.set() compares by identity, so handing it an equal-but-new
    tuple would still invalidate everything downstream. Comparing by value
    instead is what lets, say, a change of surface type leave the legend alone.
    """
    with reactive.isolate():
        if value() != new:
            value.set(new)


def selection_pane(*controls, col_widths=(3, 3, 3, 3)):
    # Never hand bslib more widths than there are controls, or it warns
    return ui.layout_columns(*controls, col_widths=col_widths[:len(controls)],
                             gap='20px', style=styles.SELECTION_PANE)


def roi_choice(id_):
    # 'unknown' is the medial wall, which has no boundary worth drawing
    regions = [r for r in region_names() if r != 'unknown']
    return ui.input_selectize(id=id_, label='ROI contours (optional)',
                              choices=regions, selected=None, multiple=True,
                              options={'plugins': ['remove_button'],
                                       'placeholder': 'No contours'})


def surface_choice(id_):
    return ui.input_selectize(id=id_, label='Surface type',
                              choices=styles.SURFACE_NAMES, selected='pial')


def resolution_choice(id_):
    return ui.input_selectize(id=id_, label='Resolution',
                              choices=styles.RESOLUTION_NAMES, selected='fsaverage6')


# ------------------------------------------------------------------------------
# Define the UI and server for the WELCOME tab
# ------------------------------------------------------------------------------


def welcome_page(start_folder, tab_name):
    return ui.nav_panel(
            'Welcome',
            ui.markdown('</br>Welcome to the **verywise WIZARD** app!</br></br>'
                        ''
                        'Here you can visualize the statistical brain surface maps obtained from your `verywise` '
                        '(or `QDECR`) analysis in an interactive way.</br>'
                        'To start, please point us to the location of your project results. '
                        'This can be:</br>'
                        '&emsp;⇢ *A path to the results folder*</br>'
                        '&emsp;&emsp;[this is the fastest, especially if you have a lot of results, '
                        'but it will only work if you are using the application "offline" (i.e you are running if from your '
                        'computer)]</br>'
                        '&emsp;⇢ *A directory inside a (public) github repository*</br>'
                        '&emsp;&emsp;[this is most flexible but it requires loading all '
                        'results before getting started so it may take a minute]</br>'
                        'A word of advice? If you have *a lot* of result files (e.g. you have run a '
                        'bunch of models or models with lots of covariates) you are probably better '
                        'off downloading them and running the app "offline". See the instructions on '
                        'the GitHub repo (top right corner).'
                        '</br>'
                        'Hit **GO** to see an overview of the results in the selected folder.</br>'),
            ui.input_radio_buttons(id='analysis_software', label='Analyses ran using:',
                                   choices={'QDECR': ui.markdown('`QDECR`'),
                                            'verywise': ui.markdown('`verywise`')},
                                   inline=True, selected='verywise'),
            ui.div(ui.layout_columns(
                 ui.input_text(id='results_folder', label='', value=start_folder),
                 ui.input_action_button(id='go_button',
                                        label='GO',
                                        style=f'color: white; font-weight: bold; '
                                              f'background-color: {styles.VW_COLOR_PALETTE["dark-red"]}; '
                                              f'border-color: {styles.VW_COLOR_PALETTE["dark-red"]}; '
                                              f'padding-top: 6px; padding-bottom: 6px;'),

                 col_widths=(10, 1, -1)
            )),
            ' ',  # spacer
            ui.output_ui(id='input_folder_info'),
            ui.markdown('Have fun!</br></br></br></br>'),
            ui.layout_columns(
                ui.output_image("funders_image"),
                ui.markdown('This work was supported by the **FLAG-ERA** grant [*Infant2Adult*](https://www.infant2adult.com/home) '
                        'and by The Netherlands Organization for Health Research and Development (**ZonMw**, grant number 16080606).'),
                        col_widths=(3, 8, -1)),
            value=tab_name)


def describe_input_folder(model_dict, selected_folder):

    tab_spacing = '&emsp;&emsp;&emsp;'  # space between the "columns"
    info_text = ''
    for dir in sorted(model_dict['results'].keys()):

        sub_dir_df = model_dict['results'][dir]

        sub_text = f'</br>&emsp;**{dir}**<table>'
        for sub_model in sorted(sub_dir_df.model.unique()):

            sub_mod_df = sub_dir_df.loc[sub_dir_df.model == sub_model]

            # Extract the outcomes (measures) examines in each model
            avail_meas = sorted(sub_mod_df.meas.unique())
            avail_meas_text = f'</br>{tab_spacing}'.join(f'<span style="background-color:{styles.measure_colors[meas]};'
                                                         f'border-radius:16px;">'
                                                         f' {meas}&nbsp;</span>' for meas in avail_meas)

            hemi_rows = []
            for sub_meas in avail_meas:
                sub_meas_df = sub_mod_df.loc[sub_mod_df.meas == sub_meas]
                avail_hemi = sorted(sub_meas_df.hemi.unique())
                hemi_rows.append('&ensp;'.join(f'<span style="background-color:{styles.VW_COLOR_PALETTE["light-blue"]};'
                                               f'border-radius:16px;">'
                                               f' {hemi[0].upper()}&nbsp;</span>' for hemi in avail_hemi))

            avail_hemi_text = f'</br>{tab_spacing}'.join(hemi_rows)

            sub_table = f'<td VALIGN=TOP>{tab_spacing}{sub_model}</td>' \
                        f'<td VALIGN=TOP>{tab_spacing}{avail_meas_text}</td>' \
                        f'<td VALIGN=TOP>{tab_spacing}{avail_hemi_text}</td></tr>'

            sub_text = sub_text + sub_table

        info_text = info_text + sub_text + '</table>'

    folder_info = ui.markdown(
        f'You have selected the directory: `{selected_folder}`</br></br>'
        f'This folder contains the following models:{info_text}</br></br>'
        f'Now, you can navigate to the **"Main results"** tab to choose which maps you would like to see. '
        f'If you select *two* maps on the Main results page, you can also see their overlap by navigating to the '
        f'**"Overlap"** tab.')

    return folder_info


# ------------------------------------------------------------------------------
# Define the UI and server modules for the MAIN RESULTS tab
# ------------------------------------------------------------------------------


def main_results_page(tab_name):
    return ui.nav_panel(
        'Main results',
        ui.markdown('</br>Select the map(s) you want to see, with the settings you prefer and hit'
                 ' **GO** to visualize the 3D brains.</br></br>Note: sometimes it can take a second to'
                 ' draw those pretty brains, so you may need a little pinch of patience.'
                 ' If you do not have that kind of time, you can reduce the resolution to low.</br>'),
        single_result_ui('result1'),
        single_result_ui('result2'),
        ' ',  # spacer
        value=tab_name)


@module.ui
def single_result_ui():

    # Buttons
    update_button = ui.div(ui.input_action_button(id='update_button',
                                                  label='GO',
                                                  class_='btn btn-dark action-button'),
                           style='padding-top: 15px')

    # One button, with a switch for what it hands you
    download_controls = ui.div(
        ui.input_radio_buttons(id='download_format', label=None,
                               choices=styles.DOWNLOAD_FORMATS, selected='png',
                               inline=True),
        ui.download_button(id='download_figure_button', label='Download figure'),
        style='padding-top: 5px')

    return ui.div(
        # Selection pane
        ui.layout_columns(
            selection_pane(
                ui.output_ui('model_ui'),
                ui.output_ui('term_ui'),
                ui.output_ui('measure_ui'),
                ui.input_selectize(id='select_output', label='Display',
                                   choices=styles.OUTPUT_NAMES, selected='betas'),
                surface_choice('select_surface'),
                resolution_choice('select_resolution'),
                roi_choice('select_roi'),
            ),
            update_button,
            col_widths=(11, 1)
        ),
        # Info
        ui.layout_columns(
            ui.row(ui.output_ui('info'), style=styles.INFO_MESSAGE),
            download_controls,
            col_widths=(8, -1, 3)
        ),
        # Brain plots: both hemispheres live in one figure, so the card can be
        # expanded on its own, while the legend stays put beside it.
        ui.layout_columns(
            ui.card(ui.card_header('Brain surface maps'),
                    output_widget('brains'),
                    full_screen=True),  # expand icon appears when hovering over the card body
            ui.card(ui.card_header('Legend'),
                    output_widget('legend')),
            col_widths=(8, 4)
        ))


@module.server
def update_single_result(input: Inputs, output: Outputs, session: Session,
                         all_results) -> tuple:

    @output

    @render.ui
    def model_ui():

        all_models = dict()
        for m in all_results()['results'].keys():

            sub_models = list(all_results()['results'][m]['model'].unique())
            # TMP: names are kept as they are
            all_models[m] = dict(zip([f'{m}/{sm}' for sm in sub_models],
                                    sub_models))

        return ui.input_selectize(
            id='select_model',
            label="Choose model",
            choices=all_models)

    @render.ui
    def measure_ui():
        which_model = input.select_model()

        group, model = which_model.split('/')

        group_df = all_results()['results'][group]
        model_df = group_df[group_df.model == model]

        meas_list = list(model_df['meas'].unique())

        avail_measures = {key: styles.measure_names[key] for key in meas_list}

        return ui.input_selectize(
            id='select_measure',
            label="Choose measure",
            choices=avail_measures)

    @render.ui
    def term_ui():

        avail_terms = detect_terms(all_results=all_results(),
                                   which_model=input.select_model(),
                                   which_meas=input.select_measure())

        return ui.input_selectize(
            id='select_term',
            label='Choose term',
            choices=avail_terms)

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
        set_if_changed(data_settings, (input.select_model(),
                                       input.select_term(),
                                       input.select_measure()))
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

    @render_plotly
    def brains():
        args = plot_args()
        surface, resolution, roi_names = req(brain_settings())

        with ui.Progress(min=0, max=1) as p:
            p.set(0, message='Drawing the brains...')

            return fill_width(vwp.surf_figure(
                args['lh'], args['rh'], args['lh_mask'], args['rh_mask'],
                cmap=args['cmap'], discrete=args['discrete'],
                fs_template=resolution,
                surface=surface,
                roi_names=roi_names))

    @render_plotly
    def legend():
        args = plot_args()

        return fill_width(vwp.panel_figure(
            args['lh'], args['rh'], args['lh_mask'], args['rh_mask'],
            cmap=args['cmap'], discrete=args['discrete'],
            label=args['label'], mode=args['mode'], stats=args['stats']))

    @reactive.Calc
    def resolved_download_format():
        """
        PNG export needs a Chrome that kaleido can drive, which a deployed
        container may not have (and pip cannot install). Fall back to HTML
        rather than handing back a broken download.
        """
        wanted = input.download_format()

        if wanted == 'png' and not chrome_available():
            return 'html'

        return wanted

    @render.download_button(
        filename=lambda: f'verywise_figure.{resolved_download_format()}')
    def download_figure_button():
        args = plot_args()
        surface, resolution, roi_names = req(brain_settings())

        which_format = resolved_download_format()

        if which_format != input.download_format():
            ui.notification_show(
                'PNG export needs Google Chrome, which is not available here. '
                'Downloading an interactive HTML figure instead.',
                type='warning', duration=10)

        with ui.Progress(min=0, max=2) as p:
            if which_format == 'png':
                p.set(0, message='Starting the image renderer...',
                      detail='The first PNG takes about a minute while a headless '
                             'browser starts up. Any later one is much quicker.')
            else:
                p.set(0, message='Building the figure...')

            with tempfile.TemporaryDirectory() as tmp_dir:
                out_file = os.path.join(tmp_dir, f'figure.{which_format}')

                # No views are passed, so each format keeps its own default:
                # the PNG gets the full six-view figure, the HTML the lateral
                # view shown on screen.
                # Built from the same snapshot the brains were drawn from, so
                # the download always matches what is on screen.
                shared = dict(
                    lh=args['lh'], rh=args['rh'],
                    lh_mask=args['lh_mask'], rh_mask=args['rh_mask'],
                    cmap=args['cmap'], discrete=args['discrete'],
                    fs_template=resolution,
                    surface=surface,
                    roi_names=roi_names,
                    colorbar_label=args['label'],
                    mode=args['mode'], stats=args['stats'],
                    title=figure_title())

                p.set(1, message='Rendering the figure...')

                if which_format == 'png':
                    try:
                        vwp.surf_png(output_file=out_file, **shared)
                    except Exception as e:
                        # Chrome was found but could not render (sandboxing, a
                        # partial download, no memory...). Say what happened
                        # instead of handing back a broken file.
                        ui.notification_show(
                            f'Could not render the PNG ({type(e).__name__}). '
                            'Try the HTML download instead.',
                            type='error', duration=15)
                        raise
                else:
                    vwp.surf_html(output_html=out_file, **shared)

                p.set(2, message='Done!')

                with open(out_file, 'rb') as f:
                    yield f.read()

    return input.select_model, input.select_term, input.select_measure


# ------------------------------------------------------------------------------
# Define the UI and server for the OVERLAP tab
# ------------------------------------------------------------------------------


def overlap_page(tab_name):
    return ui.nav_panel(
        'Overlap',
        ' ',  # spacer - fix with padding later or also never
        overlap_page_content,
        ' ',  # spacer
        value=tab_name)


overlap_page_content = ui.div(
        # Selection pane
        selection_pane(
            surface_choice('overlap_select_surface'),
            resolution_choice('overlap_select_resolution'),
            roi_choice('overlap_select_roi'),
        ),
        # Info
        ui.row(
            ui.output_ui('overlap_info'),
            style=styles.INFO_MESSAGE
        ),
        # Brain plots
        ui.card(ui.card_header('Overlap between the selected maps'),
                output_widget('overlap_brains'),
                full_screen=True))
