# Jongwon 2026-03-11
# This script is designed to be run in two scenarios:
#
# 1. AUTOMATIC: Called automatically at the end of run_pipeline_spikeglx via subprocess,
#    with pp.session_path passed as a command line argument (sys.argv[1]).
#    Runs immediately after spike sorting and automated curation are complete.
#
# 2. MANUAL: Run manually after performing manual curation in the SpikeInterface GUI.
#    In this case, run the script directly and enter the session path when prompted.
#    This regenerates cluster_info.tsv and cluster_group.tsv to reflect manual curation labels,
#    and re-migrates the updated results to the server.
#
# Jongwon 2026-03-26
# Added Migration 2 at the end of this script (see bottom).
# After compress_raw_data() completes in run_pipeline_spikeglx, this migration
# backs up the full session folder to the server so the pipeline does not need
# to be re-run from scratch later.
#
# Migration 1 (existing): copies ap.meta, lf.bin, lf.meta and sorter output
#                          to Y:\...\{mid}\np\{base_name}\{base_name}_imec0\
# Migration 2 (new):      copies full analysis folders to Y:\...\{mid}\np\{base_name}\
#   - kilosort4/          -> full copy
#   - probe00/            -> full copy
#   - raw_behavior_data/  -> full copy
#   - raw_video_data/     -> full copy
#   - raw_ephys_data/     -> directory structure only (no files),
#                            EXCEPT *power* / *psd* files which are copied


import pandas as pd
import numpy as np
import os
import shutil
import glob
import spikeinterface.full as si
import spikeinterface.exporters as se
from spikeinterface.curation import CurationSorting
from pathlib import Path
import sys
import platform
import signal

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
def _copy_file_if_needed(src: Path, dst: Path):
    """Copy a single file, skipping if destination already exists with same size."""
    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        print(f"  Skipping (exists): {dst.name}")
    else:
        print(f"  Copying: {src.name}")
        shutil.copy2(src, dst)

