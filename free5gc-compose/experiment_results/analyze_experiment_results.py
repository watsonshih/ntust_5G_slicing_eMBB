import os
import json
import re
import pandas as pd
import numpy as np
from scipy.stats import mannwhitneyu

# --- Configuration ---
RESULTS_DIR = "."  # Assume script and result files are in the same directory
TOTAL_REPETITIONS = 5 # Actual number of repetitions performed, please modify here
# If you ran each scenario 5 times, change to 5

# Scenario definition: (Scenario label, UE name, iperf client parameters (for logging only, actual parameters set at runtime))
# Competing scenario is special, will have data from two UEs
SCENARIOS = {
    "baseline": {
        "ue_name": "ueransim-ue1",
        "iperf_params": "-b 75M -P 2",
        "label_for_table": "Baseline (UE1)" # Kept as is, assuming it's an identifier
    },
    "high_only": {
        "ue_name": "ueransim-ue1",
        "iperf_params": "-b 75M -P 2",
        "label_for_table": "High-Only (UE1)" # Kept as is
    },
    "medium_only": {
        "ue_name": "ueransim-ue2",
        "iperf_params": "-b 4M -P 10",
        "label_for_table": "Medium-Only (UE2)" # Kept as is
    },
    "competing_high": { # UE1 performance in competing scenario
        "ue_name": "ueransim-ue1",
        "iperf_params": "-b 75M -P 2",
        "label_for_table": "Competing (UE1-High)" # Kept as is
    },
    "competing_medium": { # UE2 performance in competing scenario
        "ue_name": "ueransim-ue2",
        "iperf_params": "-b 4M -P 10",
        "label_for_table": "Competing (UE2-Medium)" # Kept as is
    }
}

def parse_iperf_json(filepath):
    """Parse a single iperf3 JSON file"""
    try:
        with open(filepath, 'r') as f:
            # Try to handle multiple JSON objects or non-JSON text that may exist in the file
            content = f.read()
            # Find the content between the first '{' and the last '}', try to parse as a JSON object
            # This is a simplified process, for the merged JSON you provided, it might only take the first one
            first_brace = content.find('{')
            last_brace = content.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_content = content[first_brace : last_brace+1]
                data = json.loads(json_content)

                if "end" in data and "sum" in data["end"]:
                    sum_data = data["end"]["sum"]
                    # iperf 3.9 UDP summary might be in sum_sent or sum_received
                    # For UDP sender side, it's usually in sum_sent
                    # However, the provided JSON has sum.bits_per_second etc. directly under 'sum'
                    
                    throughput_bps = sum_data.get("bits_per_second", 0)
                    jitter_ms = sum_data.get("jitter_ms", 0)
                    
                    # For UDP, lost_packets and packets are typically under 'udp' object within 'sum'
                    # or directly under 'sum' if it's an older iperf3 or specific reporting
                    if "lost_packets" in sum_data and "packets" in sum_data:
                        lost_packets = sum_data.get("lost_packets", 0)
                        total_packets = sum_data.get("packets", 0)
                    elif "udp" in sum_data: # Fallback for older iperf3 versions if sum_data is a list
                         # This part might need adjustment based on exact JSON structure for UDP summaries
                        udp_summary = {}
                        if isinstance(sum_data["udp"], list) and len(sum_data["udp"]) > 0:
                            udp_summary = sum_data["udp"][0] # Assuming first stream summary if it's a list
                        elif isinstance(sum_data["udp"], dict) :
                            udp_summary = sum_data["udp"]

                        lost_packets = udp_summary.get("lost_packets",0)
                        total_packets = udp_summary.get("packets",0)
                    else: # Another fallback
                        lost_packets = sum_data.get("lost_packets", 0)
                        total_packets = sum_data.get("packets", 0)


                    lost_percent = sum_data.get("lost_percent", 0)
                    if total_packets > 0 and lost_packets > 0 and lost_percent == 0: # Recalculate if lost_percent is 0 but packets are lost
                        lost_percent = (lost_packets / total_packets) * 100
                    
                    return {
                        "throughput_mbps": throughput_bps / 1_000_000 if throughput_bps else None,
                        "jitter_ms": jitter_ms if jitter_ms else None,
                        "lost_packets": lost_packets if total_packets else None,
                        "total_packets": total_packets if total_packets else None,
                        "lost_percent": lost_percent if total_packets else None,
                    }
                # Handle cases like "Connection reset by peer" where 'end' or 'sum' might be missing
                elif "error" in data:
                    print(f"  --> iperf error in {filepath}: {data['error']}")
                    return None
                else:
                    print(f"  --> 'end' or 'sum' not found in iperf JSON: {filepath}")
                    return None
            else:
                # Check if it's the "Connection reset by peer" error message which is not valid JSON
                if "iperf3: error - unable to send control message: Connection reset by peer" in content:
                    print(f"  --> iperf client error (Connection reset by peer) in file: {filepath}")
                    return None
                print(f"  --> No valid JSON object found in: {filepath}")
                return None
    except json.JSONDecodeError as e:
        print(f"  --> Error decoding JSON from {filepath}: {e}")
        # Check again for known error messages that are not JSON
        if "iperf3: error - unable to send control message: Connection reset by peer" in open(filepath, 'r').read():
             print(f"  --> iperf client error (Connection reset by peer) in file: {filepath}")
        return None
    except FileNotFoundError:
        print(f"  --> File not found: {filepath}")
        return None
    except Exception as e:
        print(f"  --> Unexpected error parsing iperf file {filepath}: {e}")
        return None

