from pathlib import Path

from shiny import App, render, ui

import definitions.layout_styles as styles
from definitions.config import CONFIG
from definitions.pages import (
    compare_page, config_error_page, main_results_page, preset_failed,
    repo_links, results_source_server, update_compare, update_single_result,
    welcome_info_output, welcome_page,
)

here = Path(__file__).parent

# Where the demo starts from when no results folder is configured. A wizard of
# your own names its folder in wizard_config.toml instead of here, and then
# skips the welcome page altogether -- see README, "Make your own wizard".
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
        repo_links(),     # this repo, or a fork and where it came from

        title=ui.img(src='vwwizard_logo.png', alt='verywise wizard logo',
                     height=styles.LOGO_HEIGHT),
        selected='welcome_tab',
        fillable=True,
        # top, left-right, bottom in px: the top has to clear the fixed navbar
        padding=[styles.PAGE_PADDING_TOP, 20, 20],
        # position and bg moved in here in shiny 1.3
        navbar_options=ui.navbar_options(position='fixed-top', bg='white'),
        window_title=CONFIG.title,
        id='navbar'),

    padding=styles.PAGE_PADDING,
    gap=styles.PAGE_GAP,
)


def app_server(input, output, session):

    # Preset from wizard_config.toml, or read from the folder typed on the
    # welcome page when GO is pressed
    all_results = results_source_server(input)

    # TAB 2: MAIN RESULTS  ============================================================
    update_single_result('result1', all_results=all_results)

    # TAB 3: COMPARE  =================================================================
    update_compare('compare', all_results=all_results)

    # TAB 1: FOLDER INFO =============================================================
    welcome_info_output(input, all_results)

    @render.image
    def funders_image():
        img = {"src": here / "www/funders.png", "width": "100%"}
        return img


# A configured folder that could not be read is reported in the browser, rather
# than leaving whoever deployed the app with a traceback in the host's logs.
if preset_failed():
    app = App(config_error_page(), lambda i, o, s: None,
              static_assets=here / 'www')
else:
    app = App(app_ui, app_server, static_assets=here / 'www')
