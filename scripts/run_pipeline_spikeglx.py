# -*- coding: utf-8 -*-
from powerpixels import Pipeline
import subprocess
import os
from os.path import join, isdir
import numpy as np
from datetime import datetime
from pathlib import Path
import shutil
import platform

def prepare_raw_ephys_folder(session_path: Path):
    """
    # Jongwon 2026-03-11
    # Previously, the pipeline expected data to be organized as:
    #   DATA_FOLDER/mouse_id/date/raw_ephys_data/session_g0/session_imec0/
    # This function allows a simpler flat structure where session folders
    # are placed directly in DATA_FOLDER:
    #   DATA_FOLDER/session_g0/session_imec0/
    #
    # It creates raw_ephys_data/ inside the session folder and moves the
    # imec folder into it, renaming it to probe0x so that the Pipeline
    # class can proceed without any modification.
    #
    # Before:
    #   m408s1r1_g0/
    #       process_me.flag
    #       m408s1r1_g0_imec0/
    #
    # After:
    #   m408s1r1_g0/
    #       process_me.flag
    #       raw_ephys_data/
    #           probe00/        <- renamed here to avoid conflict with restructure_files()
    """
    raw_ephys_path = session_path / 'raw_ephys_data'

    # Skip if raw_ephys_data folder already exists (e.g. pipeline was interrupted and re-run)
    if raw_ephys_path.is_dir():
        print('  raw_ephys_data already exists, skipping')
        return

    # Find imec folders in the session directory
    data_folders = [p for p in session_path.iterdir()
                    if p.is_dir() and 'imec' in p.name]

    if not data_folders:
        print(f'  WARNING: No imec folders found in {session_path}')
        return

    raw_ephys_path.mkdir()
    for folder in data_folders:
        # Jongwon 2026-03-11
        # Rename imec folder to probe0x format here (e.g. imec0 -> probe00)
        # to prevent FileExistsError in restructure_files(), which also tries
        # to rename *imec* files/folders to probe0x and conflicts with existing files
        imec_num = folder.name.split('imec')[-1][0]
        probe_name = f'probe0{imec_num}'
        print(f'  Moving {folder.name} -> raw_ephys_data/{probe_name}')
        shutil.move(str(folder), str(raw_ephys_path / probe_name))

def get_server_base():
    if platform.system() == "Windows":
        return Path(r"Y:\NeuRLab\Data")
    else:
        def timeout_handler(signum, frame):
            raise TimeoutError

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10 second timeout

        try:
            use_10g = input("Use 10G connection? (y/n, auto-No in 10s): ").strip().lower()
            signal.alarm(0)  # Cancel timeout if input received
        except TimeoutError:
            print("No input received, using Y (standard) by default.")
            use_10g = 'n'

        if use_10g == 'y':
            return Path("/mnt/Y_10G/NeuRLab/Data")
        else:
            return Path("/mnt/Y/NeuRLab/Data")

if __name__ == "__main__":

    #check OS and set server base path accordingly
    
    pp = Pipeline()

    # Jongwon 2026-03-11
    # Previously used os.walk() which recursively searched through mouse/date subfolders.
    # Replaced with iterdir() to search only one level deep in DATA_FOLDER, allowing
    # session folders (e.g. m408s1r1_g0) to be placed directly in DATA_FOLDER
    # without the mouse_id/date folder hierarchy.
    print('Looking for process_me.flag..')
    sessions_to_process = []
    for session_dir in sorted(Path(pp.settings['DATA_FOLDER']).iterdir()):
        if session_dir.is_dir() and (session_dir / 'process_me.flag').exists():
            sessions_to_process.append(session_dir)

    print(f'Found {len(sessions_to_process)} session(s) to process:')
    for s in sessions_to_process:
        print(f'  - {s.name}')

    for session_path in sessions_to_process:
        print(f'\nStarting pipeline in {session_path} at {datetime.now().strftime("%H:%M")}\n')

        # Jongwon 2026-03-11
        # Re-initialize Pipeline for each session to prevent state contamination
        # (e.g. session_path, probe paths, data_format) from carrying over between sessions
        pp = Pipeline()
        pp.session_path = session_path

        # Jongwon 2026-03-11
        # Create raw_ephys_data/ and move imec folder into it as probe0x
        # so that the Pipeline class can find the data in its expected structure
        prepare_raw_ephys_folder(session_path)

        # Detect data format
        pp.detect_data_format()
        if pp.data_format == 'openephys':
            print('\nWARNING: You are running the SpikeGLX pipeline on an OpenEphys recording!\n')
            continue

        # Restructure files and folders
        pp.restructure_files()

        # Initialize NIDAQ synchronization
        if pp.settings['USE_NIDAQ']:
            pp.extract_sync_pulses()

        # Loop over multiple probes
        probes = [i for i in os.listdir(pp.session_path / 'raw_ephys_data')
                  if (i[:5] == 'probe') and (len(i) == 7)]
        probe_done = np.zeros(len(probes)).astype(bool)
        for i, this_probe in enumerate(probes):
            print(f'\nStarting preprocessing of {this_probe}')

            pp.set_probe_paths(this_probe)

            # Skip if probe already processed
            if isdir(join(pp.session_path, pp.this_probe + pp.settings['IDENTIFIER'])):
                print('Probe already processed, moving on')
                probe_done[i] = True
                continue

            pp.decompress()
            rec = pp.preprocessing()

            print(f'\nStarting {this_probe} spike sorting at {datetime.now().strftime("%H:%M")}')
            sort = pp.spikesorting(rec)
            if sort is None:
                print('Spike sorting failed!')
                continue
            print(f'Detected {sort.get_num_units()} units\n')

            pp.neuron_metrics(sort, rec)
            pp.export_data(rec)
            pp.automatic_curation()
            # Jongwon 2026-03-11: Run generate_curated_results.py after automatic curation,
            # passing session_path as argument so the script can locate probe/sorting results
            server_base = get_server_base()
            script_path = server_base / "protocol_specific" / "neuropixels" / "powerpixels" / "scripts" / "generate_curated_results.py"
            subprocess.run(["python", str(script_path), str(pp.session_path)])
            if pp.settings['USE_NIDAQ']:
                pp.probe_synchronization()

            pp.compress_raw_data()

            probe_done[i] = True
            print(f'Done! At {datetime.now().strftime("%H:%M")}')

        # Remove process_me.flag only if all probes are successfully processed
        if np.sum(probe_done) == len(probes):
            os.remove(session_path / 'process_me.flag')