def parse_ping_log(filepath):
    """Parse a single ping log file"""
    rtt_values = []
    summary_stats = {
        "rtt_min_ms": None,
        "rtt_avg_ms": None,
        "rtt_max_ms": None,
        "rtt_mdev_ms": None,
        "rtt_95p_ms": None,
        "packet_loss_percent": None
    }
    try:
        with open(filepath, 'r') as f:
            for line in f:
                match_rtt = re.search(r"time=([\d\.]+)\s*ms", line)
                if match_rtt:
                    rtt_values.append(float(match_rtt.group(1)))

                match_summary = re.search(r"rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)\s*ms", line)
                if match_summary:
                    summary_stats["rtt_min_ms"] = float(match_summary.group(1))
                    summary_stats["rtt_avg_ms"] = float(match_summary.group(2))
                    summary_stats["rtt_max_ms"] = float(match_summary.group(3))
                    summary_stats["rtt_mdev_ms"] = float(match_summary.group(4))

                match_loss = re.search(r"([\d\.]+)% packet loss", line)
                if match_loss:
                    summary_stats["packet_loss_percent"] = float(match_loss.group(1))
            
            if rtt_values:
                summary_stats["rtt_95p_ms"] = np.percentile(rtt_values, 95) if rtt_values else None

            # Check if essential stats were parsed, if not, might be an empty or malformed ping log
            if summary_stats["rtt_avg_ms"] is None and rtt_values:
                 summary_stats["rtt_avg_ms"] = np.mean(rtt_values) if rtt_values else None
                 summary_stats["rtt_min_ms"] = np.min(rtt_values) if rtt_values else None
                 summary_stats["rtt_max_ms"] = np.max(rtt_values) if rtt_values else None
                 summary_stats["rtt_mdev_ms"] = np.std(rtt_values) if rtt_values else None


            return summary_stats
            
    except FileNotFoundError:
        print(f"  --> File not found: {filepath}")
        return summary_stats # Return dict with Nones
    except Exception as e:
        print(f"  --> Unexpected error parsing ping file {filepath}: {e}")
        return summary_stats


# --- Main Processing Flow ---
all_results = []

for scenario_key, scenario_info in SCENARIOS.items():
    ue_name = scenario_info["ue_name"]
    label = scenario_info["label_for_table"]
    
    print(f"\nProcessing scenario: {label} (key: {scenario_key})")
    
    for rep in range(1, TOTAL_REPETITIONS + 1):
        print(f" Repetition {rep}:")
        
        # Construct filename
        # ueransim-ue1_baseline_iperf_rep1.json
        # ueransim-ue1_competing_high_iperf_rep1.json

        if scenario_key == "baseline":
            iperf_file = os.path.join(RESULTS_DIR, f"{ue_name}_baseline_iperf_rep{rep}.json")
            ping_file = os.path.join(RESULTS_DIR, f"{ue_name}_baseline_ping_rep{rep}.log") # .log for ping
        elif scenario_key == "high_only":
            iperf_file = os.path.join(RESULTS_DIR, f"{ue_name}_high_only_iperf_rep{rep}.json")
            ping_file = os.path.join(RESULTS_DIR, f"{ue_name}_high_only_ping_rep{rep}.log")
        elif scenario_key == "medium_only":
            iperf_file = os.path.join(RESULTS_DIR, f"{ue_name}_medium_only_iperf_rep{rep}.json")
            ping_file = os.path.join(RESULTS_DIR, f"{ue_name}_medium_only_ping_rep{rep}.log")
        elif scenario_key == "competing_high":
            iperf_file = os.path.join(RESULTS_DIR, f"{ue_name}_competing_high_iperf_rep{rep}.json")
            ping_file = os.path.join(RESULTS_DIR, f"{ue_name}_competing_high_ping_rep{rep}.log")
        elif scenario_key == "competing_medium":
            iperf_file = os.path.join(RESULTS_DIR, f"{ue_name}_competing_medium_iperf_rep{rep}.json")
            ping_file = os.path.join(RESULTS_DIR, f"{ue_name}_competing_medium_ping_rep{rep}.log")
        else:
            print(f"  --> Unknown scenario key: {scenario_key}")
            continue
            
        iperf_data = parse_iperf_json(iperf_file)
        ping_data = parse_ping_log(ping_file)
        
        current_result = {
            "Scenario": label,
            "Repetition": rep,
            "UE": ue_name
        }
        
        if iperf_data:
            current_result.update(iperf_data)
        else: # Add NaN or 0 for missing iperf data to keep DataFrame structure consistent
            current_result.update({
                "throughput_mbps": np.nan, "jitter_ms": np.nan,
                "lost_packets": np.nan, "total_packets": np.nan, "lost_percent": np.nan
            })
            
        if ping_data:
            current_result.update(ping_data)
        else: # Add NaN or 0 for missing ping data
            current_result.update({
                "rtt_min_ms": np.nan, "rtt_avg_ms": np.nan, "rtt_max_ms": np.nan,
                "rtt_mdev_ms": np.nan, "rtt_95p_ms": np.nan, "packet_loss_percent": np.nan
            })
            
        all_results.append(current_result)

