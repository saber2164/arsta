#!/usr/bin/env python3
"""
ARSTA Results Parser - Aggregate simulation outputs into clean DataFrames.

This module parses ns-3 RRC state logs and FlowMonitor XML output,
aggregates results across seeds, and provides statistical comparison.

Author: ARSTA Project
"""

import os
import xml.etree.ElementTree as ET
from glob import glob
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy import stats

from energy_model import EnergyModel


def parse_rrc_log(filepath: str) -> pd.DataFrame:
    """
    Parse ns-3 RRC state CSV. Columns: time_s,imsi,cell_id,old_state,new_state

    Add computed columns:
    - state_name: map {5:'RRC_IDLE', 9:'RRC_CONNECTED', 99:'RRC_INACTIVE', else:'TRANSITION'}
    - dwell_ms: time until next transition for that UE (shift by 1 per IMSI group)

    Args:
        filepath: Path to the RRC state CSV file.

    Returns:
        DataFrame sorted by (imsi, time_s) with state_name and dwell_ms columns.
    """
    # State mapping from ns-3 integers to human-readable names
    state_map = {
        5: 'RRC_IDLE',
        9: 'RRC_CONNECTED',
        99: 'RRC_INACTIVE',
    }

    df = pd.read_csv(filepath)

    # Ensure expected columns exist
    expected_cols = ['time_s', 'imsi', 'cell_id', 'old_state', 'new_state']
    for col in expected_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Sort by imsi and time
    df = df.sort_values(['imsi', 'time_s']).reset_index(drop=True)

    # Add state_name column (based on new_state)
    df['state_name'] = df['new_state'].map(
        lambda x: state_map.get(x, 'TRANSITION')
    )

    # Compute dwell_ms: time until next transition for each UE
    # Shift time_s by -1 within each IMSI group, then compute difference
    df['next_time_s'] = df.groupby('imsi')['time_s'].shift(-1)
    df['dwell_ms'] = (df['next_time_s'] - df['time_s']) * 1000.0

    # For last transition of each UE, set dwell_ms to NaN (unknown)
    # or could estimate based on simulation end time
    df['dwell_ms'] = df['dwell_ms'].fillna(0.0)

    # Drop helper column
    df = df.drop(columns=['next_time_s'])

    return df


