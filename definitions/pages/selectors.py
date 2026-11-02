"""
Choosing which map to show: model -> measure -> term.

Its own module because three of these exist (one on the results page, two on
the compare page) and the cascade between the three dropdowns should only be
written once.
"""
from shiny import module, reactive, render, ui

import definitions.layout_styles as styles
from definitions.backend_results import detect_terms


@module.ui
def map_selector_ui():
    """
    Three dropdowns, filled in once a results folder has been read.

    Shown as model | term | measure. The cascade behind them runs
    model -> measure -> term, but that is the server's business: this order is
    the one that reads best.
    """
    return ui.TagList(
        ui.output_ui('model_ui'),
        ui.output_ui('term_ui'),
        ui.output_ui('measure_ui'))


@module.server
def map_selector_server(input, output, session, all_results):
    """Fill the dropdowns in; return a reactive giving (model, term, measure)."""

    @render.ui
    def model_ui():
        all_models = {}
        for group in all_results()['results']:
            sub_models = list(all_results()['results'][group]['model'].unique())
            # TMP: names are kept as they are
            all_models[group] = dict(zip([f'{group}/{m}' for m in sub_models],
                                         sub_models))

        return ui.input_selectize(id='select_model',
                                  label='Choose model',
                                  choices=all_models, width='100%')

    @render.ui
    def measure_ui():
        group, model = input.select_model().split('/')

        group_df = all_results()['results'][group]
        meas_list = list(group_df[group_df.model == model]['meas'].unique())

        return ui.input_selectize(
            id='select_measure', label='Choose measure',
            choices={key: styles.measure_names[key] for key in meas_list},
            width='100%')

    @render.ui
    def term_ui():
        avail_terms = detect_terms(all_results=all_results(),
                                   which_model=input.select_model(),
                                   which_meas=input.select_measure())

        return ui.input_selectize(id='select_term',
                                  label='Choose term',
                                  choices=avail_terms, width='100%')

    @reactive.Calc
    def selection():
        return input.select_model(), input.select_term(), input.select_measure()

    return selection
