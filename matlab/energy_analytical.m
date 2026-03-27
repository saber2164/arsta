% ARSTA Project - Analytical Model
% Reference: Kotaba et al., IEEE GLOBECOM 2022, DOI 10.1109/GLOBECOM48099.2022.9977764
% Power model: 3GPP TR 38.840 V16.0.0
%
% Discrete-time Markov chain analytical energy model for 5G NR UE
% States: IDLE(1), INACTIVE(2), CONNECTED(3)
% Power consumption (mW): P = [5, 15, 900]

%% Main script execution
function energy_analytical()
    % Power consumption for each state (mW)
    P = [5, 15, 900];  % IDLE, INACTIVE, CONNECTED
    
    % Default parameters
    dt = 0.1;           % Time step (seconds)
    T_sim = 300;        % Simulation duration (seconds)
    mu_inact = 1/10;    % Default inactivity timer = 10s
    
    % Lambda values for comparison
    lambda_vals = [0.1, 0.5, 1.0, 2.0, 5.0];
    
    % Run comparison
    [energy_reduction, ~] = compare_schemes(lambda_vals, mu_inact);
    
    % Generate and save figure
    generate_figure(lambda_vals, mu_inact, dt, T_sim, P);
    
    fprintf('Analytical model completed.\n');
    fprintf('Mean energy reduction: %.2f%%\n', mean(energy_reduction));
end

%% Compute energy from transition matrix
function [energy_mw, state_dist] = compute_energy(P_matrix, dt, T_sim)
    % P_matrix: 3x3 transition probability matrix
    % dt: time step in seconds (use 0.1)
    % T_sim: simulation duration (300)
    % Returns: mean power in mW, steady-state distribution vector
    
    % Power consumption for each state (mW)
    P = [5, 15, 900];  % IDLE, INACTIVE, CONNECTED
    
    % Compute steady-state distribution using eigenvalue method
    % Steady state satisfies: pi * P = pi, sum(pi) = 1
    
    % Method: Find left eigenvector corresponding to eigenvalue 1
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

%% Build transition probability matrix
function P = build_transition_matrix(lambda_pkt, mu_inact, alpha_ewma, scheme)
    % lambda_pkt: packet arrival rate (packets/s)
    % mu_inact: 1/inactivity_timer
    % alpha_ewma: EWMA smoothing factor (0 for baseline, 0.3 for ARSTA)
    % scheme: 'baseline' or 'arsta'
    % For ARSTA: increase P(CONNECTED→INACTIVE) by factor (1 + alpha_ewma * 2)
    
    % Convert rates to probabilities for discrete time step
    dt = 0.1;  % Time step
    
    % Base transition rates (per second)
    % From IDLE: wake up on paging or activity
    p_idle_to_inactive = 0.01;  % Low probability of wake-up
    p_idle_to_connected = min(0.95, lambda_pkt * dt);  % Activity triggers connection
    
    % From INACTIVE: either go idle (timeout) or connected (activity)
    p_inactive_to_idle = mu_inact * dt * 0.5;  % Decay to IDLE
    p_inactive_to_connected = min(0.8, lambda_pkt * dt * 0.8);  % Activity
    
    % From CONNECTED: stay connected or release
    p_connected_to_inactive = mu_inact * dt;  % Inactivity timer expiry
    p_connected_to_idle = 0.001;  % Very rare direct to IDLE
    
    % Apply ARSTA modifications
    if strcmp(scheme, 'arsta')
        % ARSTA increases early transition to INACTIVE state
        % by predicting idle periods and triggering early release
        arsta_factor = 1 + alpha_ewma * 2;
        p_connected_to_inactive = min(0.8, p_connected_to_inactive * arsta_factor);
        
        % Also slightly reduce time in INACTIVE due to better prediction
        p_inactive_to_idle = min(0.5, p_inactive_to_idle * (1 + alpha_ewma * 0.5));
    end
    
    % Ensure probabilities are valid
    p_idle_stay = max(0, 1 - p_idle_to_inactive - p_idle_to_connected);
    p_inactive_stay = max(0, 1 - p_inactive_to_idle - p_inactive_to_connected);
    p_connected_stay = max(0, 1 - p_connected_to_inactive - p_connected_to_idle);
    
    % Build transition matrix (rows = from state, cols = to state)
    % States: 1=IDLE, 2=INACTIVE, 3=CONNECTED
    P = [
        p_idle_stay,        p_idle_to_inactive,      p_idle_to_connected;
        p_inactive_to_idle, p_inactive_stay,         p_inactive_to_connected;
        p_connected_to_idle, p_connected_to_inactive, p_connected_stay
    ];
    
    % Normalize rows to ensure valid probability matrix
    for i = 1:3
        P(i,:) = P(i,:) / sum(P(i,:));
    end
