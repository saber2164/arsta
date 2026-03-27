% ARSTA Project - NS-3 Validation
% Reference: Kotaba et al., IEEE GLOBECOM 2022, DOI 10.1109/GLOBECOM48099.2022.9977764
% Power model: 3GPP TR 38.840 V16.0.0
%
% This script loads ns-3 CSV results and compares against analytical predictions
% to validate simulation accuracy.

%% Main script execution
function validate_ns3()
    % Run validation with default paths
    ns3_results_dir = 'results/processed';
    validate(ns3_results_dir, []);
end

%% Main validation function
function validate(ns3_results_dir, ~)
    % Load results/processed/full_results_table.csv
    % For each experiment: compare ns3 energy_mean vs analytical prediction
    % Compute RMSE and R^2
    % Print validation table:
    %   Config | NS3 Energy | Analytical | RMSE | R^2 | Status
    
    fprintf('\n========================================\n');
    fprintf('  ARSTA NS-3 Validation Report\n');
    fprintf('========================================\n\n');
    
    % Load NS-3 results
    results_file = fullfile(ns3_results_dir, 'full_results_table.csv');
    
    if exist(results_file, 'file')
        fprintf('Loading NS-3 results from: %s\n', results_file);
        ns3_data = load_ns3_results(results_file);
    else
        fprintf('WARNING: Results file not found. Using mock data.\n');
        ns3_data = generate_mock_data();
    end
    
    % Get analytical predictions for each configuration
    analytical_data = compute_analytical_predictions(ns3_data);
    
    % Compute validation metrics and print table
    [rmse_total, r2_total, results_table] = compute_validation_metrics(ns3_data, analytical_data);
    
    % Print validation table
    print_validation_table(results_table);
    
    % Print summary statistics
    fprintf('\n--- Overall Validation Summary ---\n');
    fprintf('Total RMSE: %.2f mJ\n', rmse_total);
    fprintf('Total R²: %.4f\n', r2_total);
    
    % Determine overall status
    pass_count = sum([results_table.status] == "PASS");
    warn_count = sum([results_table.status] == "WARNING");
    total_count = length(results_table);
    
    fprintf('Configurations: %d PASS, %d WARNING out of %d total\n', ...
        pass_count, warn_count, total_count);
    
    if r2_total > 0.8 && (pass_count / total_count) > 0.7
        fprintf('VALIDATION STATUS: PASS\n');
    else
        fprintf('VALIDATION STATUS: NEEDS REVIEW\n');
    end
    
    % Generate scatter plot
    generate_validation_scatter(ns3_data, analytical_data, results_table);
    
    fprintf('\n========================================\n');
    fprintf('  Validation Complete\n');
    fprintf('========================================\n');
end

%% Load NS-3 results from CSV
function ns3_data = load_ns3_results(filepath)
    % Read CSV file
    opts = detectImportOptions(filepath);
    data = readtable(filepath, opts);
    
    % Extract relevant columns
    ns3_data = struct();
    ns3_data.experiment = data.experiment;
    ns3_data.config_value = data.config_value;
    ns3_data.scheme = data.scheme;
    ns3_data.energy_mean_mj = data.energy_mean_mj;
    ns3_data.energy_ci_low = data.energy_ci_low;
    ns3_data.energy_ci_high = data.energy_ci_high;
    ns3_data.reduction_pct = data.reduction_pct;
    
    % Filter for ARSTA scheme only (we validate ARSTA predictions)
    arsta_idx = strcmp(data.scheme, 'arsta');
    ns3_data.experiment = ns3_data.experiment(arsta_idx);
    ns3_data.config_value = ns3_data.config_value(arsta_idx);
    ns3_data.scheme = ns3_data.scheme(arsta_idx);
    ns3_data.energy_mean_mj = ns3_data.energy_mean_mj(arsta_idx);
    ns3_data.energy_ci_low = ns3_data.energy_ci_low(arsta_idx);
    ns3_data.energy_ci_high = ns3_data.energy_ci_high(arsta_idx);
    ns3_data.reduction_pct = ns3_data.reduction_pct(arsta_idx);
    
    ns3_data.n_configs = sum(arsta_idx);
    
    fprintf('Loaded %d ARSTA configurations from NS-3 results\n', ns3_data.n_configs);
end

