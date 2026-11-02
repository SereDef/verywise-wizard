"""
Camera presets for the brain views
==================================
Manual settings for view angles and zoom.

Tuning guide
------------
'eye'      -- direction vector toward the camera. Rotates the brain.
'distance' -- Smaller = more zoomed in (eye vector scaled to this length).
'up'       -- For lateral/medial/anterior/posterior: (0,0,1) = superior up.
              For dorsal/ventral: (-1,0,0) / (1,0,0). For flat: (0,1,0).
'center'   -- Shifts the brain -- always (0,0,0) except for inflated surfaces.

Surface keys follow nilearn's naming ('inflated', 'white_matter', ...), not
FreeSurfer's.
"""

import math

VIEWS = ('lateral', 'medial', 'dorsal', 'ventral', 'anterior', 'posterior')

# Views that show both hemispheres at once, so they are never split per hemisphere
WHOLE_BRAIN_VIEWS = ('dorsal', 'ventral', 'anterior', 'posterior')


def _bilateral(presets):
    """Expand ('both', view) entries to also cover ('left'/'right', view)."""
    extra = {}
    for (hemi, view), v in presets.items():
        if hemi == 'both':
            extra.setdefault(('left', view), v)
            extra.setdefault(('right', view), v)
    return {**extra, **presets}


class VeryWiseCameraPresets:
    """
    Registry of camera presets, with a per-call override hook.

    This is a class-level constant registry (not instance-configurable);
    `resolve()` supports a per-call `custom_presets` override on top of it.
    """

    PRESETS = {
        'pial': _bilateral({
            ('left', 'lateral'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.20),
            ('right', 'lateral'):  dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.20),
            ('left', 'medial'):    dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.05),
            ('right', 'medial'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.05),
            ('both', 'dorsal'):    dict(eye=( 0.0, 0.0, 1.0), up=(-1, 0, 0), distance=1.15),
            ('both', 'ventral'):   dict(eye=( 0.0, 0.0,-1.0), up=( 1, 0, 0), distance=1.30),
            ('both', 'anterior'):  dict(eye=( 0.0, 1.0, 0.0), up=(0, 0, 1), distance=1.15),
            ('both', 'posterior'): dict(eye=( 0.0,-1.0, 0.0), up=(0, 0, 1), distance=1.15),
            # Lateral/medial are hemisphere-specific; these only apply when both
            # hemispheres share one scene, and then look in from the left.
            ('both', 'lateral'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('both', 'medial'):    dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
        }),
        'inflated': _bilateral({
            ('left', 'lateral'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.10),
            ('right', 'lateral'):  dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.10),
            ('left', 'medial'):    dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.20),
            ('right', 'medial'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.20),
            ('both', 'dorsal'):    dict(eye=(0.11, 0.0, 1.25), up=(-1, 0, 0), center=(0.15, 0, 0), distance=1.15),
            ('both', 'ventral'):   dict(eye=(0.25, 0.0,-1.30), up=( 1, 0, 0), center=(0.18, 0, 0), distance=1.30),
            ('both', 'anterior'):  dict(eye=(0.16, 1.1,-0.10), up=(0, 0.2, 1), center=(0.20, 0, 0), distance=1.15),
            ('both', 'posterior'): dict(eye=(0.20,-1.1, 0.00), up=(0, 0, 1), center=(0.18, 0, 0), distance=1.15),
            ('both', 'lateral'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('both', 'medial'):    dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
        }),
        # white_matter sits between pial and inflated
        'white_matter': _bilateral({
            ('left', 'lateral'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.20),
            ('right', 'lateral'):  dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.20),
            ('left', 'medial'):    dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.05),
            ('right', 'medial'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.05),
            ('both', 'dorsal'):    dict(eye=( 0.0, 0.0, 1.0), up=(-1, 0, 0), distance=1.18),
            ('both', 'ventral'):   dict(eye=( 0.0, 0.0,-1.0), up=( 1, 0, 0), distance=1.32),
            ('both', 'anterior'):  dict(eye=( 0.0, 1.0, 0.0), up=(0, 0, 1), distance=1.15),
            ('both', 'posterior'): dict(eye=( 0.0,-1.0, 0.0), up=(0, 0, 1), distance=1.15),
            ('both', 'lateral'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('both', 'medial'):    dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
        }),
        # The flat patch lies in the xy-plane, so every view looks straight down
        # onto it and only the in-plane rotation differs.
        'flat': _bilateral({
            ('both', 'lateral'):   dict(eye=(0.0, 0.0, 1.0), up=(0, 1, 0), distance=1.05),
            ('both', 'medial'):    dict(eye=(0.0, 0.0,-1.0), up=(0, 1, 0), distance=1.05),
            ('both', 'dorsal'):    dict(eye=(0.0, 0.0, 1.0), up=(-1, 0, 0), distance=1.05),
            ('both', 'ventral'):   dict(eye=(0.0, 0.0,-1.0), up=( 1, 0, 0), distance=1.05),
            ('both', 'anterior'):  dict(eye=(0.0, 0.0, 1.0), up=(0, 1, 0), distance=1.05),
            ('both', 'posterior'): dict(eye=(0.0, 0.0,-1.0), up=(0, 1, 0), distance=1.05),
        }),
        'sphere': _bilateral({
            ('left', 'lateral'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('right', 'lateral'):  dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('left', 'medial'):    dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('right', 'medial'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('both', 'dorsal'):    dict(eye=( 0.0, 0.0, 1.0), up=(-1, 0, 0), distance=1.30),
            ('both', 'ventral'):   dict(eye=( 0.0, 0.0,-1.0), up=( 1, 0, 0), distance=1.30),
            ('both', 'anterior'):  dict(eye=( 0.0, 1.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('both', 'posterior'): dict(eye=( 0.0,-1.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('both', 'lateral'):   dict(eye=(-1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
            ('both', 'medial'):    dict(eye=( 1.0, 0.0, 0.0), up=(0, 0, 1), distance=1.30),
        }),
    }

    @classmethod
    def resolve(cls, hemi, view, surface, custom_presets=None):
        """
        Resolve the camera dict for a (hemi, view, surface) triple.

        Lookup order:
          1. custom_presets[surface][(hemi, view)]  -- per-call override
          2. PRESETS[surface][(hemi, view)]         -- surface-specific constant
          3. PRESETS['inflated'][(hemi, view)]      -- last-resort fallback
        """
        surface_key = surface if surface in cls.PRESETS else 'inflated'

        p = None
        for source in (custom_presets, cls.PRESETS):
            if source and surface_key in source:
                p = source[surface_key].get((hemi, view))
            if p is not None:
                break

        if p is None:
            raise ValueError(
                f'No camera preset for surface={surface!r}, hemi={hemi!r}, view={view!r}. '
                f'Add it to VeryWiseCameraPresets.PRESETS[{surface_key!r}].')

        ex, ey, ez = p['eye']
        ux, uy, uz = p['up']
        cx, cy, cz = p.get('center', (0.0, 0.0, 0.0))

        scale = p['distance'] / (math.sqrt(ex ** 2 + ey ** 2 + ez ** 2) or 1.0)

        return {'eye': dict(x=ex * scale, y=ey * scale, z=ez * scale),
                'up': dict(x=ux, y=uy, z=uz),
                'center': dict(x=cx, y=cy, z=cz)}
