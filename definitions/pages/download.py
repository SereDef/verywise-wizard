"""
Handing a rendered figure to the browser.

The download happens in two steps: the visible button starts a background
render, and once the bytes exist the server tells the client to follow the
(hidden) download link, which then returns instantly. Without this the browser
would request the file first and sit on an idle connection for the whole
render, which a hosting proxy cuts short -- leaving an empty file.

The UI piece and the server piece are both here, so a page gains downloads by
calling `download_buttons()` and `wire_download()`.
"""
import asyncio
import os
import tempfile

from faicons import icon_svg
from shiny import reactive, render, req, ui
from shiny.module import resolve_id

import definitions.layout_styles as styles
from definitions import plotting as vwp
from definitions.plotting.kaleido_patch import png_export_ready


def _png_download_allowed():
    """
    Whether to offer the PNG download at all.

    The figure is rendered *before* the browser asks for it (see
    `render_download` below), so a slow render no longer stalls the download
    response and PNG is deliverable wherever the app runs, deployment included.

    This stays as a safety valve rather than a guess about the environment:
    set VWWIZARD_ALLOW_PNG=0 to hide the PNG option if a host turns out not to
    manage it.
    """
    override = os.environ.get('VWWIZARD_ALLOW_PNG')

    if override is None:
        return True

    return override.strip().lower() not in ('0', 'false', 'no', '')


PNG_DOWNLOAD_ALLOWED = _png_download_allowed()

print(f'[verywise-wizard] PNG download '
      f'{"enabled" if PNG_DOWNLOAD_ALLOWED else "disabled (HTML only)"}', flush=True)


DOWNLOAD_TRIGGER_JS = ui.tags.script("""
(function () {
    function register() {
        // Shiny may not be defined yet when this tag is parsed
        if (typeof Shiny === "undefined" || !Shiny.addCustomMessageHandler) {
            setTimeout(register, 50);
            return;
        }
        Shiny.addCustomMessageHandler("vw_download", function (msg) {
            var link = document.getElementById(msg.id);
            if (!link) {
                console.error("[verywise-wizard] no download link " + msg.id);
                return;
            }
            var href = link.getAttribute("href");
            if (!href) {
                console.error("[verywise-wizard] download link has no href yet");
                return;
            }
            // Navigate rather than click: a programmatic click on a
            // target="_blank" link can be swallowed by the popup blocker
            window.location.href = href;
        });
    }
    register();
})();
""")


def render_download_bytes(which_format, args, surface, resolution, roi_names,
                          title):
    """
    Render the figure and return its bytes.

    Blocking and free of reactive reads, so it can be handed to a worker thread
    by the extended task that drives the download.
    """
    shared = dict(
        lh=args['lh'], rh=args['rh'],
        lh_mask=args['lh_mask'], rh_mask=args['rh_mask'],
        cmap=args['cmap'], discrete=args['discrete'],
        fs_template=resolution, surface=surface, roi_names=roi_names,
        colorbar_label=args['label'], mode=args['mode'], stats=args.get('stats'),
        # Only the compare page's overlap sets this: without it the downloaded
        # colorbar would read 1/2/3 where the screen reads A only / B only / Both
        tick_text=args.get('tick_text'),
        title=title)

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = os.path.join(tmp_dir, f'figure.{which_format}')

        # No views are passed, so each format keeps its own default: the PNG
        # gets the full six-view figure, the HTML the lateral view on screen.
        if which_format == 'png':
            vwp.surf_png(output_file=out_file, **shared)
        else:
            vwp.surf_html(output_html=out_file, **shared)

        with open(out_file, 'rb') as f:
            return f.read()


def download_buttons():
    """
    One button per format, plus the hidden link they end up following. Where
    PNG is switched off that button is left out entirely, rather than offered
    and failed.

    Both visible buttons are ordinary action buttons: they only start a render.
    """
    return (
        ui.input_action_button(id='download_png', label='PNG',
                               icon=icon_svg('download'), width='100%',
                               style=styles.DOWNLOAD_BUTTON)
        if PNG_DOWNLOAD_ALLOWED else None,
        ui.input_action_button(id='download_html', label='HTML',
                               icon=icon_svg('download'), width='100%',
                               style=styles.DOWNLOAD_BUTTON),
        ui.div(ui.download_button(id='download_figure_button', label='hidden'),
               style='display: none;'),
    )


