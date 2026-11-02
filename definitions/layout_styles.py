
PAGE_PADDING = 'padding-top: 50px; padding-right: 50px; padding-bottom: 50px; padding-left: 50px'
PAGE_GAP = '20px'

VW_COLOR_PALETTE = {'dark-blue': '#000055',
                    'dark-red': '#990033',
                    'light-grey': '#CCCCCC',
                    'light-blue': '#DCE3F0'
                    }

SELECTION_PANE = f'padding-top: 10px; padding-right: 20px; padding-left: 20px; ' \
                 f'border-radius: 35px; ' \
                 f'background-color: {VW_COLOR_PALETTE["light-blue"]}'

INFO_MESSAGE = 'text-align: center; padding-top: 10px; padding-bottom: 10px'

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
BETA_COLORMAP = 'viridis'
CLUSTER_COLORMAP = 'turbo'

# Surface and resolution names follow nilearn, not FreeSurfer.
# This is deliberately a subset of plotting.SURFACES: the engine also knows
# 'white_matter' and 'sphere', they are just not offered in the app.
SURFACE_NAMES = {'pial': 'Pial',
                 'inflated': 'Inflated',
                 'flat': 'Flat'}

RESOLUTION_NAMES = {'fsaverage': 'High (164k nodes)',
                    'fsaverage6': 'Medium (41k nodes)',
                    'fsaverage5': 'Low (10k nodes)'}

OUTPUT_NAMES = {'betas': 'Beta values', 'clusters': 'Clusters'}

DOWNLOAD_FORMATS = {'png': 'PNG', 'html': 'HTML'}

BETA_LABEL = 'Observed β values'

OVLP_COLOR1 = '#333399'  # blue
OVLP_COLOR2 = '#FFCC33'  # yellow
OVLP_COLOR3 = VW_COLOR_PALETTE['dark-red']  # '#CC6677'  # light red

OVLP_COLORS = [OVLP_COLOR1, OVLP_COLOR2, OVLP_COLOR3]



