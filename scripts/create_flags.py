# create_flags.py
from pathlib import Path
import json

# Go up one level from scripts/ to PowerPixelsPipeline/
project_root = Path(__file__).parent.parent
settings_file = project_root / 'config' / 'settings.json'

with open(settings_file, 'r') as f:
    settings = json.load(f)

data_folder = Path(settings['DATA_FOLDER'])

# Only process folders starting with 'm' (e.g. m408s1r1_g0)
for session_dir in sorted(data_folder.iterdir()):
    if not session_dir.is_dir() or not session_dir.name.startswith('m'):
        continue
    
    flag_path = session_dir / 'process_me.flag'
    if not flag_path.exists():
        flag_path.touch()
        print(f'Created flag: {session_dir.name}')
    else:
        print(f'Flag already exists, skipping: {session_dir.name}')