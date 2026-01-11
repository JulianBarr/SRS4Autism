# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the backend directory path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(SPECPATH)), 'backend')

# Collect all data files from cuma_knowledge_graph
cuma_kg_path = os.path.join(backend_dir, 'cuma_knowledge_graph')

# Define data files to include
datas = []

# Add the entire cuma_knowledge_graph directory
if os.path.exists(cuma_kg_path):
    datas.append((cuma_kg_path, 'cuma_knowledge_graph'))

# Add any other data directories from backend
data_dirs = ['data', 'migrations']
for data_dir in data_dirs:
    data_path = os.path.join(backend_dir, data_dir)
    if os.path.exists(data_path):
        datas.append((data_path, data_dir))

# Add .env files if they exist
env_files = ['.env', 'gemini.env', 'google-credentials.json']
for env_file in env_files:
    env_path = os.path.join(backend_dir, env_file)
    if os.path.exists(env_path):
        datas.append((env_path, '.'))

# Collect hidden imports for FastAPI and related packages
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'pydantic',
    'oxrdflib',
    'rdflib',
]

# Collect submodules for key packages
for package in ['uvicorn', 'fastapi', 'starlette', 'pydantic', 'rdflib']:
    try:
        hiddenimports.extend(collect_submodules(package))
    except Exception as e:
        print(f"Warning: Could not collect submodules for {package}: {e}")

a = Analysis(
    [os.path.join(backend_dir, 'run.py')],
    pathex=[backend_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='api',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to True to see backend logs, False for production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='api',
)