end

%% Compare baseline vs ARSTA schemes
function [energy_reduction, p_value] = compare_schemes(lambda_vals, mu_inact)
    % Sweep lambda_pkt over [0.1, 0.5, 1.0, 2.0, 5.0] packets/s
    % For each lambda: compute energy for baseline and ARSTA
    % Return array of reduction percentages
    
    dt = 0.1;
    T_sim = 300;
    alpha_ewma = 0.3;  % Default ARSTA smoothing factor
    
    n_lambda = length(lambda_vals);
    energy_baseline = zeros(1, n_lambda);
    energy_arsta = zeros(1, n_lambda);
    energy_reduction = zeros(1, n_lambda);
    
    for i = 1:n_lambda
        lambda = lambda_vals(i);
        
        % Baseline (no EWMA prediction)
        P_baseline = build_transition_matrix(lambda, mu_inact, 0, 'baseline');
        [energy_baseline(i), ~] = compute_energy(P_baseline, dt, T_sim);
        
        % ARSTA with EWMA prediction
        P_arsta = build_transition_matrix(lambda, mu_inact, alpha_ewma, 'arsta');
        [energy_arsta(i), ~] = compute_energy(P_arsta, dt, T_sim);
        
        % Compute reduction percentage
        energy_reduction(i) = (energy_baseline(i) - energy_arsta(i)) / energy_baseline(i) * 100;
    end
    
    % Statistical test (paired t-test)
    [~, p_value] = ttest(energy_baseline, energy_arsta);
    
    fprintf('\n=== Energy Comparison Results ===\n');
    fprintf('Lambda (pkt/s) | Baseline (mW) | ARSTA (mW) | Reduction (%%)\n');
    fprintf('------------------------------------------------------------\n');
    for i = 1:n_lambda
        fprintf('%14.1f | %13.2f | %10.2f | %12.2f\n', ...
            lambda_vals(i), energy_baseline(i), energy_arsta(i), energy_reduction(i));
    end
    fprintf('------------------------------------------------------------\n');
    fprintf('Mean reduction: %.2f%%, p-value: %.4f\n', mean(energy_reduction), p_value);
end

