"""
Locate, parse and read vertex-wise results
==========================================
Everything in this module is data: no colormaps, no figures, no nilearn.plotting.

Pipeline
--------
resolve_resdir      : local path or (public) GitHub folder URL -> local directory
detect_models       : walk the directory -> {group: DataFrame(group, model, hemi, meas)}
detect_terms        : read stack_names.txt -> {stack_number: stack_name}
extract_results     : read the .mgh maps for one model/term/measure -> VWResult
cluster_stats       : per-cluster size and beta summaries -> DataFrame
compute_overlap     : combine two VWResults -> (info, overlap maps)
"""

import os
import re
import shutil
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
import nibabel as nb

from shiny import ui

here = Path(__file__).parent

HEMIS = ('left', 'right')

# Measures whose name contains a dot, so they cannot be split on '.' naively
SPECIAL_MEAS_NAMES = ('area.pial', 'w_g.pct', 'white.H', 'white.K')

_GITHUB_FOLDER_RE = r"https://github.com/([^/]+)/([^/]+)/tree/([^/]+)/(.*)"
_GITHUB_FOLDER_CACHE = {}


# ===== LOCATE THE RESULTS =====================================================

def resolve_resdir(resdir):
    """Return a local directory for `resdir`, downloading it first if needed."""
    if os.path.isdir(resdir):
        return resdir

    if re.match(_GITHUB_FOLDER_RE, resdir):
        return download_github_folder(resdir)

    # A relative path should also work when the app is not started from its own
    # directory, which is how it runs once deployed
    if not os.path.isabs(resdir):
        from_app_root = os.path.normpath(os.path.join(here.parent, resdir))
        if os.path.isdir(from_app_root):
            return from_app_root

    # (Handle other cases: zip, repo, etc.)
    raise ValueError(f'Folder specified in path does not exist: {resdir}')


def download_github_folder(github_url, download_loc=here.parent, github_token=None):
    """
    Download a folder from a public GitHub repo to a local directory.
    github_url: e.g. https://github.com/user/repo/tree/main/path/to/folder
    Returns the local path to the downloaded folder.
    """
    import requests

    if github_url in _GITHUB_FOLDER_CACHE:
        return _GITHUB_FOLDER_CACHE[github_url]

    m = re.match(_GITHUB_FOLDER_RE, github_url)
    if not m:
        raise ValueError('URL must be of the form '
                         'https://github.com/user/repo/tree/branch/path/to/folder')
    user, repo, branch, folder_path = m.groups()

    api_url = f'https://api.github.com/repos/{user}/{repo}/contents/{folder_path}?ref={branch}'

    folder_local = Path(download_loc) / 'tmp_results'  # todo folder name
    if folder_local.is_dir():
        shutil.rmtree(folder_local, ignore_errors=True)
    os.makedirs(folder_local)

    if github_token is None:
        github_token = os.environ.get('GITHUB_TOKEN')
    headers = {'Authorization': f'token {github_token}'} if github_token else {}

    def download_contents(api_url, local_dir, print_progress=True):
        resp = requests.get(api_url, headers=headers)
        resp.raise_for_status()
        contents = resp.json()

        with ui.Progress(min=0, max=len(contents)) as p:
            for e, file_info in enumerate(contents):
                prefix = 'Downloading ' if print_progress else ''
                p.set(value=e + 1,
                      message=f"{prefix}[{e + 1}/{len(contents)}]: {file_info['name']}...")

                if file_info['type'] == 'dir':
                    subfolder_local = os.path.join(local_dir, file_info['name'])
                    os.makedirs(subfolder_local, exist_ok=True)
                    download_contents(file_info['url'], subfolder_local, print_progress=False)

                elif file_info['type'] == 'file':
                    file_resp = requests.get(file_info['download_url'])
                    file_resp.raise_for_status()
                    with open(os.path.join(local_dir, file_info['name']), 'wb') as f:
                        f.write(file_resp.content)

    download_contents(api_url, folder_local)

    _GITHUB_FOLDER_CACHE[github_url] = folder_local

    return folder_local


# ===== PARSE THE DIRECTORY STRUCTURE ==========================================

def parse_directory_structure(resdir):
    """Recursively find all coefficient .mgh files, including nested directories."""
    return [os.path.join(root, f)
            for root, _, filenames in os.walk(resdir)
            for f in filenames if f.endswith('coef.mgh')]


def _split_meas(parts, start):
    """Join parts[start:start+2] when they form one of the dotted measure names."""
    two = '.'.join(parts[start:start + 2])
    return two if two in SPECIAL_MEAS_NAMES else parts[start]


def parse_verywise_filenames(d):
    """'lh.thickness.stack2.coef.mgh' -> ('lh', 'thickness')"""
    parts = d.split('.')
    return parts[0], _split_meas(parts, 1)


