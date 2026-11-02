"""
verywise wizard pages
=====================
One module per tab, with everything they share underneath.

Modules
-------
common     : shared widgets, layout rows and the two figure outputs
selectors  : map_selector  -- the model / term / measure cascade
download   : the two-step figure download (render, then hand over)
welcome    : the WELCOME tab
results    : the MAIN RESULTS tab
compare    : the COMPARE tab

Public API
----------
Each tab gives a `*_page()` function to put in the navbar, and the two that
have a server side give an `update_*()` module server to call from app.py.
"""
from .compare import compare_page, update_compare
from .results import main_results_page, update_single_result
from .welcome import describe_input_folder, welcome_page

__all__ = [
    'compare_page', 'describe_input_folder', 'main_results_page',
    'update_compare', 'update_single_result', 'welcome_page',
]
