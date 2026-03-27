#!/usr/bin/env python3
"""
ARSTA Publication Figures - IEEE-format plots for 5G RRC energy optimization.

This module generates publication-quality figures for the ARSTA paper,
conforming to IEEE Transactions formatting guidelines.

Author: ARSTA Project
"""

import os
from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

# IEEE publication formatting settings
matplotlib.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'Times', 'DejaVu Serif'],
    'font.size': 11,
    'axes.labelsize': 12,
    'legend.fontsize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.dpi': 300,
    'savefig.bbox': 'tight',
    'pdf.fonttype': 42
})

# Consistent color scheme for all figures
SCHEME_COLORS = {
    'Baseline (3GPP)': '#E24B4A',
    'ARSTA (Proposed)': '#1D9E75',
    '5GSaver [1]':      '#378ADD',
    'Khlass et al. [2]':'#EF9F27'
}

# Scheme order for consistent legend ordering
SCHEME_ORDER = ['Baseline (3GPP)', 'ARSTA (Proposed)', '5GSaver [1]', 'Khlass et al. [2]']


def _compute_cdf(values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute CDF from array of values."""
    sorted_vals = np.sort(values)
    cdf = np.arange(1, len(sorted_vals) + 1) / len(sorted_vals)
    return sorted_vals, cdf


def _confidence_interval_95(values: List[float]) -> Tuple[float, float]:
    """Compute 95% confidence interval for a list of values."""
    if len(values) < 2:
        mean_val = np.mean(values) if values else 0.0
        return (0.0, 0.0)
    arr = np.array(values)
    mean_val = np.mean(arr)
    sem = stats.sem(arr)
    ci = stats.t.interval(0.95, df=len(arr) - 1, loc=mean_val, scale=sem)
    return (mean_val - ci[0], ci[1] - mean_val)


def fig1_energy_cdf(data: Dict, save_path: str) -> None:
    """
    Generate CDF of per-UE energy consumption.

    IEEE single-column figure: 3.5 x 2.8 inches.

    Args:
        data: Dictionary with keys = scheme names, values = list of per-UE energy (mJ).
        save_path: Output file path (PDF).
    """
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    for scheme in SCHEME_ORDER:
        if scheme in data:
            values = np.array(data[scheme])
            x, y = _compute_cdf(values)
            ax.plot(x, y, label=scheme, color=SCHEME_COLORS[scheme], linewidth=1.5)

    ax.set_xlabel('Energy per UE (mJ)')
    ax.set_ylabel('CDF')
    ax.set_ylim(0, 1.05)
    ax.set_xlim(left=0)
    ax.legend(loc='lower right', frameon=True, edgecolor='black', fancybox=False)
    ax.grid(True, linestyle='--', alpha=0.5, linewidth=0.5)

    # Add minor ticks
    ax.minorticks_on()
    ax.tick_params(which='minor', length=2)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, format='pdf')
    plt.close(fig)
    print(f"  ✓ Saved: {save_path}")


def fig2_state_dwell_bar(data: Dict, save_path: str) -> None:
    """
    Generate stacked bar chart showing fraction of time in each RRC state.

    Args:
        data: Dictionary with keys = scheme names, values = dict with
              'IDLE', 'INACTIVE', 'CONNECTED' percentages.
        save_path: Output file path (PDF).
    """
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    schemes = [s for s in SCHEME_ORDER if s in data]
    n_schemes = len(schemes)
    x = np.arange(n_schemes)
    bar_width = 0.6

    # State colors
    state_colors = {
        'IDLE': '#4CAF50',       # Green
        'INACTIVE': '#FFC107',   # Amber
        'CONNECTED': '#F44336'   # Red
    }

    # Stack the bars
    bottom = np.zeros(n_schemes)
    for state in ['IDLE', 'INACTIVE', 'CONNECTED']:
        values = [data[s].get(state, 0) for s in schemes]
        ax.bar(x, values, bar_width, bottom=bottom, label=state.replace('_', ' ').title(),
               color=state_colors[state], edgecolor='black', linewidth=0.5)
        bottom += np.array(values)

    ax.set_ylabel('Time Fraction (%)')
    ax.set_xticks(x)
    ax.set_xticklabels([s.split(' ')[0] for s in schemes], rotation=15, ha='right')
    ax.set_ylim(0, 105)
    ax.legend(loc='upper right', frameon=True, edgecolor='black', fancybox=False)
    ax.grid(True, axis='y', linestyle='--', alpha=0.5, linewidth=0.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, format='pdf')
    plt.close(fig)
    print(f"  ✓ Saved: {save_path}")


def fig3_energy_vs_velocity(data: Dict, save_path: str) -> None:
    """
    Generate line plot of energy vs UE velocity with 95% CI error bars.

    Args:
        data: Dictionary with keys = scheme names, values = dict mapping
              velocity (m/s) -> list of energy values (mJ).
        save_path: Output file path (PDF).
    """
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    velocities = [0, 3, 10, 30]  # m/s
    markers = ['o', 's', '^', 'D']

    for i, scheme in enumerate(SCHEME_ORDER):
        if scheme not in data:
            continue

        means = []
        ci_low = []
        ci_high = []

        for v in velocities:
            vals = data[scheme].get(v, [0])
            mean_val = np.mean(vals)
            means.append(mean_val)
            if len(vals) > 1:
                ci = _confidence_interval_95(vals)
                ci_low.append(ci[0])
                ci_high.append(ci[1])
            else:
                ci_low.append(0)
                ci_high.append(0)

        ax.errorbar(velocities, means, yerr=[ci_low, ci_high],
                    label=scheme, color=SCHEME_COLORS[scheme],
                    marker=markers[i % len(markers)], markersize=5,
                    linewidth=1.5, capsize=3, capthick=1)

    ax.set_xlabel('UE Velocity (m/s)')
    ax.set_ylabel('Energy Consumption (mJ)')
    ax.set_xlim(-1, 32)
    ax.set_ylim(bottom=0)
    ax.legend(loc='best', frameon=True, edgecolor='black', fancybox=False, fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.5, linewidth=0.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, format='pdf')
    plt.close(fig)
    print(f"  ✓ Saved: {save_path}")


def fig4_energy_vs_traffic(data: Dict, save_path: str) -> None:
    """
    Generate grouped bar chart of energy consumption by traffic intensity.

    Args:
        data: Dictionary with keys = scheme names, values = dict mapping
              traffic level ('low', 'medium', 'high') -> mean energy (mJ).
        save_path: Output file path (PDF).
    """
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    traffic_levels = ['low', 'medium', 'high']
    schemes = [s for s in SCHEME_ORDER if s in data]
    n_schemes = len(schemes)
    n_traffic = len(traffic_levels)

    x = np.arange(n_traffic)
    bar_width = 0.8 / n_schemes

    for i, scheme in enumerate(schemes):
        values = [data[scheme].get(t, 0) for t in traffic_levels]
        offset = (i - n_schemes / 2 + 0.5) * bar_width
        ax.bar(x + offset, values, bar_width, label=scheme,
               color=SCHEME_COLORS[scheme], edgecolor='black', linewidth=0.5)

    ax.set_ylabel('Energy Consumption (mJ)')
    ax.set_xticks(x)
    ax.set_xticklabels(['Low', 'Medium', 'High'])
    ax.set_xlabel('Traffic Intensity')
    ax.set_ylim(bottom=0)
    ax.legend(loc='upper left', frameon=True, edgecolor='black', fancybox=False, fontsize=8)
    ax.grid(True, axis='y', linestyle='--', alpha=0.5, linewidth=0.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, format='pdf')
    plt.close(fig)
    print(f"  ✓ Saved: {save_path}")


def fig5_paging_success_rate(data: Dict, save_path: str) -> None:
    """
    Generate line plot of paging success rate vs UE velocity.

    Includes horizontal dashed line at 99% target.

    Args:
        data: Dictionary with keys = scheme names, values = dict mapping
              velocity (m/s) -> paging success rate (%).
        save_path: Output file path (PDF).
    """
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    velocities = [0, 3, 10, 30]  # m/s
    markers = ['o', 's', '^', 'D']

    for i, scheme in enumerate(SCHEME_ORDER):
        if scheme not in data:
            continue

        rates = [data[scheme].get(v, 100.0) for v in velocities]
        ax.plot(velocities, rates, label=scheme, color=SCHEME_COLORS[scheme],
                marker=markers[i % len(markers)], markersize=5, linewidth=1.5)

    # Target line at 99%
    ax.axhline(y=99.0, color='gray', linestyle='--', linewidth=1.0,
               label='Target (99%)', zorder=0)

    ax.set_xlabel('UE Velocity (m/s)')
    ax.set_ylabel('Paging Success Rate (%)')
    ax.set_xlim(-1, 32)
    ax.set_ylim(90, 100.5)
    ax.legend(loc='lower left', frameon=True, edgecolor='black', fancybox=False, fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.5, linewidth=0.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, format='pdf')
    plt.close(fig)
    print(f"  ✓ Saved: {save_path}")


def fig6_ho_latency_cdf(data: Dict, save_path: str) -> None:
    """
    Generate CDF of handover latency.

    Args:
        data: Dictionary with keys = scheme names, values = list of HO latencies (ms).
        save_path: Output file path (PDF).
    """
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    for scheme in SCHEME_ORDER:
        if scheme in data:
            values = np.array(data[scheme])
            x, y = _compute_cdf(values)
            ax.plot(x, y, label=scheme, color=SCHEME_COLORS[scheme], linewidth=1.5)

    ax.set_xlabel('Handover Latency (ms)')
    ax.set_ylabel('CDF')
    ax.set_ylim(0, 1.05)
    ax.set_xlim(left=0)
    ax.legend(loc='lower right', frameon=True, edgecolor='black', fancybox=False)
    ax.grid(True, linestyle='--', alpha=0.5, linewidth=0.5)

    ax.minorticks_on()
    ax.tick_params(which='minor', length=2)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, format='pdf')
    plt.close(fig)
    print(f"  ✓ Saved: {save_path}")


def table2_comparison(data: Dict, save_path: str) -> None:
    """
    Generate LaTeX table with booktabs formatting.

    Args:
        data: Dictionary with structure:
              {scheme_name: {'energy_mJ': val, 'reduction_pct': val,
                             'paging_rate': val, 'ho_latency_ms': val}}
        save_path: Output file path (.tex).
    """
    latex_lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Performance Comparison of RRC State Management Schemes}",
        r"\label{tab:comparison}",
        r"\begin{tabular}{@{}lcccc@{}}",
        r"\toprule",
        r"Scheme & Energy & Reduction & Paging & HO Latency \\",
        r"       & (mJ)   & (\%)      & Rate (\%) & (ms) \\",
        r"\midrule",
    ]

    for scheme in SCHEME_ORDER:
        if scheme not in data:
            continue
        d = data[scheme]
        energy = d.get('energy_mJ', 0)
        reduction = d.get('reduction_pct', 0)
        paging = d.get('paging_rate', 0)
        ho_lat = d.get('ho_latency_ms', 0)

        # Format scheme name for LaTeX
        scheme_tex = scheme.replace('%', r'\%').replace('_', r'\_')

        # Bold ARSTA row
        if 'ARSTA' in scheme:
            latex_lines.append(
                rf"\textbf{{{scheme_tex}}} & \textbf{{{energy:.1f}}} & "
                rf"\textbf{{{reduction:.1f}}} & \textbf{{{paging:.1f}}} & "
                rf"\textbf{{{ho_lat:.1f}}} \\"
            )
        else:
            latex_lines.append(
                rf"{scheme_tex} & {energy:.1f} & {reduction:.1f} & {paging:.1f} & {ho_lat:.1f} \\"
            )

    latex_lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, 'w') as f:
        f.write('\n'.join(latex_lines))
    print(f"  ✓ Saved: {save_path}")


def generate_mock_data() -> Dict:
    """
    Generate realistic mock data for demonstration.

    Returns:
        Dictionary containing all data structures needed for figures.
    """
    np.random.seed(42)

    data = {}

    # --- Fig 1: Energy CDF (per-UE energy in mJ) ---
    # Baseline: higher energy, wider distribution
    # ARSTA: ~30% lower, tighter distribution
    data['energy_cdf'] = {
        'Baseline (3GPP)': np.random.normal(450, 80, 100),
        'ARSTA (Proposed)': np.random.normal(315, 50, 100),  # ~30% reduction
        '5GSaver [1]': np.random.normal(405, 70, 100),       # ~10% reduction
        'Khlass et al. [2]': np.random.normal(420, 75, 100), # ~7% reduction
    }
    # Ensure non-negative
    for k in data['energy_cdf']:
        data['energy_cdf'][k] = np.clip(data['energy_cdf'][k], 50, 800)

    # --- Fig 2: State dwell time fractions (%) ---
    data['state_dwell'] = {
        'Baseline (3GPP)': {'IDLE': 25, 'INACTIVE': 0, 'CONNECTED': 75},
        'ARSTA (Proposed)': {'IDLE': 35, 'INACTIVE': 40, 'CONNECTED': 25},
        '5GSaver [1]': {'IDLE': 30, 'INACTIVE': 20, 'CONNECTED': 50},
        'Khlass et al. [2]': {'IDLE': 28, 'INACTIVE': 15, 'CONNECTED': 57},
    }

    # --- Fig 3: Energy vs velocity (with per-seed values for CI) ---
    velocities = [0, 3, 10, 30]
    data['energy_velocity'] = {}
    for scheme, base_energy in [
        ('Baseline (3GPP)', 450),
        ('ARSTA (Proposed)', 315),
        ('5GSaver [1]', 405),
        ('Khlass et al. [2]', 420)
    ]:
        data['energy_velocity'][scheme] = {}
        for v in velocities:
            # Energy increases with velocity (more handovers)
            velocity_factor = 1.0 + 0.005 * v
            base = base_energy * velocity_factor
            # 10 seeds
            data['energy_velocity'][scheme][v] = list(
                np.random.normal(base, base * 0.08, 10)
            )

    # --- Fig 4: Energy vs traffic intensity ---
    data['energy_traffic'] = {
        'Baseline (3GPP)': {'low': 280, 'medium': 450, 'high': 680},
        'ARSTA (Proposed)': {'low': 190, 'medium': 315, 'high': 510},
        '5GSaver [1]': {'low': 250, 'medium': 405, 'high': 620},
        'Khlass et al. [2]': {'low': 260, 'medium': 420, 'high': 640},
    }

    # --- Fig 5: Paging success rate vs velocity ---
    # ARSTA maintains high rate even at high velocity
    data['paging_rate'] = {
        'Baseline (3GPP)': {0: 99.8, 3: 99.5, 10: 98.2, 30: 94.5},
        'ARSTA (Proposed)': {0: 99.9, 3: 99.8, 10: 99.5, 30: 99.2},
        '5GSaver [1]': {0: 99.7, 3: 99.3, 10: 98.0, 30: 95.5},
        'Khlass et al. [2]': {0: 99.6, 3: 99.2, 10: 97.5, 30: 93.8},
    }

    # --- Fig 6: Handover latency CDF (ms) ---
    data['ho_latency'] = {
        'Baseline (3GPP)': np.random.exponential(35, 200) + 15,
        'ARSTA (Proposed)': np.random.exponential(25, 200) + 12,  # Lower due to HO-aware locking
        '5GSaver [1]': np.random.exponential(32, 200) + 14,
        'Khlass et al. [2]': np.random.exponential(38, 200) + 16,
    }

    # --- Table 2: Comparison summary ---
    data['table_comparison'] = {
        'Baseline (3GPP)': {
            'energy_mJ': 450.0, 'reduction_pct': 0.0,
            'paging_rate': 97.5, 'ho_latency_ms': 48.2
        },
        'ARSTA (Proposed)': {
            'energy_mJ': 315.0, 'reduction_pct': 30.0,
            'paging_rate': 99.6, 'ho_latency_ms': 36.8
        },
        '5GSaver [1]': {
            'energy_mJ': 405.0, 'reduction_pct': 10.0,
            'paging_rate': 97.1, 'ho_latency_ms': 45.3
        },
        'Khlass et al. [2]': {
            'energy_mJ': 420.0, 'reduction_pct': 6.7,
            'paging_rate': 96.3, 'ho_latency_ms': 52.1
        },
    }

    return data


def main():
    """Generate all publication figures."""
    print("=" * 60)
    print("ARSTA Publication Figures Generator")
    print("=" * 60)

    # Output directory
    fig_dir = "results/figures"
    os.makedirs(fig_dir, exist_ok=True)

    print(f"\n📁 Output directory: {fig_dir}")
    print("\n📊 Generating mock data for demonstration...")
    data = generate_mock_data()

    print("\n📈 Generating figures...\n")

    # Generate all figures
    fig1_energy_cdf(
        data['energy_cdf'],
        os.path.join(fig_dir, "fig1_energy_cdf.pdf")
    )

    fig2_state_dwell_bar(
        data['state_dwell'],
        os.path.join(fig_dir, "fig2_state_dwell_bar.pdf")
    )

    fig3_energy_vs_velocity(
        data['energy_velocity'],
        os.path.join(fig_dir, "fig3_energy_vs_velocity.pdf")
    )

    fig4_energy_vs_traffic(
        data['energy_traffic'],
        os.path.join(fig_dir, "fig4_energy_vs_traffic.pdf")
    )

    fig5_paging_success_rate(
        data['paging_rate'],
        os.path.join(fig_dir, "fig5_paging_success_rate.pdf")
    )

    fig6_ho_latency_cdf(
        data['ho_latency'],
        os.path.join(fig_dir, "fig6_ho_latency_cdf.pdf")
    )

    table2_comparison(
        data['table_comparison'],
        os.path.join(fig_dir, "table2_comparison.tex")
    )

    print("\n" + "=" * 60)
    print("All figures generated successfully!")
    print(f"Output files in: {fig_dir}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
