"""
Reading `wizard_config.toml`.

The point of this file is that making your own wizard should not mean editing
any code: a fork fills in the TOML, drops its results in a folder, and nothing
else in the repository has to change -- so pulling later updates stays clean.

With no results folder configured the app behaves exactly as it always has: a
welcome page with a folder box and a GO button. Name a folder and the app
switches to *preset* mode, where it already knows its results and opens on an
About page instead.

Environment variables win over the file, so a deployment can be pointed
somewhere else without a commit:

    VWWIZARD_RESULTS   results folder (path, or a public GitHub directory URL)
    VWWIZARD_SOFTWARE  'verywise' or 'QDECR'
    VWWIZARD_TITLE     browser title, and the heading on the About page
    VWWIZARD_REPO      the fork's own repository, shown in the navbar
"""
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
APP_ROOT = HERE.parent
CONFIG_FILE = APP_ROOT / 'wizard_config.toml'

# The repository this app is forked from, linked next to a fork's own repo
UPSTREAM_REPO = 'https://github.com/SereDef/verywise-wizard'
UPSTREAM_NAME = 'verywise-wizard'

DEFAULT_TITLE = 'Verywise Wizard'
SOFTWARE_CHOICES = ('verywise', 'QDECR')


@dataclass(frozen=True)
class WizardConfig:
    """What a fork can decide. Everything here has a working default."""

    results_folder: str = ''
    software: str = 'verywise'
    title: str = DEFAULT_TITLE
    intro: str = ''
    repo_url: str = ''

    @property
    def preset(self):
        """Whether this wizard already knows which results it shows."""
        return bool(self.results_folder)

    @property
    def is_fork(self):
        """A fork is a wizard that points at a repository of its own."""
        return bool(self.repo_url) and self.repo_url != UPSTREAM_REPO


def _read_file(path=CONFIG_FILE):
    """The TOML as nested dicts, or nothing at all if there is no file."""
    if not path.is_file():
        return {}

    with open(path, 'rb') as f:
        return tomllib.load(f)


def _env(name):
    """An environment variable, treating blank as unset."""
    value = os.environ.get(f'VWWIZARD_{name}', '')
    return value.strip()


def load_config(path=CONFIG_FILE):
    """Build the config from the file, then let the environment override it."""
    raw = _read_file(path)

    results = raw.get('results') or {}
    about = raw.get('about') or {}
    repo = raw.get('repo') or {}

    software = _env('SOFTWARE') or results.get('software') or 'verywise'

    if software not in SOFTWARE_CHOICES:
        raise ValueError(
            f'Unknown analysis software {software!r} in {path.name}: '
            f'expected one of {", ".join(SOFTWARE_CHOICES)}.')

    return WizardConfig(
        results_folder=_env('RESULTS') or (results.get('folder') or '').strip(),
        software=software,
        title=_env('TITLE') or about.get('title') or DEFAULT_TITLE,
        intro=about.get('intro') or '',
        repo_url=(_env('REPO') or repo.get('url') or '').strip(),
    )


CONFIG = load_config()
