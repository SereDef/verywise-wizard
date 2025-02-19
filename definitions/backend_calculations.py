import os
import numpy as np
import pandas as pd
import warnings

from nilearn import datasets
import nibabel as nb

import matplotlib as mpl
from matplotlib.colors import ListedColormap

import definitions.layout_styles as styles

# ===== DATA PROCESSING FUNCTIONS ==============================================================

# def check_results_directory(input_path):


def detect_models(resdir):
    # Make sure path is correctly specified
    resdir = f'{resdir}/' if resdir[-1] != '/' else resdir

    # List all results
    top_level = [f for f in os.listdir(resdir) if not f.startswith('.')]
    all_results = dict()
    for p in sorted(top_level):
        subdir_list = [f for f in os.listdir(f'{resdir}/{p}') if not f.startswith('.')]
        # in each directory in results, subdirectories have structure "hemi.model_name.measure"
        all_results[p] = pd.DataFrame([d.split('.') for d in sorted(subdir_list)],
                                      columns=['hemi', 'model', 'meas'])

    return all_results


def detect_terms(resdir, which_model, which_meas):

    all_results = detect_models(resdir)

    group, model = which_model.split('/')

    check_df = all_results[group]
    check_df = check_df[check_df.model == model]

    check_hemis = check_df['hemi'].unique()

    # Assume you have left and right hemispheres are always run and with the same model
    mdir = f'{resdir}/{group}/{check_hemis[0]}.{model}.{which_meas}'
    stacks = pd.read_table(f'{mdir}/stack_names.txt', delimiter="\t")

    out_terms = dict(zip(list(stacks.stack_number)[1:], list(stacks.stack_name)[1:]))

    return out_terms


def extract_results(resdir, which_model, which_term, which_meas):

    group, model = which_model.split('/')

    min_beta = []
    max_beta = []
    med_beta = []
    n_clusters = []

    sign_clusters_left_right = {}
    sign_betas_left_right = {}
    all_observed_betas_left_right = {}

    for hemi in ['left', 'right']:

        mdir = f'{resdir}/{group}/{hemi[0]}h.{model}.{which_meas}'

        # Read significant cluster map
        ocn = nb.load(f'{mdir}/stack{which_term}.cache.th30.abs.sig.ocn.mgh')
        sign_clusters = np.array(ocn.dataobj).flatten()

        # Read the full beta map
        coef = nb.load(f'{mdir}/stack{which_term}.coef.mgh')

        if not np.any(sign_clusters):  # all zeros = no significant clusters
            betas = np.empty(sign_clusters.shape)
            betas.fill(np.nan)
            n_clusters.append(0)
        else:
            # Read beta map
            betas = np.array(coef.dataobj).flatten()

            # Set non-significant betas to NA
            mask = np.where(sign_clusters == 0)[0]
            betas[mask] = np.nan

            n_clusters.append(np.max(sign_clusters))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            min_beta.append(np.nanmin(betas))
            max_beta.append(np.nanmax(betas))
            med_beta.append(np.nanmean(betas))

        sign_clusters_left_right[hemi] = sign_clusters
        sign_betas_left_right[hemi] = betas
        all_observed_betas_left_right[hemi] = np.array(coef.dataobj).flatten()

    return np.nanmin(min_beta), np.nanmax(max_beta), np.nanmean(med_beta), n_clusters, \
           sign_clusters_left_right, sign_betas_left_right, all_observed_betas_left_right

# ----------------------------------------------------------------------------------------------------------------------


def calc_betainfo_bycluster(sign_clusters, sign_betas):
    beta_by_clust = pd.DataFrame(columns=['hemi', 'size', 'mean', 'min', 'max'])

    for hemi in ['left', 'right']:

        cst = sign_clusters[
            hemi].byteswap().newbyteorder()  # ensure that data aligns with the Sys architecture (avoid big-endian)

        if np.all(cst == 0):
            continue

        bts = sign_betas[hemi].byteswap().newbyteorder()

        # Create a DataFrame from the arrays and filter only significant values
        df = pd.DataFrame({'cluster': cst, 'beta': bts})
        df = df[df['cluster'] > 0]

        # Group by cluster and calculate mean and range for beta
        hemi_beta_by_clust = df.groupby('cluster')['beta'].agg(
            ['count', 'mean', 'min', 'max'])  # lambda x: x.max() - x.min()])
        hemi_beta_by_clust.columns = ['size', 'mean', 'min', 'max']
        hemi_beta_by_clust.insert(0, 'hemi', hemi)

        beta_by_clust = pd.concat([beta_by_clust, pd.Series([np.nan]), hemi_beta_by_clust])

    beta_by_clust = beta_by_clust.reset_index()

    beta_by_clust.insert(0, 'cluster', ['' if x == 0 else f'Cluster {int(x)}' for x in beta_by_clust['index']])

    return beta_by_clust.drop(['index', 0], axis=1)

# ----------------------------------------------------------------------------------------------------------------------


def compute_overlap(resdir, model1, term1, measure1, model2, term2, measure2):

    sign_clusters1 = extract_results(resdir, model1, term1, measure1)[4]
    sign_clusters2 = extract_results(resdir, model2, term2, measure2)[4]

    ovlp_maps = {}
    ovlp_info = {}

    for hemi in ['left', 'right']:
        sign1, sign2 = sign_clusters1[hemi], sign_clusters2[hemi]

        sign1[sign1 > 0] = 1
        sign2[sign2 > 0] = 2

        # Create maps
        ovlp_maps[hemi] = np.sum([sign1, sign2], axis=0)

        # Extract info
        uniques, counts = np.unique(ovlp_maps[hemi], return_counts=True)
        ovlp_info[hemi] = dict(zip(uniques, counts))
        ovlp_info[hemi].pop(0)  # only significant clusters

    # Merge left and right info
    info = {k: [ovlp_info['left'].get(k, 0) + ovlp_info['right'].get(k, 0)] for k in
            set(ovlp_info['left']) | set(ovlp_info['right'])}
    percent = [round(i[0] / sum(sum(info.values(), [])) * 100, 1) for i in info.values()]

    for i, k in enumerate(info.keys()):
        info[k].append(percent[i])

    return info, ovlp_maps


# ===== PLOTTING FUNCTIONS ===================================================================

def fetch_surface(resolution):
    # Size / number of nodes per map
    n_nodes = {'fsaverage': 163842,
               'fsaverage6': 40962,
               'fsaverage5': 10242}

    return datasets.fetch_surf_fsaverage(mesh=resolution), n_nodes[resolution]


def fetch_discr_colormap(hemi, n_clusters, tot_clusters):

    mpl_cmap = styles.CLUSTER_COLORMAP

    cmap0 = mpl.colormaps[mpl_cmap]

    if tot_clusters > 1:
        clustcolors = cmap0(np.linspace(0, 1, tot_clusters))
    else:
        clustcolors = cmap0(np.linspace(0, 1, 10))

    if n_clusters > 1:
        if hemi == 'left':
            cmap = ListedColormap(clustcolors[:n_clusters])
        else:
            cmap = ListedColormap(clustcolors[-n_clusters:])

    else:
        if hemi == 'left':
            cmap = ListedColormap(clustcolors)
        else:
            cmap0_rev = mpl.colormaps[f'{mpl_cmap}_r']
            clustcolors = cmap0_rev(np.linspace(0, 1, 10))
            cmap = ListedColormap(clustcolors)

    # cmap = ListedColormap(whole_cmap[:n_clusters]) if n_clusters > 0 else None

    return cmap