def wire_download(input, output, session, figure_args, view_settings,
                  figure_title):
    """
    Make the buttons from `download_buttons()` work.

    Takes the same reactives the figures are drawn from, so what is downloaded
    is always what is on screen. Called from inside a module's server function,
    so the outputs and inputs land in its namespace.
    """

    def resolve_download_format(wanted):
        """
        Which format can actually be delivered, given which button was pressed.

        PNG export needs a browser kaleido can drive, which a deployed
        container does not have and pip cannot install. Settling this *before*
        rendering means the PNG button can fall back to HTML instead of handing
        over an empty .png.
        """
        if wanted != 'png' or not PNG_DOWNLOAD_ALLOWED:
            return 'html'

        with ui.Progress(min=0, max=1) as p:
            p.set(0, message='Preparing the image renderer...',
                  detail='The first PNG may need to download a headless '
                         'browser (about 150 MB). Later ones are quick.')

            ready = png_export_ready()

        if not ready:
            ui.notification_show(
                'PNG export needs a headless browser, which could not be '
                'started or downloaded on this server. Sending an interactive '
                'HTML figure instead.',
                type='warning', duration=15)
            return 'html'

        return 'png'

    # --- Render first, hand over second -----------------------------------
    # The click starts a background render; when it finishes the client is told
    # to follow the hidden download link, which then has bytes waiting. Nothing
    # ever waits on an idle HTTP connection, so the render can take as long as
    # it likes.

    rendered_download = reactive.Value(None)  # (format, bytes) once ready

    notice_id = str(resolve_id('download_notice'))
    link_id = str(resolve_id('download_figure_button'))

    @reactive.extended_task
    async def render_download(which_format, args, surface, resolution, roi_names,
                              title):
        """Render off the main thread, so the session stays responsive."""
        return which_format, await asyncio.to_thread(
            render_download_bytes, which_format, args, surface, resolution,
            roi_names, title)

    def start_download_render(wanted):
        """Shared by the two download buttons; they differ only in `wanted`."""
        args = figure_args()
        surface, resolution, roi_names = req(view_settings())

        # Falls back to HTML where PNG cannot be rendered; the notification
        # about that comes from resolve_download_format itself.
        which_format = resolve_download_format(wanted)

        ui.notification_show(
            f'Rendering the {which_format.upper()} figure... the download '
            'starts on its own when it is ready.',
            id=notice_id, duration=None, type='message')

        render_download.invoke(which_format, args, surface, resolution,
                               roi_names, figure_title())

    @reactive.Effect
    @reactive.event(input.download_png)
    def start_png_download():
        start_download_render('png')

    @reactive.Effect
    @reactive.event(input.download_html)
    def start_html_download():
        start_download_render('html')

    @reactive.Effect
    async def deliver_download():
        """Hand the finished render to the browser."""
        status = render_download.status()

        if status == 'error':
            ui.notification_remove(notice_id)
            ui.notification_show(
                'Could not render the figure. Try the other format, or a '
                'lower resolution.', type='error', duration=15)
            return

        if status != 'success':
            return  # not started, still running, or cancelled

        rendered_download.set(render_download.result())

        ui.notification_remove(notice_id)
        await session.send_custom_message('vw_download', {'id': link_id})

    @reactive.Effect
    def discard_stale_download():
        """Anything already rendered no longer matches the current settings."""
        figure_args()
        view_settings()

        rendered_download.set(None)

    def delivered_format():
        """
        The extension follows the bytes that were actually rendered, so a PNG
        that had to fall back cannot arrive named '.png'.
        """
        with reactive.isolate():
            ready = rendered_download()

        return ready[0] if ready else 'html'

    # suspend_when_hidden=False is essential here: this link lives inside a
    # display:none wrapper, and Shiny suspends hidden outputs. Suspended, its
    # value -- the download URL -- never renders, so the href stays empty and
    # the client has nothing to follow when told the figure is ready.
    @output(suspend_when_hidden=False)
    @render.download_button(
        filename=lambda: f'verywise_figure.{delivered_format()}')
    def download_figure_button():
        ready = rendered_download()

        # Only ever reached once the render has finished, so this returns at
        # once instead of holding the response open.
        req(ready is not None)

        yield ready[1]
