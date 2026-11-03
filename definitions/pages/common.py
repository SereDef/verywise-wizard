"""
Pieces every page is built from: the shared widgets, the shared layout rows,
and the two figure outputs.

Anything that appears on more than one page lives here, so the page modules
only hold what is actually particular to them.
"""
from faicons import icon_svg
from shiny import reactive, req, ui
from shinywidgets import output_widget, render_plotly

import definitions.layout_styles as styles
from definitions import plotting as vwp
from definitions.backend_results import cluster_stats
from definitions.config import CONFIG, UPSTREAM_NAME, UPSTREAM_REPO
from definitions.plotting.atlas import region_names


# ------------------------------------------------------------------------------
# Figure arguments
# ------------------------------------------------------------------------------

def display_args(result, which_output):
    """
    Translate a VWResult into the arguments the plotting engine needs, for
    either display mode. Both the brains and the legend are built from these,
    so the two can never disagree about the colour scale.
    """
    if which_output == 'clusters':
        return dict(lh=result.clusters['left'].astype(float),
                    rh=result.clusters['right'].astype(float),
                    lh_mask=result.mask['left'],
                    rh_mask=result.mask['right'],
                    cmap=styles.CLUSTER_COLORMAP,
                    discrete=True,
                    label='Cluster',
                    mode=vwp.CLUSTERS,
                    stats=cluster_stats(result))

    return dict(lh=result.betas['left'],
                rh=result.betas['right'],
                lh_mask=result.mask['left'],
                rh_mask=result.mask['right'],
                cmap=None,
                discrete=None,
                label=styles.BETA_LABEL,
                mode=vwp.DENSITY,
                stats=None)


def fill_width(fig):
    """Let a figure follow the width of the card it sits in."""
    fig.update_layout(width=None, autosize=True)
    return fig


def set_if_changed(value, new):
    """
    Update a reactive value only when it really differs.

    reactive.Value.set() compares by identity, so handing it an equal-but-new
    tuple would still invalidate everything downstream. Comparing by value
    instead is what lets, say, a change of surface type leave the legend alone.
    """
    with reactive.isolate():
        if value() != new:
            value.set(new)


# ------------------------------------------------------------------------------
# Shared controls
# ------------------------------------------------------------------------------

def repo_links():
    """
    The repository control(s) at the right of the navbar.

    A plain wizard links to verywise-wizard. A fork links to its own repository
    and says where it came from, so visitors can find both.
    """
    def repo_icon(url, icon, label, size='26px'):
        return ui.a(icon_svg(icon, fill=styles.VWW_BLUE, width=size, height=size,
                             margin_left='0', margin_right='0.3em'),
                    label,
                    href=url, target='_blank', class_='vw-repo-link',
                    style=styles.REPO_LINK)

    if not CONFIG.is_fork:
        return ui.nav_control(
            repo_icon(UPSTREAM_REPO, 'github', ''))

    return ui.nav_control(
        ui.div(
            repo_icon(CONFIG.repo_url, 'github', ''),
            ui.a(icon_svg('code-fork', fill=styles.VWW_BLUE, width='11px',
                          height='11px', margin_left='0', margin_right='0.3em'),
                 f'forked from {UPSTREAM_NAME}',
                 href=UPSTREAM_REPO, target='_blank', class_='vw-fork-note',
                 style=styles.FORK_NOTE),
            style='display: flex; align-items: center'))


def nav_title(icon, label):
    """
    A navbar link: its icon, then its text.

    margin_left is pinned to 0 because faicons defaults it to 'auto', which
    would shove the icon to the far side of the link.
    """
    return ui.span(icon_svg(icon, margin_left='0', margin_right='0.5em'), label)


def selection_pane(*controls, col_widths=(3, 3, 3, 3)):
    # Never hand bslib more widths than there are controls, or it warns
    return ui.layout_columns(*controls, col_widths=col_widths[:len(controls)],
                             gap='20px', style=styles.SELECTION_PANE)


def roi_choice(id_):
    # 'unknown' is the medial wall, which has no boundary worth drawing
    regions = [r for r in region_names() if r != 'unknown']
    return ui.input_selectize(id=id_, label='ROI contours (optional)',
                              choices=regions, selected=None, multiple=True,
                              width='100%',
                              options={'plugins': ['remove_button'],
                                       'placeholder': 'No contours'})


