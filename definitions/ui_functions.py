from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from shinywidgets import output_widget, render_plotly

import io

import definitions.layout_styles as styles
from definitions.backend_calculations import detect_models, detect_terms, extract_results, compute_overlap
from definitions.backend_dynamic_plots import plot_surfmap, plot_overlap
from definitions.backend_static_plots import beta_colorbar_density_figure, clusterwise_means_figure, plot_brain_2d


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
                        '&emsp;&emsp;[this is most flexible but it requires loading all'
                        'results before getting started so it may take a minute]</br>'
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

    # TODO: complete this and move to styles
    outcome_colors = {'area': '#FFFFCC',
                      'thickness': '#FFCCCC'}

    info_text = ''
    for dir in sorted(model_dict['results'].keys()):

        sub_dir_df = model_dict['results'][dir]

        sub_text = f'</br>&emsp;**{dir}**<table>'
        for sub_model in sorted(sub_dir_df.model.unique()):

            sub_mod_df = sub_dir_df.loc[sub_dir_df.model == sub_model]

            # Extract the outcomes (measures) examines in each model
            avail_meas = sorted(sub_mod_df.meas.unique())
            avail_meas_text = f'</br>{tab_spacing}'.join(f'<span style="background-color:{outcome_colors[meas]};'
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

    model_choice = ui.output_ui('model_ui')

    term_choice = ui.output_ui('term_ui')

    measure_choice = ui.output_ui('measure_ui')

    output_choice = ui.input_selectize(
        id='select_output',
        label='Display',
        choices={'betas': 'Beta values', 'clusters': 'Clusters'},
        selected='betas')

    surface_choice = ui.input_selectize(
        id='select_surface',
        label='Surface type',
        choices={'pial': 'Pial', 'infl': 'Inflated', 'flat': 'Flat'},
        selected='pial')

    resolution_choice = ui.input_selectize(
        id='select_resolution',
        label='Resolution',
        choices={'fsaverage': 'High (164k nodes)', 'fsaverage6': 'Medium (50k nodes)', 'fsaverage5': 'Low (10k modes)'},
        selected='fsaverage6')

    # Buttons
    update_button = ui.div(ui.input_action_button(id='update_button',
                                                  label='GO',
                                                  class_='btn btn-dark action-button'),
                           style='padding-top: 15px')

    download_figure_button = ui.div(ui.download_button(id='download_figure_button',
                                                       label='Download png'),
                                                       # class_='btn btn-light action-button'),
                                    style='padding-top: 15px')

    return ui.div(
        # Selection pane
        ui.layout_columns(
            ui.layout_columns(
                model_choice, term_choice, measure_choice, output_choice, surface_choice, resolution_choice,
                col_widths=(2, 2, 2, 2, 2, 2),  # negative numbers for empty spaces
                gap='30px',
                style=styles.SELECTION_PANE),
            update_button,
            col_widths=(11, 1)
        ),
        # Info
        ui.layout_columns(
            ui.row(ui.output_ui('info'), style=styles.INFO_MESSAGE),
            download_figure_button,
            col_widths=(8, -2, 2)
        ),
        # Brain plots
        ui.layout_columns(
            ui.card('Left hemisphere',
                    output_widget('brain_left'),
                    full_screen=True),  # expand icon appears when hovering over the card body
            ui.card('Right hemisphere',
                    output_widget('brain_right'),
                    full_screen=True),
            ui.output_plot('color_legend'),
            col_widths=(4, 4, 4)
        ))

@module.server
def update_single_result(input: Inputs, output: Outputs, session: Session,
                         all_results) -> tuple:

    @reactive.Calc
    def input_resdir():
        return all_results()['results_directory']
    
    @reactive.Calc
    def input_resformat():
        return all_results()['results_format']


    @output

    @render.ui
    # @reactive.event(go)
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

        # TODO: clean all the measure names
        clean_names = {'thickness': 'Thickness',
                       'area': 'Surface area',
                       'curv': 'Curvature',
                       'w_g.pct': 'Grey-white ratio'}

        avail_measures = {key: clean_names[key] for key in meas_list}

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

    @reactive.Calc
    @reactive.event(input.update_button, ignore_none=True)
    def single_result_output():
        with ui.Progress(min=1, max=6) as p:

            p.set(1, message="Loading results...")

            # Extract results
            min_beta, max_beta, mean_beta, n_clusters, sign_clusters, sign_betas, all_betas = extract_results(
                which_model=input.select_model(),
                which_term=input.select_term(),
                which_meas=input.select_measure(),
                resdir=input_resdir(),
                resformat=input_resformat())

            p.set(2, message="Calculating maps...")

            l_nc = int(n_clusters[0])
            r_nc = int(n_clusters[1])

            if l_nc == r_nc == 0:
                info = ui.markdown(
                    f'**0** clusters identified (in the left or the right hemisphere).')
                brains = {'left': None, 'right': None}
                legend_plot = None

            else:
                info = ui.markdown(
                    f'**{l_nc + r_nc}** clusters identified ({l_nc} in the left and {r_nc} in the right hemisphere).<br />'
                    f'Mean beta value [range] = **{mean_beta:.2f}** [{min_beta:.2f}; {max_beta:.2f}]')

                p.set(3, message="Calculating maps...")

                brains = plot_surfmap(
                    min_beta, max_beta, n_clusters, sign_clusters, sign_betas,
                    surf=input.select_surface(),
                    resol=input.select_resolution(),
                    output=input.select_output())

                p.set(4, message="Rendering brains...")

                if input.select_output() == 'betas':
                    legend_plot = beta_colorbar_density_figure(sign_betas, all_betas,
                                                             figsize=(4, 6),
                                                             colorblind=False,
                                                             set_range=None)
                else:
                    legend_plot = clusterwise_means_figure(sign_clusters, sign_betas,
                                                           figsize=(4, 6),
                                                           cmap=styles.CLUSTER_COLORMAP,
                                                           tot_clusters=int(n_clusters[0]+n_clusters[1]))

                p.set(5, message="...almost done!")

        return info, brains, legend_plot, sign_betas, all_betas

    @render.text
    def info():
        md_info = single_result_output()[0]
        return md_info

    @render_plotly
    def brain_left():
        brain = single_result_output()[1]
        return brain['left']

    @render_plotly
    def brain_right():
        brain = single_result_output()[1]
        return brain['right']

    @render.plot(alt="All observed beta values")
    def color_legend():
        return single_result_output()[2]

    @render.download(filename=f"verywise_figure.png")
    def download_figure_button():
        stat_fig = plot_brain_2d(sign_betas = single_result_output()[3], 
                                 all_observed_betas = single_result_output()[4],
                                 model=input.select_model(),
                                 meas=input.select_measure(),
                                 resol=input.select_resolution(),
                                 title=None)
        with io.BytesIO() as buf:
            stat_fig.savefig(buf, format="png")
            yield buf.getvalue()

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
        ui.layout_columns(
            ui.input_selectize(
                id='overlap_select_surface',
                label='Surface type',
                choices={'pial': 'Pial', 'infl': 'Inflated', 'flat': 'Flat'},
                selected='pial'),
            ui.input_selectize(
                id='overlap_select_resolution',
                label='Resolution',
                choices={'fsaverage': 'High (164k nodes)', 'fsaverage6': 'Medium (50k nodes)', 'fsaverage5': 'Low (10k modes)'},
                selected='fsaverage6'),

            ui.div(' ', style='padding-top: 80px'),

            col_widths=(3, 3, 2),  # negative numbers for empty spaces
            gap='30px',
            style=styles.SELECTION_PANE
        ),
        # Info
        ui.row(
            ui.output_ui('overlap_info'),
            style=styles.INFO_MESSAGE
        ),
        # Brain plots
        ui.layout_columns(
            ui.card('Left hemisphere',
                    output_widget('overlap_brain_left'),
                    full_screen=True),  # expand icon appears when hovering over the card body
            ui.card('Right hemisphere',
                    output_widget('overlap_brain_right'),
                    full_screen=True)
        ))
