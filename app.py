from pathlib import Path
from shiny import App, reactive, render, ui

from shinywidgets import render_plotly

import definitions.layout_styles as styles
from definitions.backend_calculations import detect_models, compute_overlap
from definitions.backend_dynamic_plots import plot_overlap

from definitions.ui_functions import welcome_page, main_results_page, overlap_page, \
    describe_input_folder, update_single_result


here = Path(__file__).parent

start_folder = './example_results'

# ======================================================================================================================

app_ui = ui.page_fillable(
    ui.page_navbar(
        # ui.nav_spacer(),
        welcome_page(start_folder, tab_name='welcome_tab'),

        main_results_page(tab_name='main_tab'),

        overlap_page(tab_name='overlap_tab'),

        title=ui.img(src='vwwizard_logo.png', alt='verywise wizard logo', height='150px'),
        selected='welcome_tab',
        position='fixed-top',
        fillable=True,
        padding=[140, 20, 20],  # top, left-right, bottom in px
        bg='white',
        window_title='Verywise Wizard',
        id='navbar'),

    padding=styles.PAGE_PADDING,
    gap=styles.PAGE_GAP,
)


def app_server(input, output, session):

    # TAB 2: MAIN RESULTS
    model1, term1, measure1 = update_single_result('result1', go=input.go_button, input_resdir=input.results_folder)
    model2, term2, measure2 = update_single_result('result2', go=input.go_button, input_resdir=input.results_folder)

    # TAB 1: FOLDER INFO
    @output
    @render.text
    @reactive.event(input.go_button)
    def input_folder_info():
        return describe_input_folder(input.results_folder())

    # TAB 3: OVERLAP
    @render.text
    def overlap_info():
        ovlp_info = compute_overlap(resdir=input.results_folder(),
                                    model1=model1(), term1=term1(), measure1=measure1(),
                                    model2=model2(), term2=term2(), measure2=measure2())[0]

        text = {}
        legend = {}
        for key in [1, 2, 3]:
            text[key] = f'**{ovlp_info[key][1]}%** ({ovlp_info[key][0]} vertices)' if key in ovlp_info.keys() else \
                '**0%** (0 vertices)'
            color = styles.OVLP_COLORS[key-1]
            legend[key] = f'<span style = "background-color: {color}; color: {color}"> oo</span>'

        return ui.markdown(f'There was a {text[3]} {legend[3]} **overlap** between the terms selected:</br>'
                           f'{text[1]} was unique to {legend[1]}  **{model1()}** (<ins>{measure1()}</ins>)</br>'
                           f'{text[2]} was unique to {legend[2]}  **{model2()}** (<ins>{measure2()}</ins>)')

    @reactive.Calc
    def overlap_brain3D():
        return plot_overlap(resdir=input.results_folder(),
                            model1=model1(), term1=term1(), measure1=measure1(),
                            model2=model2(), term2=term2(), measure2=measure2(),
                            surf=input.overlap_select_surface(),
                            resol=input.overlap_select_resolution())

    @render_plotly
    def overlap_brain_left():
        brain = overlap_brain3D()
        return brain['left']

    @render_plotly
    def overlap_brain_right():
        brain = overlap_brain3D()
        return brain['right']


app = App(app_ui, app_server, static_assets=here / 'www')