def _toolbar_select(id_, label, choices, selected, icon):
    """
    A compact icon + dropdown for a card header.

    `tooltip=False` is not cosmetic: with the label hidden, shiny builds its own
    tooltip from the *already namespaced* id, then namespaces it again, and
    'result1-select_surface_tooltip' is not a valid id -- so the default blows up
    inside a module. A plain `title` gives the same hint without the detour.
    """
    return ui.toolbar_input_select(id=id_, label=label, choices=choices,
                                   selected=selected, icon=icon_svg(icon),
                                   show_label=False, tooltip=False, title=label)


def surface_choice(id_):
    return _toolbar_select(id_, 'Surface type', styles.SURFACE_NAMES,
                           selected='pial', icon='globe')


def resolution_choice(id_):
    # Low by default: the brains cross the websocket as one message, and
    # fsaverage6 makes that 10.5 MB against 2.6 MB for fsaverage5 -- four times
    # more to transfer and draw, for a mesh difference that is barely visible at
    # the size the card shows. Higher resolutions stay one click away.
    return _toolbar_select(id_, 'Resolution', styles.RESOLUTION_NAMES,
                           selected='fsaverage5', icon='microscope')


def button_column(*extra):
    """The GO button, and whatever else belongs in the column beside the pane."""
    return ui.div(
        ui.input_action_button(id='update_button', label='GO',
                               class_='btn btn-dark action-button',
                               width='100%'),
        *extra,
        style='padding-top: 15px')


# ------------------------------------------------------------------------------
# Shared layout rows
# ------------------------------------------------------------------------------

def info_row():
    """
    The line of text under the selection pane.

    A plain div, not ui.row: a bootstrap row is a flex container, so the text
    would only be as wide as itself and 'text-align: center' would have nothing
    to centre it in.
    """
    return ui.div(ui.output_ui('info'), style=styles.INFO_MESSAGE)


def brains_card(surface_id='select_surface', resolution_id='select_resolution'):
    """
    The brains card, with the two settings that only change how they are drawn
    sitting in its header instead of the selection pane.
    """
    return ui.card(
        ui.card_header('Brain surface maps',
                       ui.toolbar(surface_choice(surface_id),
                                  resolution_choice(resolution_id),
                                  align='right')),
        output_widget('brains'),
        full_screen=True)  # expand icon appears when hovering over the card body


def figures_row():
    """
    Both hemispheres live in one figure, so the brains card can be expanded on
    its own, while the legend stays put beside it.
    """
    return ui.layout_columns(
        brains_card(),
        ui.card(ui.card_header('Legend'),
                output_widget('legend')),
        col_widths=(8, 4))


# ------------------------------------------------------------------------------
# Shared figure outputs
# ------------------------------------------------------------------------------

def figure_outputs(figure_args, view_settings):
    """
    Register the `brains` and `legend` outputs, which are identical on every
    page: only where their arguments come from differs.

    `figure_args` is a reactive giving what to draw (see `display_args`), and
    `view_settings` one giving (surface, resolution, ROI contours). Called from
    inside a module's server function, so the outputs land in its namespace.
    """
    @render_plotly
    def brains():
        args = figure_args()
        surface, resolution, roi_names = req(view_settings())

        with ui.Progress(min=0, max=1) as p:
            p.set(0, message='Drawing the brains...')

            return fill_width(vwp.surf_figure(
                args['lh'], args['rh'], args['lh_mask'], args['rh_mask'],
                cmap=args['cmap'], discrete=args['discrete'],
                fs_template=resolution,
                surface=surface,
                roi_names=roi_names))

    @render_plotly
    def legend():
        args = figure_args()

        # Only one of stats (cluster means) and tick_text (named levels) is
        # ever set, and the panel mode in `args` decides which one is used.
        return fill_width(vwp.panel_figure(
            args['lh'], args['rh'], args['lh_mask'], args['rh_mask'],
            cmap=args['cmap'], discrete=args['discrete'],
            label=args['label'], mode=args['mode'],
            stats=args.get('stats'), tick_text=args.get('tick_text')))

    return brains, legend
