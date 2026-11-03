"""
verywise wizard pages
=====================
One module per tab, with everything they share underneath.

Modules
-------
common     : shared widgets, layout rows and the two figure outputs
selectors  : map_selector  -- the model / term / measure cascade
download   : the two-step figure download (render, then hand over)
source     : where the results come from, preset or typed in
welcome    : the WELCOME tab, or the ABOUT tab of a configured wizard
results    : the MAIN RESULTS tab
compare    : the COMPARE tab

Public API
----------
Each tab gives a `*_page()` function to put in the navbar, and the two that
have a server side give an `update_*()` module server to call from app.py.
"""
from .common import repo_links
from .compare import compare_page, update_compare
from .results import main_results_page, update_single_result
from .source import config_error_page, preset_failed, results_source_server
from .welcome import describe_input_folder, welcome_info_output, welcome_page

__all__ = [
    'compare_page', 'config_error_page', 'describe_input_folder',
    'main_results_page', 'preset_failed', 'repo_links',
    'results_source_server', 'update_compare', 'update_single_result',
    'welcome_info_output', 'welcome_page',
]
