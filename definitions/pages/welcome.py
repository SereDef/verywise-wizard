"""
The first tab, in either of its two forms.

Without a configured results folder it asks for one: point the app at a folder 
and hit GO. With one (see wizard_config.toml) it instead introduces the wizard 
-- its own title and description, above a summary of the results the app already 
holds.
"""
from shiny import reactive, render, ui

import definitions.layout_styles as styles
from definitions.config import CONFIG
from definitions.pages.common import nav_title

FUNDING = ('This work was supported by the **FLAG-ERA** grant '
           '[*Infant2Adult*](https://www.infant2adult.com/home) '
           'and by The Netherlands Organization for Health Research and '
           'Development (**ZonMw**, grant number 16080606).')


def funding_row():
    return ui.layout_columns(
        ui.output_image('funders_image'),
        ui.markdown(FUNDING),
        col_widths=(3, 8, -1))


def welcome_page(start_folder, tab_name):
    """The WELCOME page, or the ABOUT page where results are configured."""
    if CONFIG.preset:
        return about_page(tab_name)

    return ui.nav_panel(
            nav_title('house', 'Welcome'),
            ui.markdown('</br>Welcome to the **verywise WIZARD** app!</br></br>'
                        'Here you can visualize the statistical brain surface maps obtained from your [`verywise`](https://seredef.github.io/verywise/) '
                        '(or `QDECR`) analysis in an interactive way.</br>'
                        'To start, please point us to the location of your project results. '
                        'This can be:</br>'
                        '&emsp;⇢ *A path to the results folder*</br>'
                        '&emsp;&emsp;[this is the fastest option, especially if you ran a multiple / larger models, '
                        'but it only works when using the application "offline" (see [instructions](https://github.com/SereDef/verywise-wizard#running-the-application-locally)) ]</br>'
                        '&emsp;⇢ *A directory inside a (public) github repository*</br>'
                        '&emsp;&emsp;[this is most flexible but it requires loading all '
                        'results before getting started, which may take up to a few minutes]</br></br>'
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
            funding_row(),
            value=tab_name)


DEFAULT_INTRO = (
    'The brain surface maps in this wizard were produced with '
    '[`verywise`](https://seredef.github.io/verywise/). '
    'Head to the **"Main results"** tab to look at a single map, or to '
    '**"Compare"** to put two of them side by side.')


def about_page(tab_name):
    """
    The welcome page of a configured wizard: whose results these are, and what
    is in them. No folder box and no GO button -- they are already loaded.
    """
    return ui.nav_panel(
        nav_title('house', 'Welcome'),
        # ui.h2, not markdown: a '##' that follows anything on its line (the
        # spacer this used to carry) is printed literally instead of a heading
        ui.h2(CONFIG.title, style='padding-top: 20px'),
        ui.markdown(CONFIG.intro or DEFAULT_INTRO),
        ' ',  # spacer
        ui.output_ui(id='input_folder_info'),
        funding_row(),
        value=tab_name)


def welcome_info_output(input, all_results):
    """
    Register the summary of the results folder.

    In preset mode it renders as soon as the page loads; otherwise it waits for
    GO, so that typing in the folder box does not keep rebuilding it.
    """
    if CONFIG.preset:
        @render.ui
        def input_folder_info():
            # No selected_folder: the reader did not choose it, so the summary
            # does not report a path back at them
            return describe_input_folder(model_dict=all_results(),
                                         selected_folder=None)

        return

    @render.ui
    @reactive.event(input.go_button)
    def input_folder_info():
        return describe_input_folder(model_dict=all_results(),
                                     selected_folder=input.results_folder())


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

    # A configured wizard was not pointed anywhere by whoever is reading it,
    # so there is no selection to report back
    chosen = (f'You have selected the directory: `{selected_folder}`</br></br>'
              if selected_folder else '')

    folder_info = ui.markdown(
        f'{chosen}'
        f'Models:{info_text}</br></br>')

    return folder_info
