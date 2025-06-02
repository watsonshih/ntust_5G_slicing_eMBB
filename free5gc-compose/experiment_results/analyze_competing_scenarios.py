import os
import json
import re
import pandas as pd
import numpy as np
from scipy.stats import mannwhitneyu

RESULTS_DIR = "."
TOTAL_REPETITIONS = 5

SCENARIOS_INFO = {
    "baseline_competing_ue1": {
        "label": "Baseline-Competing (UE1-HighTraffic)",
        "ue_name_in_file": "baseline-ueransim-ue1",
        "scenario_tag_in_file": "competing_high"
    },
    "baseline_competing_ue2": {
        "label": "Baseline-Competing (UE2-MediumTraffic)",
        "ue_name_in_file": "baseline-ueransim-ue2",
        "scenario_tag_in_file": "competing_medium"
    },
    "slicing_competing_ue1": {
        "label": "Slicing-Competing (UE1-HighSlice)",
        "ue_name_in_file": "ueransim-ue1",
        "scenario_tag_in_file": "competing_high"
    },
    "slicing_competing_ue2": {
        "label": "Slicing-Competing (UE2-MediumSlice)",
        "ue_name_in_file": "ueransim-ue2",
        "scenario_tag_in_file": "competing_medium"
    }
}

def parse_iperf_json(filepath):
    try:
        with open(filepath, 'r') as f:
            content = f.read()

            json_data_list = []
            decoder = json.JSONDecoder()
            idx = 0
            while idx < len(content):
                content_to_decode = content[idx:].lstrip() # Remove leading whitespace
                if not content_to_decode:
                    break
                try:
                    data, json_len = decoder.raw_decode(content_to_decode)
                    json_data_list.append(data)
                    idx += json_len
                except json.JSONDecodeError:
                    # If decoding fails, look for known error patterns or skip malformed parts
                    # This part might need refinement based on how errors are embedded
                    # For now, we'll just try to find the next potential start of a JSON object
                    next_brace = content_to_decode.find('{', 1)
                    if next_brace == -1:
                        break # No more JSON objects
                    idx += (content_to_decode.find('{', next_brace) - len(content_to_decode))


            if not json_data_list:
                if "iperf3: error - unable to send control message: Connection reset by peer" in content:
                    print(f"  --> iperf client error (Connection reset by peer) in file: {filepath}")
                else:
                    print(f"  --> No valid JSON object found in: {filepath}")
                return None

            data = None
            for item in json_data_list:
                if "end" in item and "sum" in item["end"]:
                    data = item
                    break
            
            if not data:
                print(f"  --> No complete 'end.sum' section found in any JSON object within: {filepath}")
                return None


            sum_data = data["end"]["sum"]
            throughput_bps = sum_data.get("bits_per_second", 0)
            jitter_ms = sum_data.get("jitter_ms", 0)
            
            lost_packets = sum_data.get("lost_packets", 0)
            total_packets = sum_data.get("packets", 0)
            lost_percent = sum_data.get("lost_percent", 0)

            if total_packets > 0 and lost_packets > 0 and lost_percent == 0:
                lost_percent = (lost_packets / total_packets) * 100
            
            return {
                "throughput_mbps": throughput_bps / 1_000_000 if throughput_bps else None,
                "jitter_ms": jitter_ms if jitter_ms else None,
                "lost_packets": lost_packets if total_packets else None,
                "total_packets": total_packets if total_packets else None,
                "lost_percent": lost_percent if total_packets else None,
            }

    except FileNotFoundError:
        print(f"  --> File not found: {filepath}")
        return None
    except Exception as e:
        print(f"  --> Unexpected error parsing iperf file {filepath}: {e}")
        return None

