import numpy as np

from nilearn import plotting

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.transforms as transforms
from matplotlib.colors import ListedColormap

from scipy.stats import gaussian_kde

from definitions.backend_calculations import detect_models, extract_results, calc_betainfo_bycluster, fetch_surface


# ===== BETA AND CLUSTER LEGENDS FOR APP ==============================================================


def plot_beta_colorbar_density(ax1, ax2, sign_betas, all_betas, colorblind=False, set_range=None):

    obs_betas = np.concatenate((all_betas['left'], all_betas['right']), axis=None)
    min_obs_beta = np.nanmin(obs_betas)
    max_obs_beta = np.nanmax(obs_betas)
    obs_betas = obs_betas[obs_betas != 0.00000]  # TMP: clean out all values exactly equal to 0

    sign_betas = np.concatenate((sign_betas['left'], sign_betas['right']), axis=None)

    if all(np.isnan(sign_betas)):
        ax1.axis('off')
        ax2.axis('off')
        return None

    min_sign_beta = np.nanmin(sign_betas)
    max_sign_beta = np.nanmax(sign_betas)

    lspace = np.linspace(min_obs_beta, max_obs_beta, 200)
    color_where = (lspace > min_sign_beta) & (lspace < max_sign_beta)

    blank_middle = False

    if max_sign_beta < 0 and min_sign_beta < 0:  # all negative associations
        cmap = 'viridis'
    elif max_sign_beta > 0 and min_sign_beta > 0:  # all positive associations
        cmap = 'viridis_r' if colorblind else 'hot_r'
    else:
        cmap = 'viridis' # TODO: could pick a diverging map for this one instead (rare though)
        blank_middle = True
        thresh = np.nanmin(abs(sign_betas))
        color_where = (lspace > thresh) | (lspace < -thresh)

    # PLOT 1: COLORBAR -------------------------------------------------------------------------------

    cb1 = mpl.colorbar.ColorbarBase(ax1,
                                    cmap=mpl.colormaps[cmap],
                                    norm=mpl.colors.Normalize(vmin=min_sign_beta, vmax=max_sign_beta),
                                    orientation='vertical', ticklocation='left')

    # Adjust colorbar margins, ticks and label
    # ticks = list(np.arange(margins[0], margins[1], tickstep))
    # tickform = '{:.1e}' if tickstep < 0.01 else '{:.2f}'
    # cb1.set_ticks(ticks, labels=[tickform.format(i) if i != 0 else '0.00' for i in ticks], fontsize=12)
    cb1.set_label(r'Observed $\beta$ values', fontsize=10, labelpad=5)

    # Include central threshold for maps with both positive and negative values
    if blank_middle:
        ax1.axhspan(-thresh, thresh, facecolor='white', alpha=0.99)

    if set_range == None:
        pad = abs(max_obs_beta - min_obs_beta) * 0.01  # use 1% of total range for upper and lower bounds
        ax1.set_ylim(min_obs_beta - pad, max_obs_beta + pad)
    else:
        ax1.set_ylim(set_range[0], set_range[1])

    # PLOT 2: HISTOGRAM -------------------------------------------------------------------------------
    density = gaussian_kde(obs_betas)

    # Density line
    ax2.plot(density(lspace), lspace, lw=0.5, alpha=0.3, color='k')

    # Color significant portion
    polygon = ax2.fill_betweenx(y=lspace, x1=density(lspace), where=color_where, lw=0, color='none')
    verts = np.vstack([p.vertices for p in polygon.get_paths()])

    gradient = ax2.imshow(np.linspace(0, 1, 256).reshape(-1, 1),
                          cmap=cmap, aspect='auto',
                          extent=[verts[:, 0].max(), verts[:, 0].min(), verts[:, 1].max(), verts[:, 1].min()])
    gradient.set_clip_path(polygon.get_paths()[0], transform=ax2.transData)

    ax2.axhline(y=0, dashes=(20, 5), lw=0.2, alpha=0.3, color='k')

    if set_range == None:
        ax2.set_ylim(min_obs_beta - pad, max_obs_beta + pad)
    else:
        ax2.set_ylim(set_range[0], set_range[1])

    ax2.set_xlim(0, np.nanmax(density(lspace)))

    ax2.axis('off')


def beta_colorbar_density_figure(sign_betas, all_betas, figsize=(4, 6),
                                 colorblind=False, set_range=None):

    # Figure set up
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize, width_ratios=[1, 5])

    plot_beta_colorbar_density(ax1, ax2, sign_betas, all_betas, colorblind=colorblind, set_range=set_range)

    return fig


