import os
import re
import numpy as np
import pandas as pd
import warnings

from nilearn import datasets
import nibabel as nb

import matplotlib as mpl
from matplotlib.colors import ListedColormap

from shiny import ui

import definitions.layout_styles as styles

# ===== DATA PROCESSING FUNCTIONS ==============================================================

def resolve_resdir(resdir):

    if os.path.isdir(resdir):
        return resdir
    
    # GitHub folder URL
    if re.match(r"https://github.com/.+/.+/tree/.+/.+", resdir):

        return download_github_folder(resdir)
    
    # (Handle other cases: zip, repo, etc.)
    raise ValueError("Unsupported path format")

def download_github_folder(github_url, github_token=None, GITHUB_FOLDER_CACHE = {}):
    """
    Downloads a folder from a public GitHub repo to a temp directory.
    github_url: e.g. https://github.com/user/repo/tree/main/path/to/folder
    Returns the local path to the downloaded folder.
    """
    import tempfile
    import requests

    # Check cache first
    if github_url in GITHUB_FOLDER_CACHE:
        return GITHUB_FOLDER_CACHE[github_url]
    
    m = re.match(r"https://github.com/([^/]+)/([^/]+)/tree/([^/]+)/(.*)", github_url)
    if not m:
        raise ValueError("URL must be of the form https://github.com/user/repo/tree/branch/path/to/folder")
    user, repo, branch, folder_path = m.groups()

    api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{folder_path}?ref={branch}"
    tmp_dir = tempfile.mkdtemp()
    folder_local = os.path.join(tmp_dir, os.path.basename(folder_path))
    os.makedirs(folder_local, exist_ok=True)

    headers = {}
    # Try to get token from environment if not provided
    if github_token is None:
        github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    def download_contents(api_url, local_dir, print_progress=True):
        resp = requests.get(api_url, headers=headers)
        resp.raise_for_status()
        element_count = len(resp.json())
        with ui.Progress(min=0, max=element_count) as p:
            for e, file_info in enumerate(resp.json()):

                if print_progress: 
                    p.set(value=e + 1, message=f"Downloading [{e + 1}/{element_count}]: {file_info['name']}...")
                else: 
                    p.set(value=e + 1, message=f"[{e + 1}/{element_count}]: {file_info['name']}...")

                if file_info["type"] == "dir":
                    subfolder_local = os.path.join(local_dir, file_info["name"])
                    os.makedirs(subfolder_local, exist_ok=True)
                    download_contents(file_info["url"], subfolder_local, print_progress=False)

                elif file_info["type"] == "file":
                    file_resp = requests.get(file_info["download_url"])
                    file_resp.raise_for_status()
                    with open(os.path.join(local_dir, file_info["name"]), "wb") as f:
                        f.write(file_resp.content)
                

    download_contents(api_url, folder_local)

    # Store in cache
    GITHUB_FOLDER_CACHE[github_url] = folder_local

    return folder_local


def detect_models(resdir, results_format):

    resdir = resolve_resdir(resdir)

    # List all results
    all_results = {'results_directory': resdir, 
                   'results_format': results_format,
                   'results': {}}

    top_level = [f for f in os.listdir(resdir) if not f.startswith('.')]

    if results_format == 'verywise':

        for p in sorted(top_level):
            subdir_list = [f for f in os.listdir(os.path.join(resdir, p)) if (
                os.path.isdir(os.path.join(resdir, p, f))) & (not f.startswith('.'))]
            
            if len(subdir_list) == 0: # already found the deepest level

                res = pd.DataFrame([d.split('.')[:2] for d in os.listdir(os.path.join(resdir, p)) if (
                    d.endswith('.mgh'))],
                    columns=['hemi', 'meas']).drop_duplicates()
                
                res['model'] = p
                all_results['results'][p] = res

            else:
                subdir_res = pd.DataFrame()
                
                for subdir in subdir_list:
                    res = pd.DataFrame([d.split('.')[:2] for d in os.listdir(os.path.join(resdir, p, subdir)) if (
                        d.endswith('.mgh'))],
                        columns=['hemi', 'meas']).drop_duplicates()
                    
                    res['model'] = subdir
                    subdir_res = pd.concat([subdir_res, res])
                
                all_results['results'][p] = subdir_res
    
    elif results_format == 'QDECR': #TODO: adapt this to all QDECR formats

        for p in sorted(top_level):
            subdir_list = [f for f in os.listdir(os.path.join(resdir, p)) if (
                os.path.isdir(os.path.join(resdir, p, f))) & (not f.startswith('.'))]
            
            if len(subdir_list) == 0: # already found the deepest level
                raise ValueError("Empty or malformed results directory.")
            
            else:
                all_results['results'][p] = pd.DataFrame([d.split('.') for d in subdir_list],
                                                         columns=['hemi','model','meas'])
    
    return all_results


