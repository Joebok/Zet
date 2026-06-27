import tomllib
from pathlib import Path
import os

toml_data = """
# This is a comment. TOML files use hash symbols for comments.
title = "Zet's Magic Pipeline"

[BaseFolders]
BaseCharacterPath = "_Lib/Characters/"
BaseAssetPath = "_Lib/Assets/"
BasePipelinePath = "_Lib/Pipelines/"
BaseAIQueuePath = "_Lib/AI_Queue"
"""

# 2. Parse the TOML data
# Note: tomllib requires binary mode, so we convert the string to bytes
config = tomllib.loads(toml_data)

# 3. Access the dictionary values under the "BaseFolders" table
base_folders = config["BaseFolders"]

character_path = base_folders["BaseCharacterPath"]
asset_path = base_folders["BaseAssetPath"]
pipeline_path = base_folders["BasePipelinePath"]
ai_queue_path = base_folders["BaseAIQueuePath"]

# 4. Print the results
print(f"Character Path: {character_path}")
print(f"Asset Path: {asset_path}")
print(f"Pipeline Path: {pipeline_path}")
print(f"AI Queue Path: {ai_queue_path}")

if not os.path.exists(character_path):
    os.makedirs(character_path)
if not os.path.exists(asset_path):
    os.makedirs(asset_path)
if not os.path.exists(pipeline_path):
    os.makedirs(pipeline_path)
if not os.path.exists(ai_queue_path):
    os.makedirs(ai_queue_path)
    if not os.path.exists(f'{ai_queue_path}\Ask'):
        os.makedirs(f'{ai_queue_path}\Ask')
    if not os.path.exists(f'{ai_queue_path}\Answer'):
        os.makedirs(f'{ai_queue_path}\Answer')
    if not os.path.exists(f'{ai_queue_path}\Claimed'):
        os.makedirs(f'{ai_queue_path}\Claimed')
    if not os.path.exists(f'{ai_queue_path}\Claims'):
        os.makedirs(f'{ai_queue_path}\Claims')
    if not os.path.exists(f'{ai_queue_path}\RunScripts'):
        os.makedirs(f'{ai_queue_path}\RunScripts')
    if not os.path.exists(f'{ai_queue_path}\Discarded'):
        os.makedirs(f'{ai_queue_path}\Discarded')
    if not os.path.exists(f'{ai_queue_path}\Failed'):
        os.makedirs(f'{ai_queue_path}\Failed')

