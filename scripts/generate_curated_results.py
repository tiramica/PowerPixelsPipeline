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


# 1. User Input or Argument Definitions
if len(sys.argv) > 1:
    user_input = sys.argv[1]
else:
    user_input = input(r"root_path (ex: C:\Users\NeuRLab\Data\OPTOTMP\done\20260225): ").strip().replace('"', '').replace("'", "")

root_path = Path(user_input)

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
bombcell_all = np.load(os.path.join(base_path, "clusters.bombcellLabels.npy"))
ibl_all = np.load(os.path.join(base_path, "clusters.iblLabels.npy"))
unit_refine_all = np.load(os.path.join(base_path, "clusters.unitrefineLabels.npy"))
try:
    manual_all = np.load(os.path.join(base_path, "clusters.manualLabels.npy"), allow_pickle=True)
except FileNotFoundError:
    manual_all = np.array([''] * (max(unit_ids) + 1))

final_groups = []
for idx in unit_ids:
    m_label = manual_all[idx]
    b_val = bombcell_all[idx]
    i_val = ibl_all[idx]
    u_val = unit_refine_all[idx]
    
    if m_label and str(m_label).lower() != 'nan' and str(m_label) != '':
        final_groups.append(str(m_label))
    else:
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
cluster_group = pd.DataFrame({'cluster_id': unit_ids,'group': final_groups})
cluster_group.to_csv(os.path.join(phy_output_dir, "cluster_group.tsv"), sep='\t', index=False)

print(f"Workflow finished. Final 'good' count: {final_groups.count('good')}")

# =========================================================================
# NEW: Data Migration and Server Directory Organization
# =========================================================================

print("\n--- Starting Data Migration to Server ---")

# 1. Locate the raw data folder to parse the naming convention
raw_data_dir = root_path / "raw_ephys_data" / "probe00"
search_pattern = str(raw_data_dir / "m*s*r*")
matching_items = glob.glob(search_pattern)

if not matching_items:
    print(f"Error: No folders matching m*s*r* found in {raw_data_dir}")
else:
    # Identify the base name (e.g., m1443s1r2_g0)
    full_name = Path(matching_items[0]).name
    # Assuming the format ends with _t0, we split to get the base session name
    folder_base_name = full_name.split('_t0')[0]
    
    # Extract Mouse ID (mid) from the name (e.g., m1443s1r2 -> 1443)
    try:
        mid_part = folder_base_name.split('s')[0].replace('m', '')
        
        # 2. Define Server Target Path
        # Format: Y:\NeuRLab\Data\{mid}\np\{base_name}\{base_name}_imec0
        server_destination = Path(r"Y:\NeuRLab\Data") / mid_part / "np" / folder_base_name / f"{folder_base_name}_imec0"
        
        # Create directories if they don't exist
        server_destination.mkdir(parents=True, exist_ok=True)
        print(f"Destination created: {server_destination}")

        # 3. Copy specific metadata/bin files (with skip logic for large files)
        transfer_files = ['ap.meta', 'lf.bin', 'lf.meta']
        for ext in transfer_files:
            for source_file in raw_data_dir.glob(f"*{ext}"):
                dest_file = server_destination / source_file.name
                
                if dest_file.exists() and dest_file.stat().st_size == source_file.stat().st_size:
                    print(f"⏭️  Skipping: {source_file.name} (already exists with same size)")
                else:
                    print(f"📦 Copying: {source_file.name}...")
                    shutil.copy2(source_file, dest_file)
                    print(f"✅ Finished: {source_file.name}")

        # 4. Move all files from Kilosort/Phy output directory to the server
        if ks_output_dir.exists():
            print(f"Copying curated results from {ks_output_dir} to server...")
    
            # Ensure server destination exists
            server_destination.mkdir(parents=True, exist_ok=True)
    
            for ks_file in ks_output_dir.iterdir():
                if ks_file.is_file():
                    dest_file = server_destination / ks_file.name
            
                    try:
                        # Use copy2 to preserve metadata. 
                        # This works even if files (like .log) are being used by other processes.
                        shutil.copy2(str(ks_file), str(dest_file))
                        print(f"Successfully copied: {ks_file.name}")
                    except Exception as e:
                        # Just log the error and continue to the next file
                        print(f"⚠️ Error copying {ks_file.name}: {e}")
                
            print("✅ Migration complete. Local copies are preserved.")
        else:
            print(f"Warning: Sorter output directory not found at {ks_output_dir}")

    except Exception as e:
        print(f"An error occurred during migration: {e}")

print("\nAll tasks completed successfully.")

# import pandas as pd
# import numpy as np
# import os
# import spikeinterface.full as si
# import spikeinterface.exporters as se
# from spikeinterface.curation import CurationSorting
# from pathlib import Path

# user_input = input("root_path (ex: D:\\Data\\Project): ").strip()

# root_path = Path(user_input)
# user_input = user_input.replace('"', '').replace("'", "")

# base_path = root_path / "probe00"
# sorting_path = base_path / "sorting"
# ks_output_dir = root_path / "kilosort4" / "probe00" / "sorter_output"
# phy_output_dir = ks_output_dir
# json_path = sorting_path / "spikeinterface_gui" / "curation_data.json"

