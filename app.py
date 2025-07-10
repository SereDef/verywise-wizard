from pathlib import Path
from shiny import App, reactive, render, ui

from shinywidgets import render_plotly
from faicons import icon_svg

import definitions.layout_styles as styles
from definitions.backend_calculations import detect_models, compute_overlap
from definitions.backend_dynamic_plots import plot_overlap

from definitions.ui_functions import welcome_page, main_results_page, overlap_page, \
    describe_input_folder, update_single_result


here = Path(__file__).parent

# start_folder = './example_results'
# Lorenza (QDECR)
start_folder = '/Users/Serena/Desktop/PA-brain-project/results'
# start_folder = 'https://github.com/SereDef/PA-brain-project/tree/main/results'

# Annet (verywise)
# start_folder = 'https://github.com/SereDef/vw_testing/tree/main/results/'
# start_folder = '/Users/Serena/Desktop/VW_WIZARD/vw_testing/results'

vww_blue = '#001f60'
vww_red = '#95013a'
vww_grey = '#c7cfe2'
vww_pink = '#d4acb8'
# ======================================================================================================================

app_ui = ui.page_fillable(
    ui.page_navbar(
        # ui.nav_spacer(),
        welcome_page(start_folder, tab_name='welcome_tab'),
        main_results_page(tab_name='main_tab'),
        overlap_page(tab_name='overlap_tab'),

        ui.nav_spacer(),  # Pushes the next item(s) to the right
        ui.nav_control(
            ui.a(
                icon_svg("github", fill=vww_blue, width="26px", height="26px"),
                href="https://github.com/SereDef/verywise-wizard",
                target="_blank",
                style="margin-left: 20px; vertical-align: top;"
            )
        ),

        title=ui.img(src='vwwizard_logo.png', alt='verywise wizard logo', height='140px'),
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

    # Extract results from folder or link 
    @reactive.Calc
    @reactive.event(input.go_button)
    def all_results():
        return detect_models(input.results_folder(), 
                             results_format=input.analysis_software())

    # TAB 2: MAIN RESULTS  ============================================================
    model1, term1, measure1 = update_single_result('result1', all_results=all_results)
    model2, term2, measure2 = update_single_result('result2', all_results=all_results)

    # TAB 1: FOLDER INFO =============================================================
    @output
    @render.text
    @reactive.event(input.go_button)
    def input_folder_info():
        return describe_input_folder(model_dict=all_results(), 
                                     selected_folder=input.results_folder())
    
    @render.image  
    def funders_image():
        img = {"src": here / "www/funders.png", "width": "100%"}  
        return img

    # TAB 3: OVERLAP  ===============================================================
    @reactive.Calc
    def overlap_results():
        return compute_overlap(model1=model1(), term1=term1(), measure1=measure1(),
                               model2=model2(), term2=term2(), measure2=measure2(),
                               resdir=all_results()['results_directory'],
                               resformat=all_results()['results_format'])

    @render.text
    def overlap_info():
        ovlp_info = overlap_results()[0]

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
        return plot_overlap(overlap_maps = overlap_results()[1],
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