def copy_folder_full(src: Path, dst: Path):
    """Recursively copy an entire folder to dst."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob('*'):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            _copy_file_if_needed(item, target)

def copy_raw_ephys_structure_and_psd(src: Path, dst: Path):
    """
    Recreate the raw_ephys_data directory structure without copying files,
    except for power spectral density files (*power* or *psd* in filename).
    """
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob('*'):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            name_lower = item.name.lower()
            if 'power' in name_lower or 'psd' in name_lower:
                _copy_file_if_needed(item, target)
            # all other files: skip (preserve directory structure only)



# 1. User Input or Argument Definitions
if len(sys.argv) > 1:
    user_input = sys.argv[1]
else:
    user_input = input(r"root_path (ex: D:\Data\m1443s1r2_g0): ").strip().replace('"', '').replace("'", "")

root_path = Path(user_input)

# Jongwon 2026-03-11
# Previously, folder_base_name and mid_part were parsed by searching for m*s*r*
# folders inside raw_ephys_data/probe00/, which no longer exist in the new flat structure.
# Now parsed directly from root_path (session folder name) since run_pipeline_spikeglx
# passes pp.session_path as the argument, which is already the session folder (e.g. m1443s1r2_g0).
folder_base_name = root_path.name  # e.g. m1443s1r2_g0
mid_part = folder_base_name.split('s')[0].replace('m', '')  # e.g. 1443

# Jongwon 2026-03-11
# Updated base_path to reflect new folder structure where probe00 sits inside
# raw_ephys_data/ instead of directly under the session root
base_path = root_path / "probe00"
sorting_path = base_path / "sorting"
ks_output_dir = root_path / "kilosort4" / "probe00" / "sorter_output"
phy_output_dir = ks_output_dir
json_path = sorting_path / "spikeinterface_gui" / "curation_data.json"

# 2. Load Sorting and Check for Unit Changes
analyzer = si.load_sorting_analyzer(sorting_path)
curated_sorting = CurationSorting(analyzer.sorting, json_path)

original_unit_ids = analyzer.sorting.unit_ids
curated_unit_ids = curated_sorting.sorting.unit_ids

print(f"Original units: {len(original_unit_ids)}")
print(f"Curated units: {len(curated_unit_ids)}")

# -------------------------------------------------------------------------
# Case Selection: Decide whether to re-compute based on Unit Count
# -------------------------------------------------------------------------
if len(original_unit_ids) != len(curated_unit_ids):
    print("Changes detected. Running SpikeInterface Re-computation...")
    actual_curated_sorting = curated_sorting.sorting
    curated_analyzer = si.create_sorting_analyzer(actual_curated_sorting, analyzer.recording, format="memory")
    curated_analyzer.compute(["random_spikes", "waveforms", "templates"], n_jobs=-1)

    se.export_to_phy(curated_analyzer, output_folder=phy_output_dir,
                     copy_binary=False, remove_if_exists=True,
                     compute_pc_features=False, compute_amplitudes=False, sparsity=None)

    unit_ids = curated_analyzer.unit_ids
    templates = curated_analyzer.get_extension('templates').get_data()
    abs_templates = np.abs(templates)
    max_abs_per_unit = np.max(abs_templates, axis=1)
else:
    print("No changes. Using Kilosort output directly...")
    unit_ids = original_unit_ids
    templates = np.load(os.path.join(ks_output_dir, "templates.npy"))
    abs_templates = np.abs(templates)
    max_abs_per_unit = np.max(abs_templates, axis=1)

# -------------------------------------------------------------------------
# 3. Final Grouping Logic & cluster_info.tsv Generation
# -------------------------------------------------------------------------

# Load automated QC labels from three independent quality metrics:
# - Bombcell: waveform-based quality metric
#     0 = noise, 1 = good single neuron, 2 = multi-unit activity, 3 = non-somatic
# - IBL: Inter-Brain-Laboratory pipeline quality metric
#     0 = noise, 0.33-0.66 = multi-unit activity, 1 = good single neuron
# - UnitRefine: ML-based single unit classifier
#     0 = multi-unit activity or noise, 1 = good single neuron

bombcell_all = np.load(os.path.join(base_path, "clusters.bombcellLabels.npy"))
ibl_all = np.load(os.path.join(base_path, "clusters.iblLabels.npy"))
unit_refine_all = np.load(os.path.join(base_path, "clusters.unitrefineLabels.npy"))

# Load manual curation labels if they exist (set during manual curation in SpikeInterface GUI)
# If not found, initialize with empty strings (no manual label for any unit)

try:
    manual_all = np.load(os.path.join(base_path, "clusters.manualLabels.npy"), allow_pickle=True)
except FileNotFoundError:
    manual_all = np.array([''] * (max(unit_ids) + 1))

# Classify each unit as 'good' or 'mua' based on the following priority:
# 1. If a manual label exists for this unit, always use it (manual overrides everything)
# 2. If no manual label, unit is 'good' only if ALL THREE automated metrics agree (strict consensus):
#    - Bombcell == 1 (good single neuron)
#    - IBL == 1 (good single neuron)
#    - UnitRefine == 1 (good single neuron)
#    - If any one of the three fails, the unit is classified as 'mua'

final_groups = []
for idx in unit_ids:
    m_label = manual_all[idx]
    b_val = bombcell_all[idx]
    i_val = ibl_all[idx]
    u_val = unit_refine_all[idx]

    if m_label and str(m_label).lower() != 'nan' and str(m_label) != '':
        # Manual label takes priority over all automated metrics
        final_groups.append(str(m_label))
    else:
        # Unit is 'good' only if all three automated QC metrics agree
        is_good = (b_val == 1) and (i_val == 1) and (u_val == 1)
        final_groups.append('good' if is_good else 'mua')

channel_positions = np.load(os.path.join(ks_output_dir, "channel_positions.npy"))
spike_clusters = np.load(os.path.join(ks_output_dir, "spike_clusters.npy"))
spike_times = np.load(os.path.join(ks_output_dir, "spike_times.npy"))

main_channels = np.argmax(max_abs_per_unit, axis=1)
depths = channel_positions[main_channels, 1]
unique, counts = np.unique(spike_clusters, return_counts=True)
count_dict = dict(zip(unique, counts))
n_spikes = [count_dict.get(i, 0) for i in unit_ids]
total_duration_sec = (spike_times.max() - spike_times.min()) / 30000

cluster_info = pd.DataFrame({
    'cluster_id': unit_ids,
    'Amplitude': [max_abs_per_unit[i, main_channels[i]] for i, _ in enumerate(unit_ids)],
    'ContamPct': 0.0,
    'KSLabel': final_groups,
    'amp': [max_abs_per_unit[i, main_channels[i]] for i, _ in enumerate(unit_ids)],
    'ch': main_channels,
    'depth': depths,
    'fr': [n / total_duration_sec for n in n_spikes],
    'group': final_groups,
    'n_spikes': n_spikes,
    'sh': 0
})

os.makedirs(phy_output_dir, exist_ok=True)
cluster_info.to_csv(os.path.join(phy_output_dir, "cluster_info.tsv"), sep='\t', index=False)
cluster_group = pd.DataFrame({'cluster_id': unit_ids, 'group': final_groups})
cluster_group.to_csv(os.path.join(phy_output_dir, "cluster_group.tsv"), sep='\t', index=False)

print(f"Workflow finished. Final 'good' count: {final_groups.count('good')}")

# =========================================================================
# Migration 1: Kilosort/Phy results -> Y:\...\{mid}\np\{base_name}\{base_name}_imec0
# Copies ap.meta, lf.bin, lf.meta and all sorter output files (existing logic)
# =========================================================================

print("\n--- Starting Migration 1: Kilosort results to _imec0 folder ---")

# Jongwon 2026-03-11
# Previously searched for m*s*r* folders inside raw_ephys_data/probe00/ to get
# folder_base_name, but this folder no longer exists in the new flat structure.
# raw_data_dir now points directly to probe00/ where the raw data files reside.
raw_data_dir = root_path / "raw_ephys_data" / "probe00"

try:
    # Define server target path using folder_base_name parsed from session path
    server_base = get_server_base()
    # Format: Y:\NeuRLab\Data\{mid}\np\{base_name}\{base_name}_imec0
    server_destination_imec0 = server_base / mid_part / "np" / folder_base_name / f"{folder_base_name}_imec0"
    server_destination_imec0.mkdir(parents=True, exist_ok=True)
    print(f"Destination created: {server_destination_imec0}")

    # Copy specific metadata files (skip if already exists with same size)
    transfer_files = ['ap.meta', 'lf.bin', 'lf.meta']
    for ext in transfer_files:
        for source_file in raw_data_dir.glob(f"*{ext}"):
            dest_file = server_destination_imec0 / source_file.name
            if dest_file.exists() and dest_file.stat().st_size == source_file.stat().st_size:
                print(f"  Skipping: {source_file.name} (already exists with same size)")
            else:
                print(f"  Copying: {source_file.name}...")
                shutil.copy2(source_file, dest_file)
                print(f"  Finished: {source_file.name}")

    # Copy all files from Kilosort/Phy output directory to server
    if ks_output_dir.exists():
        print(f"Copying kilosort results from {ks_output_dir} to {server_destination_imec0}...")
        for ks_file in ks_output_dir.iterdir():
            if ks_file.is_file():
                dest_file = server_destination_imec0 / ks_file.name
                try:
                    shutil.copy2(str(ks_file), str(dest_file))
                    if dest_file.exists() and dest_file.stat().st_size == ks_file.stat().st_size:
                        print(f"  Successfully copied: {ks_file.name}")
                    else:
                        print(f"  WARNING: Copy failed silently: {ks_file.name}")
                except Exception as e:
                    print(f"  Error copying {ks_file.name}: {e}")
    else:
        print(f"Warning: Sorter output directory not found at {ks_output_dir}")

except Exception as e:
    print(f"An error occurred during Migration 1: {e}")

# =========================================================================
# Migration 2: Full session backup -> Y:\...\{mid}\np\{base_name}\
# Jongwon 2026-03-26
# Previously, only a subset of files was copied to the server due to storage
# constraints, and raw data was deleted locally after compression. This meant
# re-analysis required re-running the full pipeline from scratch.
# Migration 2 backs up all analysis outputs after compress_raw_data() so that
# any re-analysis can resume from the existing results without re-processing.
#
# Folder rules:
#   kilosort4/          -> full copy
#   probe00/            -> full copy
#   raw_behavior_data/  -> full copy
#   raw_video_data/     -> full copy
#   raw_ephys_data/     -> directory structure only (no files),
#                          EXCEPT *power* / *psd* files which are copied
# =========================================================================

print("\n--- Starting Migration 2: Full session backup ---")



try:
    server_base = get_server_base()
    server_destination_session = server_base / mid_part / "np" / folder_base_name
    server_destination_session.mkdir(parents=True, exist_ok=True)
    print(f"Destination: {server_destination_session}")

    for folder_name in ['kilosort4', 'probe00', 'raw_behavior_data', 'raw_video_data']:
        src = root_path / folder_name
        if src.exists():
            print(f"\nCopying {folder_name}/ ...")
            copy_folder_full(src, server_destination_session / folder_name)
        else:
            print(f"\nSkipping {folder_name}/ (not found locally)")

    src_ephys = root_path / 'raw_ephys_data'
    if src_ephys.exists():
        print(f"\nCopying raw_ephys_data/ (structure + PSD files only) ...")
        copy_raw_ephys_structure_and_psd(src_ephys, server_destination_session / 'raw_ephys_data')
    else:
        print("\nSkipping raw_ephys_data/ (not found locally)")

except Exception as e:
    print(f"An error occurred during Migration 2: {e}")

print("\nAll tasks completed successfully.")