function aiteach_motor_torque_cli(r2, x2, e2, s_min, s_max, n_points, output_path, plot_output_path)
% AITEACH_MOTOR_TORQUE_CLI
% MATLAB CLI bridge for Python backend.

if nargin < 7
    error('aiteach_motor_torque_cli requires 7 arguments.');
end

[slip, torque, max_slip, max_torque, start_torque] = aiteach_motor_torque_curve( ...
    r2, x2, e2, s_min, s_max, n_points);

result = struct();
result.slip = slip;
result.torque = torque;
result.max_slip = max_slip;
result.max_torque = max_torque;
result.start_torque = start_torque;

output_dir = fileparts(output_path);
if ~isempty(output_dir) && ~exist(output_dir, 'dir')
    mkdir(output_dir);
end

json_text = jsonencode(result);
fid = fopen(output_path, 'w');
if fid == -1
    error('Cannot open output file: %s', output_path);
end
cleanup_obj = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, json_text, 'char');

if nargin >= 8 && ~isempty(plot_output_path)
    plot_dir = fileparts(plot_output_path);
    if ~isempty(plot_dir) && ~exist(plot_dir, 'dir')
        mkdir(plot_dir);
    end

    fig = figure('Visible', 'off', 'Color', 'white');
    cleanup_fig = onCleanup(@() close(fig)); %#ok<NASGU>
    plot(slip, torque, 'k-', 'LineWidth', 2.0);
    hold on;
    scatter(max_slip, max_torque, 36, [0.16 0.42 0.88], 'filled');
    xlabel('Slip s');
    ylabel('Torque T');
    title(sprintf('Induction Motor T-s Curve (R_2 = %.3f)', r2));
    grid on;
    box on;
    set(gca, 'FontName', 'Arial', 'LineWidth', 1.0);

    if exist('exportgraphics', 'file') == 2
        exportgraphics(fig, plot_output_path, 'Resolution', 180);
    else
        saveas(fig, plot_output_path);
    end
end