%% Generate figure with 4 subplots
function generate_figure(lambda_vals, mu_inact_default, dt, T_sim, P)
    % Create figure
    fig = figure('Position', [100, 100, 1200, 900]);
    
    % Set font properties for IEEE style
    set(0, 'DefaultAxesFontName', 'Times New Roman');
    set(0, 'DefaultAxesFontSize', 11);
    
    alpha_ewma_default = 0.3;
    
    %% Subplot 1: Energy vs lambda_pkt (baseline vs ARSTA)
    subplot(2,2,1);
    
    energy_baseline = zeros(1, length(lambda_vals));
    energy_arsta = zeros(1, length(lambda_vals));
    
    for i = 1:length(lambda_vals)
        lambda = lambda_vals(i);
        P_baseline = build_transition_matrix(lambda, mu_inact_default, 0, 'baseline');
        P_arsta = build_transition_matrix(lambda, mu_inact_default, alpha_ewma_default, 'arsta');
        [energy_baseline(i), ~] = compute_energy(P_baseline, dt, T_sim);
        [energy_arsta(i), ~] = compute_energy(P_arsta, dt, T_sim);
    end
    
    plot(lambda_vals, energy_baseline, 'b-o', 'LineWidth', 2, 'MarkerSize', 8, 'DisplayName', 'Baseline');
    hold on;
    plot(lambda_vals, energy_arsta, 'r-s', 'LineWidth', 2, 'MarkerSize', 8, 'DisplayName', 'ARSTA');
    hold off;
    
    xlabel('Packet Arrival Rate (packets/s)', 'FontName', 'Times New Roman');
    ylabel('Mean Power (mW)', 'FontName', 'Times New Roman');
    title('(a) Energy vs Packet Arrival Rate', 'FontName', 'Times New Roman');
    legend('Location', 'southeast', 'FontName', 'Times New Roman');
    grid on;
    xlim([0, max(lambda_vals) * 1.1]);
    
    %% Subplot 2: State distribution pie chart for ARSTA at lambda=0.5
    subplot(2,2,2);
    
    lambda_pie = 0.5;
    P_arsta_pie = build_transition_matrix(lambda_pie, mu_inact_default, alpha_ewma_default, 'arsta');
    [~, state_dist] = compute_energy(P_arsta_pie, dt, T_sim);
    
    labels = {'IDLE (5mW)', 'INACTIVE (15mW)', 'CONNECTED (900mW)'};
    colors = [0.2 0.6 0.2; 0.9 0.7 0.1; 0.8 0.2 0.2];
    
    pie_handle = pie(state_dist);
    
    % Set colors and labels
    for i = 1:length(state_dist)
        pie_handle(2*i-1).FaceColor = colors(i,:);
        pie_handle(2*i).String = sprintf('%s\n%.1f%%', labels{i}, state_dist(i)*100);
        pie_handle(2*i).FontName = 'Times New Roman';
        pie_handle(2*i).FontSize = 9;
    end
    
    title(sprintf('(b) ARSTA State Distribution (\\lambda=%.1f pkt/s)', lambda_pie), ...
        'FontName', 'Times New Roman');
    
    %% Subplot 3: Energy reduction % vs inactivity_timer (5,10,20,30s)
    subplot(2,2,3);
    
    inact_timers = [5, 10, 20, 30];
    reduction_vs_timer = zeros(1, length(inact_timers));
    
    lambda_test = 1.0;  % Fixed lambda for this test
    
    for i = 1:length(inact_timers)
        mu_inact = 1 / inact_timers(i);
        P_baseline = build_transition_matrix(lambda_test, mu_inact, 0, 'baseline');
        P_arsta = build_transition_matrix(lambda_test, mu_inact, alpha_ewma_default, 'arsta');
        [e_baseline, ~] = compute_energy(P_baseline, dt, T_sim);
        [e_arsta, ~] = compute_energy(P_arsta, dt, T_sim);
        reduction_vs_timer(i) = (e_baseline - e_arsta) / e_baseline * 100;
    end
    
    bar(inact_timers, reduction_vs_timer, 0.6, 'FaceColor', [0.3 0.5 0.8]);
    xlabel('Inactivity Timer (s)', 'FontName', 'Times New Roman');
    ylabel('Energy Reduction (%)', 'FontName', 'Times New Roman');
    title('(c) Energy Reduction vs Inactivity Timer', 'FontName', 'Times New Roman');
    grid on;
    ylim([0, max(reduction_vs_timer) * 1.3]);
    
    % Add value labels on bars
    for i = 1:length(inact_timers)
        text(inact_timers(i), reduction_vs_timer(i) + 1, sprintf('%.1f%%', reduction_vs_timer(i)), ...
            'HorizontalAlignment', 'center', 'FontName', 'Times New Roman', 'FontSize', 10);
    end
    
    %% Subplot 4: Energy reduction % vs EWMA alpha (0.1,0.3,0.5,0.7)
    subplot(2,2,4);
    
    alpha_vals = [0.1, 0.3, 0.5, 0.7];
    reduction_vs_alpha = zeros(1, length(alpha_vals));
    
    for i = 1:length(alpha_vals)
        alpha = alpha_vals(i);
        P_baseline = build_transition_matrix(lambda_test, mu_inact_default, 0, 'baseline');
        P_arsta = build_transition_matrix(lambda_test, mu_inact_default, alpha, 'arsta');
        [e_baseline, ~] = compute_energy(P_baseline, dt, T_sim);
        [e_arsta, ~] = compute_energy(P_arsta, dt, T_sim);
        reduction_vs_alpha(i) = (e_baseline - e_arsta) / e_baseline * 100;
    end
    
    bar(alpha_vals, reduction_vs_alpha, 0.6, 'FaceColor', [0.8 0.4 0.3]);
    xlabel('EWMA Smoothing Factor (\alpha)', 'FontName', 'Times New Roman');
    ylabel('Energy Reduction (%)', 'FontName', 'Times New Roman');
    title('(d) Energy Reduction vs EWMA Alpha', 'FontName', 'Times New Roman');
    grid on;
    ylim([0, max(reduction_vs_alpha) * 1.3]);
    
    % Add value labels on bars
    for i = 1:length(alpha_vals)
        text(alpha_vals(i), reduction_vs_alpha(i) + 1, sprintf('%.1f%%', reduction_vs_alpha(i)), ...
            'HorizontalAlignment', 'center', 'FontName', 'Times New Roman', 'FontSize', 10);
    end
    
    %% Save figure
    % Add overall title
    sgtitle('ARSTA Analytical Energy Model', 'FontName', 'Times New Roman', ...
        'FontSize', 14, 'FontWeight', 'bold');
    
    % Export to PDF
    output_path = 'results/figures/analytical_model.pdf';
    
    % Ensure directory exists
    [dir_path, ~, ~] = fileparts(output_path);
    if ~exist(dir_path, 'dir')
        mkdir(dir_path);
    end
    
    % Save using exportgraphics
    exportgraphics(fig, output_path, 'ContentType', 'vector', 'Resolution', 300);
    
    fprintf('\nFigure saved to: %s\n', output_path);
    
    % Close figure
    close(fig);
end

%% Run main function when script is executed
energy_analytical();