def parse_qdecr_filenames(d):
    """'lh.my_model.thickness' -> ('my_model', 'lh', 'thickness')"""
    parts = d.split('.')
    hemi, model = parts[0], parts[1]

    meas = _split_meas(parts, 2)
    if len(parts) > 3 and meas not in SPECIAL_MEAS_NAMES:
        raise ValueError(f'Incorrect (QDECR) project name. {parts}')

    return model, hemi, meas


def detect_models(resdir, results_format):
    """Walk `resdir` and describe every model found in it."""
    resdir = resolve_resdir(resdir)

    all_files = parse_directory_structure(resdir)
    if not all_files:
        raise ValueError('No .mgh files found in the specified directory.')

    rows = []
    for file_path in all_files:
        parent_dir = os.path.dirname(file_path)

        if results_format == 'verywise':
            model = (os.path.basename(parent_dir) if parent_dir == resdir
                     else parent_dir.replace(f'{resdir}/', ''))
            hemi, meas = parse_verywise_filenames(os.path.basename(file_path))
            group = model

        elif results_format == 'QDECR':  # TODO: adapt this to all QDECR formats
            model, hemi, meas = parse_qdecr_filenames(os.path.basename(parent_dir))
            group = os.path.dirname(parent_dir.replace(f'{resdir}/', ''))

        else:
            raise ValueError(f'Unknown results format: {results_format}')

        rows.append(dict(group=group, model=model, hemi=hemi, meas=meas))

    res = pd.DataFrame(rows).drop_duplicates()

    return {'results_directory': resdir,
            'results_format': results_format,
            'results': {group: data for group, data in res.groupby('group')}}


def model_dir(all_results, which_model, which_meas=None, hemi=None):
    """Directory holding the result files for one model (and hemisphere, for QDECR)."""
    resdir = all_results['results_directory']
    resformat = all_results['results_format']

    group, model = which_model.split('/')

    if resformat == 'verywise':
        return f'{resdir}/{group}' if group == model else f'{resdir}/{group}/{model}'

    # QDECR keeps each hemisphere in its own directory. When no hemisphere is
    # requested, fall back to any hemisphere that was run for this model:
    # stack_names.txt is identical across them.
    if hemi is None:
        check_df = all_results['results'][group]
        hemi = check_df[check_df.model == model]['hemi'].unique()[0]
    else:
        hemi = f'{hemi[0]}h'

    return os.path.join(resdir, group, f'{hemi}.{model}.{which_meas}')


def detect_terms(all_results, which_model, which_meas):
    """Read the model's stack_names.txt -> {stack_number: stack_name}."""
    mdir = model_dir(all_results, which_model, which_meas)

    stacks = pd.read_table(os.path.join(mdir, 'stack_names.txt'), delimiter='\t')

    # The first stack is the intercept, which is never of interest here
    return dict(zip(list(stacks.stack_number)[1:], list(stacks.stack_name)[1:]))


def result_paths(all_results, which_model, which_term, which_meas, hemi):
    """Return the (cluster map, coefficient map) paths for one hemisphere."""
    resformat = all_results['results_format']
    mdir = model_dir(all_results, which_model, which_meas, hemi=hemi)

    if resformat == 'QDECR':
        stem = f'stack{which_term}'
    else:
        stem = f'{hemi[0]}h.{which_meas}.stack{which_term}'

    return (os.path.join(mdir, f'{stem}.cache.th30.abs.sig.ocn.mgh'),
            os.path.join(mdir, f'{stem}.coef.mgh'))


# ===== READ THE RESULTS =======================================================

def _load_mgh(path, dtype=np.float32):
    """Read an .mgh map as a flat, native-endian array (+/-Inf -> NaN)."""
    arr = np.asarray(nb.load(path).dataobj, dtype=dtype).ravel()
    if np.issubdtype(arr.dtype, np.floating):
        arr[~np.isfinite(arr)] = np.nan
    return arr


class VWResult(NamedTuple):
    """
    Vertex-wise result for one model / term / measure.

    Attributes
    ----------
    betas : dict
        hemi -> *all* observed beta values (nothing masked out).
    mask : dict
        hemi -> bool, True where the vertex belongs to a significant cluster.
    clusters : dict
        hemi -> cluster id per vertex, 0 where not significant. Ids are unique
        *across* hemispheres (the right hemisphere is offset by the number of
        left-hemisphere clusters) so that one colormap covers both.
    n_clusters : dict
        hemi -> number of significant clusters.
    """
    betas: dict
    mask: dict
    clusters: dict
    n_clusters: dict

    @property
    def sign_betas(self):
        """hemi -> beta values, NaN outside significant clusters."""
        return {h: np.where(self.mask[h], self.betas[h], np.nan) for h in HEMIS}

    @property
    def total_clusters(self):
        return int(sum(self.n_clusters.values()))

    @property
    def is_empty(self):
        return self.total_clusters == 0

    def beta_summary(self):
        """(min, mean, max) across all significant vertices of both hemispheres."""
        sign = np.concatenate([self.sign_betas[h] for h in HEMIS])
        if np.all(np.isnan(sign)):
            return np.nan, np.nan, np.nan
        return float(np.nanmin(sign)), float(np.nanmean(sign)), float(np.nanmax(sign))