def parse_ping_log(filepath):
    rtt_values = []
    summary_stats = {
        "rtt_min_ms": np.nan, "rtt_avg_ms": np.nan, "rtt_max_ms": np.nan,
        "rtt_mdev_ms": np.nan, "rtt_95p_ms": np.nan, "packet_loss_percent": np.nan
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
                summary_stats["rtt_95p_ms"] = np.percentile(rtt_values, 95)
                if pd.isna(summary_stats["rtt_avg_ms"]): # If summary line wasn't found, calculate from values
                    summary_stats["rtt_avg_ms"] = np.mean(rtt_values)
                    summary_stats["rtt_min_ms"] = np.min(rtt_values)
                    summary_stats["rtt_max_ms"] = np.max(rtt_values)
                    summary_stats["rtt_mdev_ms"] = np.std(rtt_values)
            return summary_stats
            
    except FileNotFoundError:
        print(f"  --> File not found: {filepath}")
        return summary_stats 
    except Exception as e:
        print(f"  --> Unexpected error parsing ping file {filepath}: {e}")
        return summary_stats

# --- 主處理流程 ---
all_results = []

for scenario_key, info in SCENARIOS_INFO.items():
    label = info["label"]
    ue_file_prefix = info["ue_name_in_file"]
    scenario_file_tag = info["scenario_tag_in_file"]
    
    print(f"\nProcessing scenario: {label} (key: {scenario_key})")
    
    for rep in range(1, TOTAL_REPETITIONS + 1):
        print(f" Repetition {rep}:")
        
        iperf_file = os.path.join(RESULTS_DIR, f"{ue_file_prefix}_{scenario_file_tag}_iperf_rep{rep}.json")
        ping_file = os.path.join(RESULTS_DIR, f"{ue_file_prefix}_{scenario_file_tag}_ping_rep{rep}.log")
            
        iperf_data = parse_iperf_json(iperf_file)
        ping_data = parse_ping_log(ping_file)
        
        current_result = {
            "Scenario_Key": scenario_key, # To group for comparisons
            "Scenario_Label": label,
            "Repetition": rep
        }
        
        if iperf_data:
            current_result.update(iperf_data)
        else: 
            current_result.update({
                "throughput_mbps": np.nan, "jitter_ms": np.nan,
                "lost_packets": np.nan, "total_packets": np.nan, "lost_percent": np.nan
            })
            
        if ping_data:
            current_result.update(ping_data)
        else: 
            current_result.update({
                "rtt_min_ms": np.nan, "rtt_avg_ms": np.nan, "rtt_max_ms": np.nan,
                "rtt_mdev_ms": np.nan, "rtt_95p_ms": np.nan, "packet_loss_percent": np.nan
            })
            
        all_results.append(current_result)

df_results = pd.DataFrame(all_results)

cols_ordered = [
    "Scenario_Label", "Repetition", 
    "throughput_mbps", "jitter_ms", "lost_packets", "total_packets", "lost_percent",
    "rtt_avg_ms", "rtt_95p_ms", "rtt_min_ms", "rtt_max_ms", "rtt_mdev_ms", "packet_loss_percent",
    "Scenario_Key" # Keep this for grouping if needed
]
existing_cols = [col for col in cols_ordered if col in df_results.columns]
df_results = df_results[existing_cols]

print("\n\n--- Raw Results ---")
print(df_results.to_string())

summary_stats = df_results.groupby("Scenario_Label").agg(
    Avg_Throughput_Mbps=('throughput_mbps', 'mean'), Std_Throughput_Mbps=('throughput_mbps', 'std'),
    Avg_Jitter_ms=('jitter_ms', 'mean'), Std_Jitter_ms=('jitter_ms', 'std'),
    Avg_Lost_Packets=('lost_packets', 'mean'), Avg_Lost_Percent=('lost_percent', 'mean'),
    Avg_RTT_ms=('rtt_avg_ms', 'mean'), Std_RTT_ms=('rtt_avg_ms', 'std'),
    Avg_RTT_95p_ms=('rtt_95p_ms', 'mean'), Std_RTT_95p_ms=('rtt_95p_ms', 'std'),
    Avg_Ping_Loss_Pct=('packet_loss_percent', 'mean')
).reset_index()

print("\n\n--- Summary Statistics per Scenario ---")
print(summary_stats.to_string())

print("\n\n--- Mann-Whitney U Tests (p-values) ---")
kpi_to_test = [
    'throughput_mbps', 'jitter_ms', 'lost_percent',
    'rtt_avg_ms', 'rtt_95p_ms', 'packet_loss_percent'
]

# 比較 Baseline-Competing UE1 vs Slicing-Competing UE1
# 和 Baseline-Competing UE2 vs Slicing-Competing UE2
comparison_pairs_labels = [
    ("Baseline-Competing (UE1-HighTraffic)", "Slicing-Competing (UE1-HighSlice)"),
    ("Baseline-Competing (UE2-MediumTraffic)", "Slicing-Competing (UE2-MediumSlice)"),
]

test_results = []

for kpi in kpi_to_test:
    print(f"\nTesting KPI: {kpi}")
    for scenario1_label, scenario2_label in comparison_pairs_labels:
        data1 = df_results[df_results["Scenario_Label"] == scenario1_label][kpi].dropna()
        data2 = df_results[df_results["Scenario_Label"] == scenario2_label][kpi].dropna()

        if len(data1) < 2 or len(data2) < 2: # Mann-Whitney U needs at least some data points, ideally more
            print(f"  Not enough data for {scenario1_label} (n={len(data1)}) vs {scenario2_label} (n={len(data2)}) for KPI {kpi}")
            stat, p_value = np.nan, np.nan
        else:
            try:
                stat, p_value = mannwhitneyu(data1, data2, alternative='two-sided')
                print(f"  {scenario1_label} vs {scenario2_label}: U-stat={stat:.2f}, p-value={p_value:.4f} {'(Significant at p<0.05)' if p_value < 0.05 else '(Not Significant)'}")
            except ValueError as e: 
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

df_results.to_csv("all_competing_raw_results.csv", index=False)
summary_stats.to_csv("competing_summary_statistics.csv", index=False)
df_test_results.to_csv("competing_mann_whitney_u_test_results.csv", index=False)
print("\n\nRaw results, summary statistics, and test results saved to CSV files.")