%% Generate mock data for testing when CSV not available
function ns3_data = generate_mock_data()
    fprintf('Generating mock NS-3 data for validation testing...\n');
    
    % Mock experiments matching the analytical model scenarios
    experiments = {'EXP1_timer', 'EXP1_timer', 'EXP1_timer', ...
                   'EXP2_traffic', 'EXP2_traffic', 'EXP2_traffic', ...
                   'EXP3_mobility', 'EXP3_mobility', 'EXP3_mobility'};
    config_values = [10, 20, 50, 0.5, 1.0, 2.0, 0.0, 10.0, 20.0];
    
    % Generate mock energy values (mJ) with some noise
    base_energies = [34000, 34000, 39500, 53000, 34000, 30000, 32000, 36000, 48000];
    noise = randn(1, length(base_energies)) * 2000;
    energy_means = base_energies + noise;
    
    ns3_data = struct();
    ns3_data.experiment = experiments';
    ns3_data.config_value = config_values';
    ns3_data.scheme = repmat({'arsta'}, length(experiments), 1);
    ns3_data.energy_mean_mj = energy_means';
    ns3_data.energy_ci_low = (energy_means - 3000)';
    ns3_data.energy_ci_high = (energy_means + 3000)';
    ns3_data.reduction_pct = 40 + randn(1, length(experiments)) * 5;
    ns3_data.reduction_pct = ns3_data.reduction_pct';
    ns3_data.n_configs = length(experiments);
end

%% Compute analytical predictions using energy_analytical model
function analytical_data = compute_analytical_predictions(ns3_data)
    % Use the analytical model functions to predict energy
    % based on experiment configuration
    
    fprintf('Computing analytical predictions...\n');
    
    n = ns3_data.n_configs;
    analytical_energy = zeros(n, 1);
    
    % Power consumption (mW) and simulation parameters
    P = [5, 15, 900];  % IDLE, INACTIVE, CONNECTED
    dt = 0.1;
    T_sim = 300;
    alpha_ewma = 0.3;
    
    for i = 1:n
        exp_type = ns3_data.experiment{i};
        config_val = ns3_data.config_value(i);
        
        % Determine parameters based on experiment type
        if contains(exp_type, 'timer')
            % EXP1: Inactivity timer sweep
            lambda_pkt = 1.0;  % Default traffic rate
            mu_inact = 1 / config_val;  % Timer in seconds
        elseif contains(exp_type, 'traffic')
            % EXP2: Traffic intensity sweep
            lambda_pkt = config_val;  % packets/s
            mu_inact = 1/10;  % Default 10s timer
        elseif contains(exp_type, 'mobility')
            % EXP3: Mobility sweep - affects transition probabilities
            lambda_pkt = 1.0;
            mu_inact = 1/10;
            % Adjust for mobility (higher mobility = more state changes)
            velocity = config_val;  % m/s
            % Mobility factor increases connected time slightly
            if velocity > 15
                alpha_ewma = 0.2;  % Less aggressive at high speed
            elseif velocity > 5
                alpha_ewma = 0.3;
            else
                alpha_ewma = 0.35;  % More aggressive at low speed
            end
        elseif contains(exp_type, 'density')
            % EXP4: UE density sweep
            lambda_pkt = 1.0;
            mu_inact = 1/10;
            % Density affects contention but not directly energy model
        elseif contains(exp_type, 'rna')
            % EXP5: RNA area size sweep
            lambda_pkt = 1.0;
            mu_inact = 1/10;
            % RNA size affects paging but modeled as transition probability
        else
            % Default parameters
            lambda_pkt = 1.0;
            mu_inact = 1/10;
        end
        
        % Build transition matrix for ARSTA
        P_arsta = build_transition_matrix(lambda_pkt, mu_inact, alpha_ewma, 'arsta');
        
        % Compute steady-state energy (mW)
        [energy_mw, ~] = compute_energy(P_arsta, dt, T_sim);
        
        % Convert to total energy over simulation time (mJ)
        % energy_mw is average power; multiply by time to get total energy
        analytical_energy(i) = energy_mw * T_sim;  % mW * s = mJ
        
        % Reset alpha for next iteration
        alpha_ewma = 0.3;
    end
    
    analytical_data = struct();
    analytical_data.energy_mj = analytical_energy;
end

