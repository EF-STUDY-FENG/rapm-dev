# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['psychopy', 'psychopy.visual', 'psychopy.visual.line', 'psychopy.event', 'psychopy.core', 'psychopy.gui', 'psychopy.plugins', 'psychopy.visual.backends.pygletbackend', 'pyglet', 'pyglet.gl', 'pyglet.window', 'pyglet.window.win32', 'pyglet.canvas', 'pyglet.graphics', 'PIL']
hiddenimports += collect_submodules('psychopy')
hiddenimports += collect_submodules('psychopy.visual')
hiddenimports += collect_submodules('psychopy.tools')
hiddenimports = [
    'psychopy', 'psychopy.visual', 'psychopy.visual.line', 'psychopy.event', 'psychopy.core',
    'psychopy.gui', 'psychopy.plugins', 'psychopy.visual.backends.pygletbackend',
    'pyglet', 'pyglet.gl', 'pyglet.window', 'pyglet.window.win32', 'pyglet.canvas',
    'pyglet.graphics', 'PIL'
]
hiddenimports += collect_submodules('psychopy')
hiddenimports += collect_submodules('psychopy.visual')
hiddenimports += collect_submodules('psychopy.tools')


"""PyInstaller spec for RavenTask.

This file is versioned to ensure reproducible builds in CI (e.g. GitHub Actions).
Adjust 'excludes' and 'hiddenimports' as the project evolves.
"""

a = Analysis(
    ['scripts/raven_task.py'],  # relative path for portability across machines/CI
    pathex=[],
    binaries=[],
    datas=[('configs', 'configs'), ('stimuli', 'stimuli')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude PsychoPy demos and tests to reduce build size.
        'psychopy.tests',
        'psychopy.demos',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RavenTask',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RavenTask',
)
