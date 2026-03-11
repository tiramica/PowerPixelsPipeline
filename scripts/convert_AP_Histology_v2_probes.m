% Convert AP_histology v2 annotation to IBL alignment GUI format
% Written by Jongwon, 2026-03-11
% Extracts CCF coordinates from AP_histology_processing.mat and exports
% each probe annotation as a JSON file compatible with the IBL alignment GUI

% Set bregma coordinates in CCF voxel space (10 um/voxel)
vecBregma = [540, 44, 570];

% Load AP_histology_processing file
[strProbeFile, strProbePath] = uigetfile('*.mat', 'Open AP_histology_processing file');
sLoad = load(fullfile(strProbePath, strProbeFile));
AP_histology_processing = sLoad.AP_histology_processing;

% Loop through each probe annotation
for curr_probe = 1:length(AP_histology_processing.annotation)

    % Extract CCF coordinates across all slices and concatenate into N x 3 matrix
    all_ccf = AP_histology_processing.annotation(curr_probe).vertices_ccf;
    ap = vertcat(all_ccf.ap);
    ml = vertcat(all_ccf.ml);
    dv = vertcat(all_ccf.dv);
    points = [ap, ml, dv];

    % Remove rows with NaN (slices where no points were annotated)
    points = points(~any(isnan(points), 2), :);

    % Convert CCF voxel coordinates to um relative to bregma
    % CCF uses 10 um voxels; reorder axes from (ap, ml, dv) to (ml, ap, dv) for IBL
    matBregmaPoints = (repmat(vecBregma, size(points, 1), 1) - points) * 10;
    matBregmaPoints = [matBregmaPoints(:,3), matBregmaPoints(:,1), matBregmaPoints(:,2)];

    % Save trajectory points as JSON file named after the annotation label
    probe_label = AP_histology_processing.annotation(curr_probe).label;
    sXYZ = struct('xyz_picks', matBregmaPoints);
    out_file = fullfile(strProbePath, [probe_label, '.json']);
    fid = fopen(out_file, 'w');
    fprintf(fid, jsonencode(sXYZ));
    fclose(fid);
    fprintf('Exported %s as %s\n', probe_label, out_file);

end