def detect_terms(all_results, which_model, which_meas):

    resdir = all_results['results_directory']
    resformat = all_results['results_format']

    group, model = which_model.split('/')

    check_df = all_results['results'][group]

    if resformat == 'verywise':
        if group != model:
            check_df = check_df[check_df.model == model]
            
            mdir = f'{resdir}/{group}/{model}'
        else:
            mdir = f'{resdir}/{group}'

    elif resformat == 'QDECR':

        check_df = check_df[check_df.model == model]
        
        # Assume you have left and right hemispheres are always run and with the same model
        check_hemis = check_df['hemi'].unique()
        mdir = f'{resdir}/{group}/{check_hemis[0]}.{model}.{which_meas}'

    stacks = pd.read_table(os.path.join(mdir, 'stack_names.txt'), delimiter="\t")

    out_terms = dict(zip(list(stacks.stack_number)[1:], list(stacks.stack_name)[1:]))

    return out_terms


def extract_results(which_model, which_term, which_meas, 
                    resdir, resformat):

    group, model = which_model.split('/')

    if resformat == 'verywise':
        if group != model:
            mdir = f'{resdir}/{group}/{model}'
        else:
            mdir = f'{resdir}/{group}'

    min_beta = []
    max_beta = []
    med_beta = []
    n_clusters = []

    sign_clusters_left_right = {}
    sign_betas_left_right = {}
    all_observed_betas_left_right = {}

    missing_hemis = []

    for hemi in ['left', 'right']:

        try:
        # Read significant cluster map and the full beta maps
            if resformat == 'QDECR':
                mdir = os.path.join(resdir, group, f'{hemi[0]}h.{model}.{which_meas}')

                ocn = nb.load(os.path.join(mdir, f'stack{which_term}.cache.th30.abs.sig.ocn.mgh'))
                coef = nb.load(os.path.join(mdir, f'stack{which_term}.coef.mgh'))
            
            elif resformat == 'verywise':
        
                ocn = nb.load(os.path.join(mdir, f'{hemi[0]}h.{which_meas}.stack{which_term}.cache.th30.abs.sig.ocn.mgh'))
                coef = nb.load(os.path.join(mdir, f'{hemi[0]}h.{which_meas}.stack{which_term}.coef.mgh'))
        
        except FileNotFoundError as e:
            missing_hemis.append(hemi)
            # Fill with NAs for this hemisphere
            sign_clusters_left_right[hemi] = np.array([])
            sign_betas_left_right[hemi] = np.array([])
            all_observed_betas_left_right[hemi] = np.array([])
            min_beta.append(np.nan)
            max_beta.append(np.nan)
            med_beta.append(np.nan)
            n_clusters.append(0)
            continue

        sign_clusters = np.array(ocn.dataobj).flatten()

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
    
    if missing_hemis:
        raise FileNotFoundError(
            f'Could not find result files for the {" nor the ".join(missing_hemis)} hemisphere. '
            'Please check your results directory for missing or corrupted files.')

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


def compute_overlap(model1, term1, measure1, model2, term2, measure2, 
                    resdir, resformat):

    sign_clusters1 = extract_results(model1, term1, measure1, resdir, resformat)[4]
    sign_clusters2 = extract_results(model2, term2, measure2, resdir, resformat)[4]

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


def fetch_cont_colormap(stats_map,
                        max_val = 1,
                        min_val = -1, 
                        colorblind = True):

    if max_val < 0 and min_val < 0:  # all negative associations
        thresh = max_val
        cmap = 'viridis'
    elif max_val > 0 and min_val > 0:  # all positive associations
        thresh = min_val
        cmap = 'viridis_r' if colorblind else 'hot_r'
    else:
        # Diverging associations: create a custom colormap from hot_r (left) to viridis (right)
        thresh = np.nanmin(abs(stats_map))
        # Sample colors from hot_r (left side) and viridis (right side)
        hot_r = mpl.colormaps['hot_r'](np.linspace(0, 1, 128))
        viridis = mpl.colormaps['viridis'](np.linspace(0, 1, 128))
        # Stack: hot_r for negative, viridis for positive
        colors = np.vstack((viridis, hot_r))
        cmap = mpl.colors.LinearSegmentedColormap.from_list('hot_r_viridis', colors)
        # cmap = 'viridis'

    return(cmap, thresh)



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