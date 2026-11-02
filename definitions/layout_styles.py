
PAGE_PADDING = 'padding-top: 50px; padding-right: 50px; padding-bottom: 50px; padding-left: 50px'
PAGE_GAP = '20px'

VW_COLOR_PALETTE = {'dark-blue': '#000055',
                    'dark-red': '#990033',
                    'light-grey': '#CCCCCC',
                    'light-blue': '#DCE3F0',
                    'mid-blue': '#C5D0E6',  # one step darker than light-blue
                    'deep-blue': '#33518C'  # dark, but still clearly blue
                    }

# The brand colours, central so the navbar, the logo and the plots agree
VWW_BLUE = '#001f60'
VWW_RED = '#95013a'
VWW_GREY = '#c7cfe2'
VWW_PINK = '#d4acb8'

# --- NAVBAR -------------------------------------------------------------------
# The logo sets the navbar's height, and a fixed-top navbar covers the top of
# the page, so NAVBAR_HEIGHT has to stay a little above LOGO_HEIGHT and the
# page's top padding has to clear it
LOGO_HEIGHT = '110px'
NAVBAR_HEIGHT = 72
PAGE_PADDING_TOP = NAVBAR_HEIGHT + 20

NAVBAR_CSS = f"""
/* Let the brand image, not bootstrap's own padding, set the height */
.navbar {{
    padding-top: 0; padding-bottom: 0;
    min-height: {NAVBAR_HEIGHT}px;
}}
.navbar .navbar-brand {{ padding-top: 4px; padding-bottom: 4px; }}

/* Bigger, in the brand blue, turning red on hover and where selected */
.navbar .nav-link {{
    font-size: 1.15rem;
    font-weight: 600;
    color: {VWW_BLUE};
    padding: 6px 14px;
}}
.navbar .nav-link:hover,
.navbar .nav-link:focus {{ color: {VWW_RED}; }}
.navbar .nav-link.active {{
    color: {VWW_RED};
    border-bottom: 3px solid {VWW_RED};
}}
"""

# Corners close to the cards' own, so the pane and the cards below it match
SELECTION_PANE = f'padding-top: 10px; padding-right: 20px; padding-left: 20px; ' \
                 f'padding-bottom: 20px; ' \
                 f'border-radius: 10px; ' \
                 f'background-color: {VW_COLOR_PALETTE["light-blue"]}'

# On the compare page the two maps each get a band of their own, so their
# dropdowns do not need to repeat which map they belong to
# A flex row, not a grid: that is what lets the letter take a fixed sliver of
# space (see MAP_BADGE) instead of a whole twelfth of the band, and centres it
# against the dropdowns beside it
MAP_ROW =  f'display: flex; align-items: center; ' \
           f'padding-top: 10px; padding-right: 10px; padding-left: 0px; ' \
           f'padding-bottom: 0px; ' \
           f'border-radius: 10px; ' \
           f'background-color: {VW_COLOR_PALETTE["mid-blue"]}'

INFO_MESSAGE = 'text-align: center; padding-top: 10px; padding-bottom: 10px'

# The download buttons sit in a narrow column, where bootstrap would wrap the
# icon and the label onto two lines: nowrap keeps them on one, and the flexbox
# centres the pair instead of leaving them against the left edge.
DOWNLOAD_BUTTON = 'margin-top: 10px; white-space: nowrap; ' \
                  'padding-left: 8px; padding-right: 8px; ' \
                  'display: flex; align-items: center; justify-content: center; ' \
                  'gap: 6px'



# 'flex: 0 0 <width>' is the only number to change to give the letter more or
# less room; MAP_ROW centres it vertically, so it reads against the band rather
# than against the dropdowns, which carry a label above them
MAP_BADGE = f'flex: 0 0 46px; ' \
            f'display: flex; align-items: center; justify-content: center; ' \
            f'font-size: 1.8rem; font-weight: bold; ' \
            f'color: {VW_COLOR_PALETTE["deep-blue"]}'

measure_names = {'thickness': 'Thickness',
                 'area': 'Surface area',
                 'area.pial': 'Surface area (pial)',
                 'curv': 'Curvature',
                 'jacobian_white': 'Jacobian determinant (white)',
                 'pial_lgi': 'Local gyrification index (pial)',
                 'sulc': 'Sulcal depth',
                 'volume': 'Gray matter volume',
                 'w_g.pct': 'White/gray matter contrast',
                 'white.H': 'Mean curvature (white)',
                 'white.K': 'Gaussian curvature (white)'}

measure_colors = {'thickness': '#FFCCCC',
                 'area': '#FFFFCC',
                 'area.pial': '#FFFFCC',
                 'curv': '#d8f3dc',
                 'jacobian_white': '#fff0f3',
                 'pial_lgi': '#fae0e4',
                 'sulc': '#fff0f3',
                 'volume': '#d9d9d9',
                 'w_g.pct': '#edf2fb',
                 'white.H': '#d8f3dc',
                 'white.K': '#d8f3dc'}

# ------ PLOTTING ------------
CLUSTER_COLORMAP = 'turbo'

# Surface and resolution names follow nilearn, not FreeSurfer.
# This is deliberately a subset of plotting.SURFACES: the engine also knows
# 'white_matter' and 'sphere', they are just not offered in the app.
SURFACE_NAMES = {'pial': 'Pial',
                 'inflated': 'Inflated',
                 'flat': 'Flat'}

# Listed cheapest first, since Low is the default
RESOLUTION_NAMES = {'fsaverage5': 'Low (10k nodes)',
                    'fsaverage6': 'Medium (41k nodes)',
                    'fsaverage': 'High (164k nodes)'}

OUTPUT_NAMES = {'betas': 'Beta values', 'clusters': 'Clusters'}

COMPARE_MODES = {'difference': 'Difference (A − B)',
                 'overlap': 'Cluster overlap'}

# Labels for the three overlap codes, in place of the bare level numbers
OVERLAP_TICK_LABELS = ['A only', 'B only', 'Both']

DOWNLOAD_FORMATS = {'png': 'PNG', 'html': 'HTML'}

BETA_LABEL = 'Observed β values'

# One colour per overlap code: 1 = first map only, 2 = second map only, 3 = both
OVLP_COLORS = ['#333399',                     # blue
               '#FFCC33',                     # yellow
               VW_COLOR_PALETTE['dark-red']]  # dark red