def plot_clusterwise_means(fig, ax, df, cmap, tot_clusters):

    df['lower_error'] = df['mean'] - df['min']
    df['upper_error'] = df['max'] - df['mean']

    # Sample colormap
    cmap0 = mpl.colormaps[cmap]

    if tot_clusters > 1:
        cmap_discr = ListedColormap(cmap0(np.linspace(0, 1, tot_clusters)))
    else:
        cmap_discr = ListedColormap(cmap0(np.linspace(0, 1, 10)))

    # Plot each line with its corresponding color and error bars
    for n, i in enumerate(df.dropna().index):
        ax.errorbar(y=i,  # Position on the y-axis
                    x=df['mean'][i],  # Mean value
                    xerr=[[df['lower_error'][i]], [df['upper_error'][i]]],  # Error bars
                    fmt='d',  # Marker style
                    ms=8,  # marker size
                    color=cmap_discr.colors[n],  # Line color
                    ecolor=cmap_discr.colors[n],  # Error bar color
                    capsize=8)  # Error bar cap size
    # Add 0 reference
    ax.axvline(x=0, dashes=(40, 10), lw=0.2, alpha=0.3, color='k')

    # Adjast x- and y-axis
    ax.set_yticks(range(len(df)))
    ax.tick_params('y', length=0.0)  # do not draw y-asis ticks
    ax.set_yticklabels([f'{c} (size = {int(n)})' if c != '' else '' for c, n in zip(df['cluster'], df['size'])],
                       fontsize=10)
    ax.invert_yaxis()

    ax.set_xlabel(r'Mean $\beta$ value', fontsize=10, fontweight='bold', labelpad=15)
    ax.tick_params('x', length=5, labelsize=10)

    for pos in ['right', 'left', 'top']: ax.spines[pos].set_visible(False)

    # Add hemisphere legend
    hemi_text = dict(x=0.01, fontsize=11, fontweight='bold', va='center', ha='left',
                     transform=transforms.blended_transform_factory(fig.transFigure, ax.transData))

    vcs = df['hemi'].value_counts()
    if all(h in list(vcs.keys()) for h in ['left', 'right']):

        hemi_label_ys = [y + 0.2 for y in [0, vcs['left'] + 1]]

        ax.text(y=hemi_label_ys[0], s='Left hemisphere', **hemi_text)
        ax.text(y=hemi_label_ys[1], s='Right hemisphere', **hemi_text)
    else:

        hemi_label_y = 0

        if 'left' in list(vcs.keys()):
            ax.text(y=hemi_label_y, s='Left hemisphere', **hemi_text)
        elif 'right' in list(vcs.keys()):
            ax.text(y=hemi_label_y, s='Right hemisphere', **hemi_text)


def clusterwise_means_figure(sign_clusters, sign_betas,
                             cmap, tot_clusters, figsize=(4, 6)):

    betas_by_cluster = calc_betainfo_bycluster(sign_clusters, sign_betas)

    # Figure set up
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    plot_clusterwise_means(fig, ax, betas_by_cluster, cmap=cmap, tot_clusters=tot_clusters)

    return fig

# ===== STATIC BRAIN PLOTS ==============================================================


def plot_single_brain(ax, hemi, coord, fig, sign_betas, surf='pial', resol='fsaverage5', colorblind=False):

    fs_avg, n_nodes = fetch_surface(resol)

    stats_map = sign_betas[hemi]  # sign_betas
    bg_color = fs_avg[f'sulc_{hemi}']

    bg_darkness = 0.3 if np.isnan(stats_map).all() else 0.6

    min_sign_beta = np.nanmin(stats_map)
    max_sign_beta = np.nanmax(stats_map)

    if max_sign_beta < 0 and min_sign_beta < 0:  # all negative associations
        cmap = 'viridis'
    elif max_sign_beta > 0 and min_sign_beta > 0:  # all positive associations
        cmap = 'viridis_r' if colorblind else 'hot_r'
    else:
        cmap = 'viridis' # TODO: could pick a diverging map for this one instead (rare though)


    p = plotting.plot_surf(surf_mesh=fs_avg[f'{surf}_{hemi}'],  # Surface mesh geometry
                           surf_map=stats_map[:n_nodes],  # Statistical map confounder model
                           bg_map=bg_color,
                           # alpha=0.01,
                           darkness=bg_darkness,  # of the bg_map
                           hemi=hemi,
                           view=coord,
                           cmap=cmap,
                           symmetric_cmap=False,
                           axes=ax,
                           figure=fig,
                           colorbar=False)
    return p


