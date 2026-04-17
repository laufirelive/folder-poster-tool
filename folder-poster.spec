# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Folder Poster portable build (--onedir)."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

transformers_datas = collect_data_files("transformers", includes=["**/*.json"])

hidden = [
    "einops",
    "kornia",
    "timm",
    "PIL",
    "huggingface_hub",
]
hidden += collect_submodules("transformers.models.bit")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=transformers_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "tkinter",
        "jupyter",
        "notebook",
        "pytest",
        "sphinx",
        "IPython",
        "jedi",
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Folder-Poster",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Folder-Poster",
)