def parse_flow_monitor(xml_path: str) -> pd.DataFrame:
    """
    Parse FlowMonitor XML. Return DataFrame with columns:
    flow_id, src_ip, dst_ip, tx_packets, rx_packets,
    throughput_mbps, mean_delay_ms, jitter_ms, loss_pct

    Args:
        xml_path: Path to the FlowMonitor XML file.

    Returns:
        DataFrame with flow statistics.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Build IP classifier mapping (flowId -> src/dst addresses)
    ip_map: Dict[str, Tuple[str, str]] = {}
    classifier = root.find('.//Ipv4FlowClassifier')
    if classifier is not None:
        for flow in classifier.findall('Flow'):
            flow_id = flow.get('flowId')
            src_addr = flow.get('sourceAddress', '')
            dst_addr = flow.get('destinationAddress', '')
            ip_map[flow_id] = (src_addr, dst_addr)

    # Parse flow stats
    flows_data = []
    flow_stats = root.find('.//FlowStats')
    if flow_stats is not None:
        for flow in flow_stats.findall('Flow'):
            flow_id = flow.get('flowId')
            tx_packets = int(flow.get('txPackets', 0))
            rx_packets = int(flow.get('rxPackets', 0))
            tx_bytes = int(flow.get('txBytes', 0))

            # Delay in nanoseconds
            delay_sum_ns = float(flow.get('delaySum', '0ns').rstrip('ns'))
            jitter_sum_ns = float(flow.get('jitterSum', '0ns').rstrip('ns'))

            # Time values for throughput calculation
            time_first_tx = flow.get('timeFirstTxPacket', '0ns')
            time_last_rx = flow.get('timeLastRxPacket', '0ns')

            # Parse time strings (format: "+1.234567890e+09ns")
            def parse_ns(s: str) -> float:
                return float(s.rstrip('ns').lstrip('+'))

            first_tx_ns = parse_ns(time_first_tx)
            last_rx_ns = parse_ns(time_last_rx)
            duration_s = (last_rx_ns - first_tx_ns) / 1e9 if last_rx_ns > first_tx_ns else 1.0

            # Compute metrics
            throughput_mbps = (tx_bytes * 8) / (duration_s * 1e6) if duration_s > 0 else 0.0
            mean_delay_ms = (delay_sum_ns / rx_packets / 1e6) if rx_packets > 0 else 0.0
            jitter_ms = (jitter_sum_ns / max(rx_packets - 1, 1) / 1e6) if rx_packets > 1 else 0.0
            loss_pct = ((tx_packets - rx_packets) / tx_packets * 100) if tx_packets > 0 else 0.0

            src_ip, dst_ip = ip_map.get(flow_id, ('', ''))

            flows_data.append({
                'flow_id': int(flow_id),
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'tx_packets': tx_packets,
                'rx_packets': rx_packets,
                'throughput_mbps': throughput_mbps,
                'mean_delay_ms': mean_delay_ms,
                'jitter_ms': jitter_ms,
                'loss_pct': loss_pct
            })

    return pd.DataFrame(flows_data)


def load_experiment(exp_dir: str, scheme: str) -> dict:
    """
    Load all seeds for one experiment+scheme combination.

    Args:
        exp_dir: e.g. "results/raw/EXP1_timer10"
        scheme: "baseline" or "arsta"

    Returns:
        {
          'rrc': pd.DataFrame,           # concatenated all seeds
          'flows': pd.DataFrame,         # concatenated all seeds
          'energy_per_seed': list[float],# one value per seed (mJ averaged over UEs)
          'transitions_per_seed': list[int]
        }
    """
    model = EnergyModel()

    rrc_dfs: List[pd.DataFrame] = []
    flow_dfs: List[pd.DataFrame] = []
    energy_per_seed: List[float] = []
    transitions_per_seed: List[int] = []

    # Expected file pattern: {scheme}_seed{N}_rrc.csv, {scheme}_seed{N}_flows.xml
    rrc_pattern = os.path.join(exp_dir, f"{scheme}_seed*_rrc.csv")
    rrc_files = sorted(glob(rrc_pattern))

    for rrc_file in rrc_files:
        # Extract seed number from filename
        basename = os.path.basename(rrc_file)
        # e.g., "baseline_seed1_rrc.csv" -> seed = 1
        seed_str = basename.replace(f"{scheme}_seed", "").replace("_rrc.csv", "")
        seed = int(seed_str) if seed_str.isdigit() else 0

        # Parse RRC log
        rrc_df = parse_rrc_log(rrc_file)
        rrc_df['seed'] = seed
        rrc_dfs.append(rrc_df)

        # Compute energy per UE and average
        ue_energies = []
        for imsi in rrc_df['imsi'].unique():
            ue_trace = rrc_df[rrc_df['imsi'] == imsi].copy()
            energy_mj = model.compute_session_energy_mj(ue_trace)
            ue_energies.append(energy_mj)

        avg_energy = np.mean(ue_energies) if ue_energies else 0.0
        energy_per_seed.append(avg_energy)

        # Count transitions
        transitions = model.transition_count(rrc_df)
        transitions_per_seed.append(transitions)

        # Try to load corresponding flow monitor XML
        flow_file = rrc_file.replace("_rrc.csv", "_flows.xml")
        if os.path.exists(flow_file):
            flow_df = parse_flow_monitor(flow_file)
            flow_df['seed'] = seed
            flow_dfs.append(flow_df)

    # Concatenate all DataFrames
    rrc_combined = pd.concat(rrc_dfs, ignore_index=True) if rrc_dfs else pd.DataFrame()
    flows_combined = pd.concat(flow_dfs, ignore_index=True) if flow_dfs else pd.DataFrame()

    return {
        'rrc': rrc_combined,
        'flows': flows_combined,
        'energy_per_seed': energy_per_seed,
        'transitions_per_seed': transitions_per_seed
    }


def summarise(values: list) -> dict:
    """
    Compute summary statistics with 95% confidence interval.

    Args:
        values: List of numeric values.

    Returns:
        {mean, std, ci_low, ci_high} using scipy.stats.t.interval at 95%
    """
    if not values or len(values) == 0:
        return {'mean': 0.0, 'std': 0.0, 'ci_low': 0.0, 'ci_high': 0.0}

    arr = np.array(values)
    n = len(arr)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0

    if n > 1 and std_val > 0:
        sem = std_val / np.sqrt(n)
        ci = stats.t.interval(0.95, df=n - 1, loc=mean_val, scale=sem)
        ci_low, ci_high = float(ci[0]), float(ci[1])
    else:
        ci_low, ci_high = mean_val, mean_val

    return {
        'mean': mean_val,
        'std': std_val,
        'ci_low': ci_low,
        'ci_high': ci_high
    }


def compare_schemes(baseline_vals: list, arsta_vals: list) -> dict:
    """
    Perform Welch t-test comparing baseline and ARSTA values.

    Args:
        baseline_vals: List of baseline metric values.
        arsta_vals: List of ARSTA metric values.

    Returns:
        {reduction_pct, p_value, significant (bool, p<0.05),
         baseline_mean, arsta_mean, baseline_ci, arsta_ci}
    """
    baseline_summary = summarise(baseline_vals)
    arsta_summary = summarise(arsta_vals)

    baseline_mean = baseline_summary['mean']
    arsta_mean = arsta_summary['mean']

    # Calculate reduction percentage
    if baseline_mean > 0:
        reduction_pct = ((baseline_mean - arsta_mean) / baseline_mean) * 100.0
    else:
        reduction_pct = 0.0

    # Perform Welch's t-test (unequal variance)
    if len(baseline_vals) > 1 and len(arsta_vals) > 1:
        t_stat, p_value = stats.ttest_ind(
            baseline_vals, arsta_vals, equal_var=False
        )
        p_value = float(p_value)
    else:
        p_value = 1.0

    significant = p_value < 0.05

    return {
        'reduction_pct': reduction_pct,
        'p_value': p_value,
        'significant': significant,
        'baseline_mean': baseline_mean,
        'arsta_mean': arsta_mean,
        'baseline_ci': (baseline_summary['ci_low'], baseline_summary['ci_high']),
        'arsta_ci': (arsta_summary['ci_low'], arsta_summary['ci_high'])
    }


def create_mock_experiment(base_dir: str) -> None:
    """Create mock experiment data for demonstration."""
    os.makedirs(base_dir, exist_ok=True)

    # Generate mock RRC log data for multiple seeds
    np.random.seed(42)

    for seed in range(1, 4):  # 3 seeds
        # Baseline: more time in CONNECTED, no INACTIVE
        baseline_data = []
        t = 0.0
        states = [5, 9]  # IDLE, CONNECTED only
        current_state = 5

        for i in range(20):
            next_state = 9 if current_state == 5 else 5
            baseline_data.append({
                'time_s': t,
                'imsi': 1001,
                'cell_id': 1,
                'old_state': current_state,
                'new_state': next_state
            })
            t += np.random.exponential(5.0 + seed * 0.5)
            current_state = next_state

        df_baseline = pd.DataFrame(baseline_data)
        df_baseline.to_csv(
            os.path.join(base_dir, f"baseline_seed{seed}_rrc.csv"),
            index=False
        )

        # ARSTA: includes INACTIVE state, less CONNECTED time
        arsta_data = []
        t = 0.0
        states = [5, 9, 99]  # IDLE, CONNECTED, INACTIVE
        current_state = 5

        for i in range(25):
            # Prefer transitioning to INACTIVE from CONNECTED
            if current_state == 9:
                next_state = np.random.choice([5, 99], p=[0.3, 0.7])
            elif current_state == 99:
                next_state = np.random.choice([5, 9], p=[0.5, 0.5])
            else:
                next_state = 9

            arsta_data.append({
                'time_s': t,
                'imsi': 1001,
                'cell_id': 1,
                'old_state': current_state,
                'new_state': next_state
            })
            t += np.random.exponential(4.0 + seed * 0.3)
            current_state = next_state

        df_arsta = pd.DataFrame(arsta_data)
        df_arsta.to_csv(
            os.path.join(base_dir, f"arsta_seed{seed}_rrc.csv"),
            index=False
        )


def main():
    """Demonstrate loading mock experiment and print comparison."""
    print("=" * 70)
    print("ARSTA Results Parser - Demonstration")
    print("=" * 70)

    # Create mock experiment directory
    mock_dir = "results/raw/EXP1_mock"
    print(f"\n📁 Creating mock experiment data in: {mock_dir}")
    create_mock_experiment(mock_dir)

    # Load baseline and ARSTA results
    print("\n📊 Loading experiment data...")
    baseline_results = load_experiment(mock_dir, "baseline")
    arsta_results = load_experiment(mock_dir, "arsta")

    # Display loaded data summary
    print(f"\n  Baseline seeds loaded: {len(baseline_results['energy_per_seed'])}")
    print(f"  ARSTA seeds loaded:    {len(arsta_results['energy_per_seed'])}")

    # Summarize energy
    baseline_energy = summarise(baseline_results['energy_per_seed'])
    arsta_energy = summarise(arsta_results['energy_per_seed'])

    print("\n📈 Energy Consumption Summary (mJ per UE):")
    print("-" * 50)
    print(f"  {'Scheme':<12} {'Mean':>10} {'Std':>10} {'95% CI':>20}")
    print("-" * 50)
    print(f"  {'Baseline':<12} {baseline_energy['mean']:>10.2f} "
          f"{baseline_energy['std']:>10.2f} "
          f"[{baseline_energy['ci_low']:.2f}, {baseline_energy['ci_high']:.2f}]")
    print(f"  {'ARSTA':<12} {arsta_energy['mean']:>10.2f} "
          f"{arsta_energy['std']:>10.2f} "
          f"[{arsta_energy['ci_low']:.2f}, {arsta_energy['ci_high']:.2f}]")

    # Compare schemes
    comparison = compare_schemes(
        baseline_results['energy_per_seed'],
        arsta_results['energy_per_seed']
    )

    print("\n📉 Statistical Comparison (Welch t-test):")
    print("-" * 50)
    print(f"  Energy Reduction: {comparison['reduction_pct']:.2f}%")
    print(f"  p-value:          {comparison['p_value']:.4f}")
    print(f"  Significant:      {'Yes ✓' if comparison['significant'] else 'No'}")

    # Transition counts
    baseline_trans = summarise(baseline_results['transitions_per_seed'])
    arsta_trans = summarise(arsta_results['transitions_per_seed'])

    print("\n🔄 Transition Count Summary:")
    print("-" * 50)
    print(f"  Baseline:  {baseline_trans['mean']:.1f} ± {baseline_trans['std']:.1f}")
    print(f"  ARSTA:     {arsta_trans['mean']:.1f} ± {arsta_trans['std']:.1f}")

    # Create summary CSV
    summary_data = {
        'metric': ['energy_mJ', 'energy_mJ', 'transitions', 'transitions'],
        'scheme': ['baseline', 'arsta', 'baseline', 'arsta'],
        'mean': [
            baseline_energy['mean'], arsta_energy['mean'],
            baseline_trans['mean'], arsta_trans['mean']
        ],
        'std': [
            baseline_energy['std'], arsta_energy['std'],
            baseline_trans['std'], arsta_trans['std']
        ],
        'ci_low': [
            baseline_energy['ci_low'], arsta_energy['ci_low'],
            baseline_trans['ci_low'], arsta_trans['ci_low']
        ],
        'ci_high': [
            baseline_energy['ci_high'], arsta_energy['ci_high'],
            baseline_trans['ci_high'], arsta_trans['ci_high']
        ]
    }
    summary_df = pd.DataFrame(summary_data)

    # Save to processed directory
    output_dir = "results/processed"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "exp1_summary.csv")
    summary_df.to_csv(output_path, index=False)
    print(f"\n💾 Summary saved to: {output_path}")

    # Display the comparison table
    print("\n📋 Comparison Table:")
    print("-" * 70)
    print(summary_df.to_string(index=False))

    print("\n" + "=" * 70)
    print("Results parsing demonstration completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