# # 2. Load Sorting and Check for Unit Changes
# analyzer = si.load_sorting_analyzer(sorting_path)
# curated_sorting = CurationSorting(analyzer.sorting, json_path)

# original_unit_ids = analyzer.sorting.unit_ids
# curated_unit_ids = curated_sorting.sorting.unit_ids

# print(f"Original units: {len(original_unit_ids)}")
# print(f"Curated units: {len(curated_unit_ids)}")

# # -------------------------------------------------------------------------
# # Case Selection: Decide whether to re-compute based on Unit Count
# # -------------------------------------------------------------------------
# if len(original_unit_ids) != len(curated_unit_ids):
#     # CASE 1: Units merged or deleted - Re-compute waveforms/templates via SI
#     print("Changes detected. Running SpikeInterface Re-computation...")
#     actual_curated_sorting = curated_sorting.sorting
#     curated_analyzer = si.create_sorting_analyzer(actual_curated_sorting, analyzer.recording, format="memory")
#     curated_analyzer.compute(["random_spikes", "waveforms", "templates"], n_jobs=-1)
    
#     # Export initial files to Phy (handles templates.npy, spikes_times.npy etc.)
#     se.export_to_phy(curated_analyzer, output_folder=phy_output_dir, 
#                      copy_binary=False, remove_if_exists=True, 
#                      compute_pc_features=False, compute_amplitudes=False, sparsity=None)
    
#     unit_ids = curated_analyzer.unit_ids
#     # SI templates shape: (units, samples, channels)
#     templates = curated_analyzer.get_extension('templates').get_data()
#     abs_templates = np.abs(templates)
#     max_abs_per_unit = np.max(abs_templates, axis=1) # Max along time axis
# else:
#     # CASE 2: No changes - Use Kilosort output directly (Fast)
#     print("No changes. Using Kilosort output directly...")
#     unit_ids = original_unit_ids
#     templates = np.load(os.path.join(ks_output_dir, "templates.npy"))
#     # KS templates shape: (units, samples, channels)
#     abs_templates = np.abs(templates)
#     max_abs_per_unit = np.max(abs_templates, axis=1)

# # -------------------------------------------------------------------------
# # 3. Final Grouping Logic & cluster_info.tsv Generation
# # -------------------------------------------------------------------------

# # Load QC and Manual Labels
# bombcell_all = np.load(os.path.join(base_path, "clusters.bombcellLabels.npy"))
# ibl_all = np.load(os.path.join(base_path, "clusters.iblLabels.npy"))
# unit_refine_all = np.load(os.path.join(base_path, "clusters.unitrefineLabels.npy"))
# try:
#     manual_all = np.load(os.path.join(base_path, "clusters.manualLabels.npy"), allow_pickle=True)
# except FileNotFoundError:
#     manual_all = np.array([''] * (max(unit_ids) + 1))

# # Process logical grouping
# final_groups = []
# for idx in unit_ids:
#     m_label = manual_all[idx]
#     b_val = bombcell_all[idx]
#     i_val = ibl_all[idx]
#     u_val = unit_refine_all[idx]
    
#     if m_label and str(m_label).lower() != 'nan' and str(m_label) != '':
#         final_groups.append(str(m_label))
#     else:
#         # 'good' only if all three metrics pass
#         is_good = (b_val == 1) and (i_val == 1) and (u_val == 1)
#         final_groups.append('good' if is_good else 'mua')

# # Load additional data for metrics
# channel_positions = np.load(os.path.join(ks_output_dir, "channel_positions.npy"))
# spike_clusters = np.load(os.path.join(ks_output_dir, "spike_clusters.npy"))
# spike_times = np.load(os.path.join(ks_output_dir, "spike_times.npy"))

# # Calculate metrics for DataFrame
# main_channels = np.argmax(max_abs_per_unit, axis=1)
# depths = channel_positions[main_channels, 1]
# unique, counts = np.unique(spike_clusters, return_counts=True)
# count_dict = dict(zip(unique, counts))
# n_spikes = [count_dict.get(i, 0) for i in unit_ids]
# total_duration_sec = (spike_times.max() - spike_times.min()) / 30000

# # Build final DataFrame as requested
# cluster_info = pd.DataFrame({
#     'cluster_id': unit_ids,
#     'Amplitude': [max_abs_per_unit[i, main_channels[i]] for i, _ in enumerate(unit_ids)],
#     'ContamPct': 0.0,
#     'KSLabel': final_groups,
#     'amp': [max_abs_per_unit[i, main_channels[i]] for i, _ in enumerate(unit_ids)],
#     'ch': main_channels,
#     'depth': depths,
#     'fr': [n / total_duration_sec for n in n_spikes],
#     'group': final_groups,
#     'n_spikes': n_spikes,
#     'sh': 0
# })

# # Save to TSV
# os.makedirs(phy_output_dir, exist_ok=True)
# cluster_info.to_csv(os.path.join(phy_output_dir, "cluster_info.tsv"), sep='\t', index=False)

# cluster_group = pd.DataFrame({'cluster_id': unit_ids,'group': final_groups})
# cluster_group.to_csv(os.path.join(phy_output_dir, "cluster_group.tsv"), sep='\t', index=False)



# print(f"Workflow finished. Final 'good' count: {final_groups.count('good')}")