# Convert to Pandas DataFrame
df_results = pd.DataFrame(all_results)

# Ensure column order
cols_ordered = [
    "Scenario", "Repetition", "UE",
    "throughput_mbps", "jitter_ms", "lost_packets", "total_packets", "lost_percent",
    "rtt_avg_ms", "rtt_95p_ms", "rtt_min_ms", "rtt_max_ms", "rtt_mdev_ms", "packet_loss_percent"
]
# Filter out columns that actually exist in the DataFrame to avoid KeyError
existing_cols = [col for col in cols_ordered if col in df_results.columns]
df_results = df_results[existing_cols]


print("\n\n--- Raw Results ---")
print(df_results.to_string())

# --- Calculate Mean and Standard Deviation for Each Scenario ---
summary_stats = df_results.groupby("Scenario").agg(
    Avg_Throughput_Mbps=('throughput_mbps', 'mean'),
    Std_Throughput_Mbps=('throughput_mbps', 'std'),
    Avg_Jitter_ms=('jitter_ms', 'mean'),
    Std_Jitter_ms=('jitter_ms', 'std'),
    Avg_Lost_Packets=('lost_packets', 'mean'),
    Avg_Lost_Percent=('lost_percent', 'mean'),
    Avg_RTT_ms=('rtt_avg_ms', 'mean'),
    Std_RTT_ms=('rtt_avg_ms', 'std'),
    Avg_RTT_95p_ms=('rtt_95p_ms', 'mean'),
    Std_RTT_95p_ms=('rtt_95p_ms', 'std'),
    Avg_Ping_Loss_Pct=('packet_loss_percent', 'mean') # Ping packet loss rate
).reset_index()

print("\n\n--- Summary Statistics per Scenario ---")
print(summary_stats.to_string())

# --- Perform Mann-Whitney U Test (Example) ---
# According to your research plan VI. B and Table VI.1
# You need to adjust this based on the actual collected data and the metrics to be compared
print("\n\n--- Mann-Whitney U Tests (p-values) ---")

# List of KPIs to test
kpi_to_test = [
    'throughput_mbps', 'jitter_ms', 'lost_percent',
    'rtt_avg_ms', 'rtt_95p_ms', 'packet_loss_percent'
]

# Define comparison pairs (based on Scenario's 'label_for_table')
comparison_pairs = [
    ("Baseline (UE1)", "High-Only (UE1)"),
    ("Baseline (UE1)", "Medium-Only (UE2)"),
    ("High-Only (UE1)", "Medium-Only (UE2)"),
    ("High-Only (UE1)", "Competing (UE1-High)"),
    ("Medium-Only (UE2)", "Competing (UE2-Medium)"),
]

test_results = []

for kpi in kpi_to_test:
    print(f"\nTesting KPI: {kpi}")
    for scenario1_label, scenario2_label in comparison_pairs:
        data1 = df_results[df_results["Scenario"] == scenario1_label][kpi].dropna()
        data2 = df_results[df_results["Scenario"] == scenario2_label][kpi].dropna()

        if len(data1) < 1 or len(data2) < 1: # Need enough data points
            print(f"  Not enough data for {scenario1_label} vs {scenario2_label} for KPI {kpi}")
            stat, p_value = np.nan, np.nan
        else:
            try:
                stat, p_value = mannwhitneyu(data1, data2, alternative='two-sided')
                print(f"  {scenario1_label} vs {scenario2_label}: U-stat={stat:.2f}, p-value={p_value:.4f} {'(Significant)' if p_value < 0.05 else '(Not Significant)'}")
            except ValueError as e: # May cause U-test problems because the data is the same
                print(f"  Could not perform test for {scenario1_label} vs {scenario2_label} for KPI {kpi}: {e}")
                stat, p_value = np.nan, np.nan
        
        test_results.append({
            "KPI": kpi,
            "Comparison": f"{scenario1_label} vs {scenario2_label}",
            "U_Statistic": stat,
            "P_Value": p_value,
            "Significant (p<0.05)": "Yes" if p_value < 0.05 else ("No" if not np.isnan(p_value) else "N/A")
        })

df_test_results = pd.DataFrame(test_results)
print("\n\n--- Mann-Whitney U Test Summary Table ---")
print(df_test_results.to_string())

# --- Save Results to CSV ---
df_results.to_csv("all_experiment_raw_results.csv", index=False)
summary_stats.to_csv("experiment_summary_statistics.csv", index=False)
df_test_results.to_csv("mann_whitney_u_test_results.csv", index=False)
print("\n\nRaw results, summary statistics, and test results saved to CSV files.")