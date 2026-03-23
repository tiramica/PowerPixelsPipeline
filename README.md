![GitHub License](https://img.shields.io/github/license/NeuroNetMem/PowerPixelsPipeline)
# Power Pixels: A turnkey pipeline for processing of Neuropixel recordings ⚡
<img src="https://github.com/user-attachments/assets/37d9003a-788a-43d2-a5a6-ff4d7a29f780" alt="PowerPixels logo" width="30%" align="right" vspace="20"/>

> **NeuRLab fork** — This is a lab-specific fork of the [original PowerPixelsPipeline](https://github.com/NeuroNetMem/PowerPixelsPipeline) by Guido Meijer. Several scripts have been modified to fit NeuRLab's data organization and workflow. See [Lab-specific modifications](#lab-specific-modifications-neurlab) for details.

📄 Please cite the [Peer Community Journal](https://peercommunityjournal.org/articles/10.24072/pcjournal.679/) if you use the pipeline 📄 ⭐ And star the original repository! ⭐

The Power Pixels pipeline combines several packages and workflows into one end-to-end pipeline. It supports Neuropixel 1.0 and 2.0 probes recorded on a National Instruments system using SpikeGLX or OpenEphys.

This pipeline relies on these amazing open-source projects:
- [SpikeInterface](https://spikeinterface.readthedocs.io)
- [ibllib](https://github.com/int-brain-lab/ibllib)
- [Kilosort](https://github.com/MouseLand/Kilosort)
- [AP_histology](https://github.com/petersaj/AP_histology)
- [Universal Probe Finder](https://github.com/JorritMontijn/UniversalProbeFinder)
- [Bombcell](https://github.com/Julie-Fabre/bombcell)
- [UnitRefine](https://huggingface.co/SpikeInterface/UnitRefine_sua_mua_classifier)
- [neuroconv](https://neuroconv.readthedocs.io/en/stable/)

## Description of the pipeline elements

![pipeline process](https://github.com/user-attachments/assets/1a6b70e7-6f5f-4c3f-83d8-1de4c1d5ccce)

The pipeline contains the following elements:
- **Phase shift correction**: channels on a Neuropixel probe are not recorded simultaneously, there is a small delay in the order of microseconds between the acquisition of a block of channels. Correcting for this small delay greatly improves artifact removal.
- **Remove bad channels**: bad channels are detected by looking at both coherence with other channels and PSD power in the high-frequency range, then they are interpolated using neighboring channels. Channels outside of the brain are removed.
- **Artifact removal**: the user can decide whether to apply common average referencing, local average referencing (default), or destriping to remove electrical artifacts and noise.
- **High-frequency noise**: high-frequency noise in specific frequency bands is automatically filtered out using notch filters targeted to detected peaks in the power spectrum.
- **Spike sorting**: a spike sorting algorithm is used to detect spikes and sort them into units. SpikeInterface supports many [spike sorters](https://spikeinterface.readthedocs.io/en/latest/modules/sorters.html#supported-spike-sorters) out of the box (recommended: Kilosort).
- **Automatic classification of single neurons**: The pipeline runs three algorithms for automatic classification of good single units: Bombcell, UnitRefine and the IBL quality criteria.
- **Synchronization**: each Neuropixel probe and the BNC breakout box has their own clock. This means one has to synchronize the spike times between the probes (if you use more than one) and the synchronization channels which carry timestamps of events (for example: behavioral events or pulses from a camera).
- **Compression**: the raw binary file is compressed using *zarr* or *mtscomp* compression which results in a 2-3x reduction in file size.
- **Histological tracing**: the fluorescent tracks of the probes are traced using AP_histology or Universal Probe Finder.
- **Ephys-histology alignment**: the brain regions along the probe, inferred from the tracing, are aligned to electrophysiological features.

---

## Lab-specific modifications (NeuRLab)

The following scripts have been modified or added for NeuRLab's workflow. All changes are annotated with `% Jongwon YYYY-MM-DD` or `# Jongwon YYYY-MM-DD` comments in the code.

### 1. `scripts/run_pipeline_spikeglx.py` — Flat folder structure support

The original pipeline expected data organized as `DATA_FOLDER/mouse_id/date/raw_ephys_data/`. In NeuRLab, session folders are placed directly in `DATA_FOLDER` with a flat structure:

```
DATA_FOLDER/
├── m408s1r1_g0/
│   ├── m408s1r1_g0_imec0/
│   └── process_me.flag
├── m408s1r2_g0/
│   └── ...
```

The script now uses `iterdir()` instead of `os.walk()` to search only one level deep, and a `prepare_raw_ephys_folder()` helper function automatically creates the `raw_ephys_data/` folder and renames `imec*` folders to `probe0x` before the Pipeline class is called.

After automatic curation, `generate_curated_results.py` is called automatically via `subprocess`, passing `session_path` as an argument.

### 2. `scripts/create_flags.py` — Replaces `prepare_sessions.py`

Instead of the original `prepare_sessions.py`, NeuRLab uses `create_flags.py` to create `process_me.flag` files. It reads `DATA_FOLDER` from `config/settings.json` and creates flags only for session folders whose names start with `m` (e.g. `m408s1r1_g0`).

```bash
python scripts/create_flags.py
```

### 3. `scripts/convert_AP_Histology_v2_probes.m` — AP_histology v2 compatibility

The original `convert_AP_Histology_probes.m` was written for AP_histology v1. This replacement script (`convert_AP_Histology_v2_probes.m`) reads the `AP_histology_processing.mat` output from AP_histology v2, extracts CCF coordinates (`ap`, `ml`, `dv`) from the `annotation` struct, converts them to microns relative to bregma, and exports one `xyz_picks.json` per probe in the format expected by the IBL alignment GUI.

Usage: run in MATLAB and select the `AP_histology_processing.mat` file when prompted.

### 4. `scripts/generate_curated_results.py` — Curated results export and server migration

This script handles the final steps after spike sorting and automated curation are complete. It can be run in two modes:

**Automatic**: called at the end of `run_pipeline_spikeglx.py` with `session_path` as a command-line argument.

**Manual**: run directly after performing manual curation in the SpikeInterface GUI to regenerate `cluster_info.tsv` / `cluster_group.tsv` and re-migrate results to the server.

```bash
python scripts/generate_curated_results.py
# Enter session path when prompted, e.g.: D:\Data\m1443s1r2_g0
```

The script applies the following unit classification logic (in priority order):

1. If a **manual label** was set in the SpikeInterface GUI → use it
2. Otherwise, a unit is marked `good` only if **all three** automated QC metrics agree (Bombcell = 1, IBL = 1, UnitRefine = 1); otherwise `mua`

After classification, results are migrated to the lab server at:
`Y:\NeuRLab\Data\{mouse_id}\np\{session_name}\{session_name}_imec0`

---

## Installation

It is recommended to install Power Pixels in an Anaconda or Miniforge environment.
1. Install [Anaconda](https://www.anaconda.com/) or [Miniforge](https://github.com/conda-forge/miniforge) — Miniforge is the recommended option
2. Open the Anaconda or Miniforge prompt
3. Create a new environment: `conda create -n powerpixels python=3.10 git`
4. Activate the environment: `conda activate powerpixels`
5. Clone this repository: `git clone https://github.com/tiramica/PowerPixelsPipeline.git`
6. Install PowerPixels: `cd PowerPixelsPipeline && pip install -e .`
7. Install `iblapps`: `git clone https://github.com/int-brain-lab/iblapps && pip install -e iblapps`

### Spike sorting

_Option 1: local installation of Kilosort4_

Kilosort4 is already installed with PowerPixels. To enable GPU support:
1. `pip uninstall torch`
2. `pip3 install torch --index-url https://download.pytorch.org/whl/cu118`
3. Verify: `ipython` → `import torch; torch.cuda.is_available()`

_Option 2: run spike sorter in Docker_
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Create an account on [Docker Hub](https://hub.docker.com/)
3. Install WSL2: open PowerShell and type `wsl --install`

### Probe tracing

Tracing is done with [AP_histology v2](https://github.com/petersaj/AP_histology) in MATLAB. A MATLAB license is required.

---

## First time use

1. Open Anaconda/Miniforge prompt and activate the environment: `conda activate powerpixels`
2. Run `powerpixels-setup` to generate config files
3. Open `config/settings.json` and fill in your settings
4. Open `config/wiring/nidq.wiring.json` and fill in your synchronization channels (if using a BNC breakout box)
5. (Optional) Adjust spike sorter parameters in `config/sorter_params/`
6. (Optional) Adjust Bombcell and IBL QC parameters in `config/`

## Settings

- `SPIKE_SORTER`: which spike sorter to use (any sorter supported by SpikeInterface)
- `IDENTIFIER`: text appended to the final data folder to distinguish multiple sorting runs
- `DATA_FOLDER`: path to the top-level folder where session folders are stored
- `SINGLE_SHANK`: artifact removal for single-shank probes (`car_global`, `car_local`, `destripe`)
- `MULTI_SHANK`: artifact removal for multi-shank probes
- `LOCAL_RADIUS`: *(car_local only)* annulus in µm around each channel (inner, outer diameter)
- `PEAK_THRESHOLD`: threshold for peak detection in power spectrum for notch filtering
- `USE_NIDAQ`: whether you use a BNC breakout box with synchronization channels
- `USE_DOCKER`: whether to run spike sorting in a Docker container
- `COMPRESS_RAW_DATA`: whether to compress raw data
- `COMPRESSION`: compression method (`zarr` or `mtscomp`)
- `NWB_EXPORT`: whether to export spike sorting results as an NWB file
- `N_CORES`: number of CPUs for preprocessing (`-1` = all)

---

## Folder structure

Session folders should be placed directly in `DATA_FOLDER`. Inside each session folder, the raw SpikeGLX output (`*_imec0` folder) should be present along with a `process_me.flag` file.

```
DATA_FOLDER/
└── m408s1r1_g0/
    ├── m408s1r1_g0_imec0/   ← SpikeGLX output
    └── process_me.flag
```

The pipeline automatically creates `raw_ephys_data/` and reorganizes the folder structure internally. You do not need to do this manually.

To create `process_me.flag` files for all session folders starting with `m`:

```bash
python scripts/create_flags.py
```

---

## Usage workflow

1. Place your SpikeGLX session folder (e.g. `m408s1r1_g0`) directly in `DATA_FOLDER`.
2. Create flag files: `python scripts/create_flags.py`
3. Start the pipeline: `python scripts/run_pipeline_spikeglx.py`
   - The pipeline will search `DATA_FOLDER` for `process_me.flag` files and process each session.
   - After spike sorting and automated curation, `generate_curated_results.py` runs automatically.
   - Results are migrated to the lab server at `Y:\NeuRLab\Data\`.
   - Best to run overnight.
4. After histology, open MATLAB and run AP_histology v2 to trace probe tracts.
5. Convert the tracing to IBL format by running `scripts/convert_AP_Histology_v2_probes.m` in MATLAB. Select the `AP_histology_processing.mat` file when prompted. One `<probe_label>.json` file will be saved per probe.
6. Move each `.json` file to the corresponding probe folder created by the pipeline and rename it `xyz_picks.json`.
7. Launch the alignment GUI:
   ```bash
   python iblapps/atlaselectrophysiology/ephys_atlas_gui.py -o True
   ```
   See [usage instructions](https://github.com/int-brain-lab/iblapps/wiki/2.-Usage-instructions).
8. After alignment, click Upload. The final channel locations and brain regions are saved in `channel_locations.json`.
9. (Optional) Manual curation in SpikeInterface GUI:
   ```python
   from powerpixels import manual_curation
   manual_curation("path/to/sorting/results")
   ```
   After manual curation, re-run `generate_curated_results.py` to regenerate `cluster_info.tsv` / `cluster_group.tsv` and re-migrate to the server.
10. Load your neural data:
    ```python
    from powerpixels import load_neural_data
    spikes, clusters, channels = load_neural_data(session_path, probe)
    ```
    Filter by automated curation labels:

    | Label array | Values |
    |---|---|
    | `clusters['bombcell_label']` | 0=noise, 1=good SU, 2=MUA, 3=non-somatic |
    | `clusters['unitrefine_label']` | 0=MUA/noise, 1=good SU |
    | `clusters['ibl_label']` | 0=noise, 0.33–0.66=MUA, 1=good SU |
    | `clusters['kilosort_label']` | 0=MUA/noise, 1=good SU |

    Or pass `keep_units='bombcell'`, `'unitrefine'`, `'ibl'`, or `'kilosort'` to `load_neural_data`.

---

## Data output

After the pipeline completes, the session folder will contain:

```
m408s1r1_g0/
├── raw_ephys_data/probe00/     ← raw/compressed data
├── probe00/                    ← ALF-format output (spikes, clusters, channels)
│   └── sorting/                ← SpikeInterface sorting analyzer
└── kilosort4/probe00/sorter_output/  ← Kilosort output + cluster_info.tsv
```

Data is also migrated to the server at:
`Y:\NeuRLab\Data\{mouse_id}\np\{session_name}\{session_name}_imec0`

For ALF dataset documentation, see [this guide](https://docs.google.com/document/d/1OqIqqakPakHXRAwceYLwFY9gOrm8_P62XIfCTnHwstg/).