%% Compute energy from transition matrix (from energy_analytical.m)
function [energy_mw, state_dist] = compute_energy(P_matrix, ~, ~)
    % P_matrix: 3x3 transition probability matrix
    % Returns: mean power in mW, steady-state distribution vector
    
    % Power consumption for each state (mW)
    P = [5, 15, 900];  % IDLE, INACTIVE, CONNECTED
    
    % Compute steady-state distribution using eigenvalue method
    [V, D] = eig(P_matrix');
    
    % Find eigenvalue closest to 1
    eigenvalues = diag(D);
    [~, idx] = min(abs(eigenvalues - 1));
    
    % Extract and normalize the corresponding eigenvector
    state_dist = abs(V(:, idx));
    state_dist = state_dist / sum(state_dist);
    state_dist = state_dist';  % Row vector
    
    % Compute mean energy consumption
    energy_mw = sum(state_dist .* P);
end

%% Build transition probability matrix (from energy_analytical.m)
function P = build_transition_matrix(lambda_pkt, mu_inact, alpha_ewma, scheme)
    % lambda_pkt: packet arrival rate (packets/s)
    % mu_inact: 1/inactivity_timer
    % alpha_ewma: EWMA smoothing factor (0 for baseline, 0.3 for ARSTA)
    % scheme: 'baseline' or 'arsta'
    
    dt = 0.1;  % Time step
    
    % Base transition rates
    p_idle_to_inactive = 0.01;
    p_idle_to_connected = min(0.95, lambda_pkt * dt);
    p_inactive_to_idle = mu_inact * dt * 0.5;
    p_inactive_to_connected = min(0.8, lambda_pkt * dt * 0.8);
    p_connected_to_inactive = mu_inact * dt;
    p_connected_to_idle = 0.001;
    
    % Apply ARSTA modifications
    if strcmp(scheme, 'arsta')
        arsta_factor = 1 + alpha_ewma * 2;
        p_connected_to_inactive = min(0.8, p_connected_to_inactive * arsta_factor);
        p_inactive_to_idle = min(0.5, p_inactive_to_idle * (1 + alpha_ewma * 0.5));
    end
    
    % Ensure valid probabilities
    p_idle_stay = max(0, 1 - p_idle_to_inactive - p_idle_to_connected);
    p_inactive_stay = max(0, 1 - p_inactive_to_idle - p_inactive_to_connected);
    p_connected_stay = max(0, 1 - p_connected_to_inactive - p_connected_to_idle);
    
    % Build transition matrix
    P = [
        p_idle_stay,        p_idle_to_inactive,      p_idle_to_connected;
        p_inactive_to_idle, p_inactive_stay,         p_inactive_to_connected;
        p_connected_to_idle, p_connected_to_inactive, p_connected_stay
    ];
    
    % Normalize rows
    for i = 1:3
        P(i,:) = P(i,:) / sum(P(i,:));
    end
end

%% Compute validation metrics
function [rmse_total, r2_total, results_table] = compute_validation_metrics(ns3_data, analytical_data)
    n = ns3_data.n_configs;
    
    ns3_energy = ns3_data.energy_mean_mj;
    analytical_energy = analytical_data.energy_mj;
    
    % Compute per-configuration metrics
    deviation_pct = abs(ns3_energy - analytical_energy) ./ ns3_energy * 100;
    squared_errors = (ns3_energy - analytical_energy).^2;
    
    % Overall RMSE
    rmse_total = sqrt(mean(squared_errors));
    
    % Overall R^2
    ss_res = sum(squared_errors);
    ss_tot = sum((ns3_energy - mean(ns3_energy)).^2);
    r2_total = 1 - (ss_res / ss_tot);
    
    % Build results table structure
    results_table = struct();
    results_table.experiment = ns3_data.experiment;
    results_table.config_value = ns3_data.config_value;
    results_table.ns3_energy = ns3_energy;
    results_table.analytical_energy = analytical_energy;
    results_table.deviation_pct = deviation_pct;
    results_table.rmse = sqrt(squared_errors);  % Per-config RMSE
    
    % Per-config R^2 (using sliding window would need more data, so use deviation)
    % Assign status based on deviation threshold
    status = strings(n, 1);
    for i = 1:n
        if deviation_pct(i) < 15
            status(i) = "PASS";
        else
            status(i) = "WARNING";
        end
    end
    results_table.status = status;
end

%% Print validation table
function print_validation_table(results_table)
    fprintf('\n--- Validation Results Table ---\n');
    fprintf('%-15s | %10s | %12s | %12s | %10s | %8s\n', ...
        'Config', 'NS3 (mJ)', 'Analytical', 'Deviation%', 'RMSE', 'Status');
    fprintf('%s\n', repmat('-', 1, 80));
    
    n = length(results_table.experiment);
    for i = 1:n
        % Create config string
        exp_short = strrep(results_table.experiment{i}, 'EXP', 'E');
        exp_short = strrep(exp_short, '_timer', 'T');
        exp_short = strrep(exp_short, '_traffic', 'R');
        exp_short = strrep(exp_short, '_mobility', 'M');
        exp_short = strrep(exp_short, '_density', 'D');
        exp_short = strrep(exp_short, '_rna', 'A');
        config_str = sprintf('%s=%.1f', exp_short, results_table.config_value(i));
        
        % Print row
        fprintf('%-15s | %10.1f | %12.1f | %11.1f%% | %10.1f | %8s\n', ...
            config_str, ...
            results_table.ns3_energy(i), ...
            results_table.analytical_energy(i), ...
            results_table.deviation_pct(i), ...
            results_table.rmse(i), ...
            results_table.status(i));
    end
    fprintf('%s\n', repmat('-', 1, 80));
end

%% Generate validation scatter plot
function generate_validation_scatter(ns3_data, analytical_data, results_table)
    fprintf('\nGenerating validation scatter plot...\n');
    
    % Create figure
    fig = figure('Position', [100, 100, 800, 700], 'Visible', 'off');
    
    % Set font properties for IEEE style
    set(0, 'DefaultAxesFontName', 'Times New Roman');
    set(0, 'DefaultAxesFontSize', 11);
    
    ns3_energy = ns3_data.energy_mean_mj;
    analytical_energy = analytical_data.energy_mj;
    
    % Determine axis limits
    all_energy = [ns3_energy; analytical_energy];
    min_e = min(all_energy) * 0.8;
    max_e = max(all_energy) * 1.2;
    
    % Plot 1:1 reference line
    hold on;
    plot([min_e, max_e], [min_e, max_e], 'k--', 'LineWidth', 1.5, ...
        'DisplayName', '1:1 Line (Perfect Agreement)');
    
    % Plot ±15% deviation bands
    plot([min_e, max_e], [min_e * 0.85, max_e * 0.85], 'r:', 'LineWidth', 1, ...
        'DisplayName', '±15% Deviation');
    plot([min_e, max_e], [min_e * 1.15, max_e * 1.15], 'r:', 'LineWidth', 1, ...
        'HandleVisibility', 'off');
    
    % Plot data points with color coding by status
    pass_idx = results_table.status == "PASS";
    warn_idx = results_table.status == "WARNING";
    
    if any(pass_idx)
        scatter(analytical_energy(pass_idx), ns3_energy(pass_idx), 100, ...
            'o', 'MarkerFaceColor', [0.2, 0.7, 0.2], 'MarkerEdgeColor', 'k', ...
            'LineWidth', 1.5, 'DisplayName', 'PASS (<15% dev.)');
    end
    
    if any(warn_idx)
        scatter(analytical_energy(warn_idx), ns3_energy(warn_idx), 100, ...
            '^', 'MarkerFaceColor', [0.9, 0.5, 0.1], 'MarkerEdgeColor', 'k', ...
            'LineWidth', 1.5, 'DisplayName', 'WARNING (≥15% dev.)');
    end
    
    hold off;
    
    % Labels and formatting
    xlabel('Analytical Energy (mJ)', 'FontName', 'Times New Roman', 'FontSize', 12);
    ylabel('NS-3 Simulated Energy (mJ)', 'FontName', 'Times New Roman', 'FontSize', 12);
    title('ARSTA: NS-3 vs Analytical Model Validation', ...
        'FontName', 'Times New Roman', 'FontSize', 14, 'FontWeight', 'bold');
    
    % Compute overall metrics for annotation
    ss_res = sum((ns3_energy - analytical_energy).^2);
    ss_tot = sum((ns3_energy - mean(ns3_energy)).^2);
    r2 = 1 - (ss_res / ss_tot);
    rmse = sqrt(mean((ns3_energy - analytical_energy).^2));
    
    % Add annotation with metrics
    annotation_text = sprintf('R² = %.4f\nRMSE = %.1f mJ\nN = %d configs', ...
        r2, rmse, length(ns3_energy));
    text(max_e * 0.65, min_e * 1.2, annotation_text, ...
        'FontName', 'Times New Roman', 'FontSize', 11, ...
        'BackgroundColor', 'white', 'EdgeColor', 'black');
    
    legend('Location', 'northwest', 'FontName', 'Times New Roman');
    grid on;
    xlim([min_e, max_e]);
    ylim([min_e, max_e]);
    axis square;
    
    % Ensure output directory exists
    output_dir = 'results/figures';
    if ~exist(output_dir, 'dir')
        mkdir(output_dir);
    end
    
    % Save figure
    output_path = fullfile(output_dir, 'validation_scatter.pdf');
    
    try
        exportgraphics(fig, output_path, 'ContentType', 'vector', 'Resolution', 300);
        fprintf('Scatter plot saved to: %s\n', output_path);
    catch ME
        % Fallback for older MATLAB versions
        fprintf('Warning: exportgraphics failed (%s). Trying print...\n', ME.message);
        print(fig, output_path, '-dpdf', '-r300');
        fprintf('Scatter plot saved to: %s (using print)\n', output_path);
    end
    
    close(fig);
end

%% Run main function when script is executed
validate_ns3();