def plot_brain_2d(start_folder, outc, model, meas, resol='fsaverage5', title=None):

    title = f'{model} ({meas})' if title == None else title

    print("Computing figure")

    _, _, _, _, _, sign_betas, all_observed_betas = extract_results(start_folder, outc, model, meas)

    fig, axs = plt.subplot_mosaic('ABCDD..a.b;EFG.HH.a.b', figsize=(12, 7),
                                  per_subplot_kw={('ABCDEFGH'): {'projection': '3d'}},
                                  gridspec_kw=dict(wspace=0, hspace=0, width_ratios=[0.19, 0.19, 0.19, 0.02, 0.17,
                                                                                     0.02, 0.08, 0.03, 0.01, 0.1]))

    kargs = dict(sign_betas=sign_betas, fig=fig, surf='pial', resol=resol)
    tkargs = dict(ha='center', va='center', style='italic', fontsize=10)

    plot_single_brain(axs['A'], 'left', 'lateral', **kargs)
    plot_single_brain(axs['B'], 'right', 'lateral', **kargs)

    plot_single_brain(axs['C'], 'left', 'dorsal', **kargs)
    plot_single_brain(axs['C'], 'right', 'dorsal', **kargs)

    plot_single_brain(axs['D'], 'left', 'posterior', **kargs)
    plot_single_brain(axs['D'], 'right', 'posterior', **kargs)

    plot_single_brain(axs['E'], 'left', 'medial', **kargs)
    plot_single_brain(axs['F'], 'right', 'medial', **kargs)

    plot_single_brain(axs['G'], 'left', 'ventral', **kargs)
    plot_single_brain(axs['G'], 'right', 'ventral', **kargs)

    plot_single_brain(axs['H'], 'left', 'anterior', **kargs)
    plot_single_brain(axs['H'], 'right', 'anterior', **kargs)

    axs['A'].set_ylim3d(-88, 90)
    axs['B'].set_ylim3d(-88, 90)

    axs['E'].set_ylim3d(-128, 50)
    axs['F'].set_ylim3d(-128, 50)

    plot_beta_colorbar_density(axs['a'], axs['b'], sign_betas, all_observed_betas)

    # axs['C'].set_ylim3d(-118, 60); # axs['C'].set_zlim3d(-118, 60)

    # fig.patch.set_facecolor('xkcd:mint green')
    fig.suptitle(title, fontsize=14, fontweight='bold', y=.90)

    y_top, y_bot = 0.54, 0.15
    x_1, x_2, x_3 = 0.275, 0.50, 0.65

    tkargs = dict(ha='center', va='center', style='italic', fontsize=10)

    fig.text(x_1, y_top, "Lateral\nview", tkargs)
    fig.text(x_2, y_top, "Dorsal\nview", tkargs)
    fig.text(x_3, y_top, "Posterior\nview", tkargs)

    fig.text(x_1, y_bot, "Medial\nview", tkargs)
    fig.text(x_2, y_bot, "Ventral\nview", tkargs)
    fig.text(x_3, y_bot, "Anterior\nview", tkargs)

    lkargs = dict(ha='center', va='center', style='italic', fontsize=12, color='grey')

    y_top, y_bot = y_top + 0.23, y_bot + 0.23
    x_1a, x_1b = x_1 - 0.11, x_1 + 0.11
    x_2a = x_2b = x_2 - 0.06
    x_3a, x_3b = x_3 - 0.045, x_3 + 0.045

    fig.text(x_1a, y_top, "L", lkargs);
    fig.text(x_1b, y_top, "R", lkargs)
    fig.text(x_1a, y_bot, "L", lkargs);
    fig.text(x_1b, y_bot, "R", lkargs)

    fig.text(x_2a, y_top, "L", lkargs);
    fig.text(x_2b, y_top - 0.18, "R", lkargs)
    fig.text(x_2a, y_bot, "L", lkargs);
    fig.text(x_2b, y_bot - 0.18, "R", lkargs)

    fig.text(x_3a, y_top, "L", lkargs);
    fig.text(x_3b, y_top, "R", lkargs)
    fig.text(x_3a, y_bot, "R", lkargs);
    fig.text(x_3b, y_bot, "L", lkargs)

    return fig