def extract_results(all_results, which_model, which_term, which_meas):
    """Read the cluster and coefficient maps for one model/term/measure."""
    betas, mask, clusters, n_clusters = {}, {}, {}, {}

    missing_hemis = []
    cluster_offset = 0

    for hemi in HEMIS:
        ocn_path, coef_path = result_paths(
            all_results, which_model, which_term, which_meas, hemi)

        if not (os.path.exists(ocn_path) and os.path.exists(coef_path)):
            missing_hemis.append(hemi)
            continue

        sign_clusters = _load_mgh(ocn_path, dtype=np.int32)

        beta = _load_mgh(coef_path)

        # Vertices outside the cortex come out as exact zeros. Treat them as
        # missing, so they neither colour the surface nor pile up at zero in
        # the density estimate. (Note: the cluster map's zeros are meaningful --
        # they mark non-significant vertices -- so only the betas are touched.)
        beta[beta == 0.0] = np.nan

        betas[hemi] = beta
        mask[hemi] = sign_clusters > 0
        n_clusters[hemi] = int(sign_clusters.max())

        # Shift this hemisphere's ids so they do not collide with the other's
        clusters[hemi] = np.where(sign_clusters > 0, sign_clusters + cluster_offset, 0)
        cluster_offset += n_clusters[hemi]

    if missing_hemis:
        raise FileNotFoundError(
            f'Could not find result files for the {" nor the ".join(missing_hemis)} '
            'hemisphere. Please check your results directory for missing or '
            'corrupted files.')

    return VWResult(betas=betas, mask=mask, clusters=clusters, n_clusters=n_clusters)


# ===== SUMMARISE ==============================================================

def cluster_stats(result):
    """Per-cluster size and beta summaries, ordered left hemisphere first."""
    rows = []
    for hemi in HEMIS:
        if result.n_clusters[hemi] == 0:
            continue

        df = pd.DataFrame({'cluster': result.clusters[hemi],
                           'beta': result.betas[hemi]})
        df = df[df['cluster'] > 0]

        stats = df.groupby('cluster')['beta'].agg(['count', 'mean', 'min', 'max'])
        stats.columns = ['size', 'mean', 'min', 'max']
        stats.insert(0, 'hemi', hemi)

        rows.append(stats.reset_index())

    if not rows:
        return pd.DataFrame(columns=['cluster', 'hemi', 'size', 'mean', 'min', 'max'])

    out = pd.concat(rows, ignore_index=True)
    out['label'] = [f'Cluster {int(c)}' for c in out['cluster']]

    return out


def compute_difference(result1, result2):
    """
    Subtract one result's beta map from the other, vertex by vertex.

    Nothing is masked: the difference is returned everywhere, including
    vertices that were significant in neither map. Vertices outside the cortex
    are NaN in both inputs (extract_results turns the exact zeros there into
    NaN), so they stay NaN here and render uncoloured -- that is why the medial
    wall still looks blank, not because it was masked out.
    """
    return {hemi: result1.betas[hemi] - result2.betas[hemi] for hemi in HEMIS}


def compute_overlap(result1, result2):
    """
    Combine the significant clusters of two results.

    Returns (info, maps) where `maps` codes each vertex as
    1 = result1 only, 2 = result2 only, 3 = both,
    and `info` maps those same codes to [n_vertices, percentage].
    """
    maps, counts = {}, {}

    for hemi in HEMIS:
        # Note: build fresh arrays, never modify the inputs in place
        maps[hemi] = (result1.mask[hemi].astype(np.int8)
                      + 2 * result2.mask[hemi].astype(np.int8))

        uniques, n = np.unique(maps[hemi], return_counts=True)
        counts[hemi] = {int(u): int(c) for u, c in zip(uniques, n) if u > 0}

    # Merge left and right
    info = {k: [counts['left'].get(k, 0) + counts['right'].get(k, 0)]
            for k in sorted(set(counts['left']) | set(counts['right']))}

    total = sum(v[0] for v in info.values())
    for v in info.values():
        v.append(round(v[0] / total * 100, 1) if total else 0.0)

    return info, maps
