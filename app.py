from pathlib import Path

from faicons import icon_svg
from shiny import App, reactive, render, ui

import definitions.layout_styles as styles
from definitions.backend_results import detect_models
from definitions.pages import (
    compare_page, describe_input_folder, main_results_page, update_compare,
    update_single_result, welcome_page,
)

here = Path(__file__).parent

start_folder = './verywise_example_results'
# Lorenza (QDECR)
# start_folder = './qdecr_example_results'
# start_folder = '/Users/Serena/Desktop/PA-brain-project/results'
# start_folder = 'https://github.com/SereDef/PA-brain-project/tree/main/results'

# Annet (verywise)
# start_folder = 'https://github.com/SereDef/vw_testing/tree/main/results/'
# start_folder = '/Users/Serena/Desktop/annet/longi-ADHD-brain/results'

# The brand colours now live in layout_styles (styles.VWW_BLUE and friends)
# ======================================================================================================================

app_ui = ui.page_fillable(
    ui.page_navbar(
        ui.head_content(ui.tags.style(styles.NAVBAR_CSS)),

        # ui.nav_spacer(),
        welcome_page(start_folder, tab_name='welcome_tab'),
        main_results_page(tab_name='main_tab'),
        compare_page(tab_name='compare_tab'),

        ui.nav_spacer(),  # Pushes the next item(s) to the right
        ui.nav_control(
            ui.a(
                icon_svg("github", fill=styles.VWW_BLUE, width="26px", height="26px"),
                href="https://github.com/SereDef/verywise-wizard",
                target="_blank",
                style="margin-left: 20px; vertical-align: top;"
            )
        ),

        title=ui.img(src='vwwizard_logo.png', alt='verywise wizard logo',
                     height=styles.LOGO_HEIGHT),
        selected='welcome_tab',
        fillable=True,
        # top, left-right, bottom in px: the top has to clear the fixed navbar
        padding=[styles.PAGE_PADDING_TOP, 20, 20],
        # position and bg moved in here in shiny 1.3
        navbar_options=ui.navbar_options(position='fixed-top', bg='white'),
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
    update_single_result('result1', all_results=all_results)

    # TAB 3: COMPARE  =================================================================
    update_compare('compare', all_results=all_results)

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


app = App(app_ui, app_server, static_assets=here / 'www')
