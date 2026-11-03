"""
Where the results come from.

Two modes, behind one reactive so no page has to know which is in play:

* preset      -- the folder is named in wizard_config.toml, so it is read once
                 at startup and shared by every visitor
* interactive -- the folder is typed in on the welcome page and read when GO is
                 pressed, which is how the public demo works

A folder that cannot be read is reported as a message in the browser rather
than a traceback, so whoever deployed the app can see what went wrong without
digging through the host's logs.
"""
from shiny import reactive, ui

from definitions.backend_results import detect_models
from definitions.config import CONFIG

# Filled in at import in preset mode: (results, error)
_PRESET_RESULTS = None
_PRESET_ERROR = None


def _load_preset():
    """Read the configured folder once, keeping any failure to report later."""
    global _PRESET_RESULTS, _PRESET_ERROR

    if not CONFIG.preset:
        return

    print(f'[verywise-wizard] reading results from {CONFIG.results_folder} '
          f'({CONFIG.software})...', flush=True)

    try:
        _PRESET_RESULTS = detect_models(CONFIG.results_folder,
                                       results_format=CONFIG.software)
    except Exception as err:  # noqa: BLE001  -- reported in the UI, see below
        _PRESET_ERROR = f'{type(err).__name__}: {err}'
        print(f'[verywise-wizard] could not read the results folder '
              f'{CONFIG.results_folder!r}\n    {_PRESET_ERROR}', flush=True)
        return

    n_models = sum(len(df.model.unique())
                   for df in _PRESET_RESULTS['results'].values())
    print(f'[verywise-wizard] {n_models} models ready', flush=True)


_load_preset()


def preset_failed():
    """The error from reading the configured folder, if there was one."""
    return _PRESET_ERROR


def config_error_page():
    """
    What the app shows instead of its tabs when the configured folder could not
    be read: the path it tried and the reason, which is what the person who
    deployed it needs to fix it.
    """
    return ui.page_fillable(
        ui.div(
            ui.markdown(
                f'## This wizard is not configured correctly</br></br>'
                f'`wizard_config.toml` points at</br></br>'
                f'&emsp;`{CONFIG.results_folder}`</br></br>'
                f'but those results could not be read:</br></br>'
                f'&emsp;`{_PRESET_ERROR}`</br></br>'
                f'Check the `[results] folder` setting (or the `VWWIZARD_RESULTS` '
                f'environment variable), then restart the app.'),
            style='padding: 60px; max-width: 900px'))


def results_source_server(input):
    """
    The reactive every page reads its results from.

    In preset mode it hands back what was loaded at startup; otherwise it reads
    the folder named on the welcome page, when GO is pressed.
    """
    if CONFIG.preset:
        @reactive.Calc
        def all_results():
            return _PRESET_RESULTS

        return all_results

    @reactive.Calc
    @reactive.event(input.go_button)
    def all_results():
        return detect_models(input.results_folder(),
                             results_format=input.analysis_software())

    return all_results
