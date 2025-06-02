# Experiment Results (Performance Evaluation of 5G eMBB Network Slicing for Simulated Smart Factory Video Streams using free5GC)

**113-2 5G Network Foundation - Team 1**

Advisor: Shu-hao Liang

TA: Marnel Patrick Junior Altius

Student: Hua-chen Shih (M11351020), VO THANH TUNG (D11203820)

---

## 1. Introduction and Purpose

This document details the research methodology and experimental procedure for evaluating 5G Enhanced Mobile Broadband (eMBB) network slicing capabilities. The primary objective is to establish a software-based 5G network using Docker Compose, simulate video streaming traffic (UDP) typical of smart factory environments (e.g., machine vision, remote monitoring, AR/VR assisted operations), and assess the impact of different slice configurations on network Key Performance Indicators (KPIs) and container resource consumption.

The study employs free5GC as the 5G Core (5GC) and UERANSIM as the Radio Access Network (RAN) and User Equipment (UE) simulator, all containerized using Docker Compose for ease of deployment and management. KPIs including throughput, Round-Trip Time (RTT), jitter, and packet loss rate will be measured. Resource utilization (CPU, memory, network I/O) of the containerized Network Functions (NFs) will also be monitored.

The core comparison in this analysis focuses on two competitive scenarios:
1.  **Baseline-Competing:** Two UEs (UE1 with a high-bandwidth traffic profile, UE2 with a medium-bandwidth traffic profile) operate concurrently, both configured to use a **shared, default network policy** without specific S-NSSAI-based differentiation for QoS.
2.  **Slicing-Competing:** The same two UEs operate concurrently, but UE1 requests a dedicated eMBB-High slice and UE2 requests a dedicated eMBB-Medium slice, with distinct S-NSSAIs and associated (configured) QoS parameters.

This comparison aims to determine if logical slice separation provides tangible performance benefits or isolation under contention compared to a shared resource scenario. A significant consideration is the default free5GC User Plane Function's (UPF) gtp5g kernel module, which has known limitations in strictly enforcing Guaranteed Bit Rate (GBR) and Maximum Bit Rate (MBR) policies at the data plane level.

## 2. Experiment Environment

### 2.1. Host & Software Specifications

* **Host Machine:**
    * CPU: Intel® Core™ i7-10700 (8 Cores / 16 Threads)
    * RAM: 16 GB
    * OS: Ubuntu 24.04.2 LTS
    * Kernel: Linux 6.11.0-26-generic
* **Core Network (5GC):** free5GC v4.0.1
* **RAN/UE Simulator:** UERANSIM v3.2.7
* **Containerization:** Docker Engine & Docker Compose v2
* **Monitoring:** Prometheus & cAdvisor
* **Traffic Tools:** iperf3 & ping
* **Data Analysis:** Python 3.12.3 (pandas, scipy, numpy, json, re)

### 2.2. Docker Compose Setup

* The environment is deployed using `docker-compose` based on the `free5gc-compose` project.
* All free5GC NFs, MongoDB, WebUI, Prometheus, cAdvisor, and UERANSIM components are containerized.
* Custom configuration files from `./custom_configs/` are volume-mounted.
* The `gtp5g` kernel module is installed on the host.
* Host IP forwarding and NAT rules are configured.

## 3. Core Network Configuration & Troubleshooting Summary

A stable multi-slice environment was achieved through iterative configuration and troubleshooting. Key final settings include:

### 3.1. S-NSSAI (Single Network Slice Selection Assistance Information) Configuration

* **Problem Resolution**: Ensured consistency in Slice Differentiator (SD) values. UE-requested SDs (`"000101"` for High, `"000102"` for Medium in `ueX.yaml`) were mapped to their Core Network (AMF-interpreted) equivalents (`"000065"` for High, `"000066"` for Medium) across all relevant NF configurations and UDM data for the "Slicing-Competing" scenario.
* **For "Baseline-Competing" scenario**: UEs were configured to request a shared/default S-NSSAI (e.g., by omitting specific slice requests in `ueX.yaml` or by configuring them to request the same default S-NSSAI like `sst: 1, sd: "000000"`), which was then mapped to a common PDU session policy and IP pool in SMF.
* **AMF (`custom_configs/amfcfg.yaml`)**: `plmnSupportList[0].snssaiList` configured accordingly for both scenarios (supporting specific SDs for slicing, and the shared/default SD for baseline competing).
* **SMF (`custom_configs/smfcfg.yaml`)**:
    * For Slicing: `snssaiInfos` and `userplaneInformation.upNodes.UPF.sNssaiUpfInfos` configured with `sd: "000065"` (Pool: `10.60.0.0/16`) and `sd: "000066"` (Pool: `10.61.0.0/16`).
    * For Baseline-Competing: A common `sNssaiInfo` (e.g., `sst:1, sd:"000000"`) was configured with a shared DNN and IP pool (e.g., `10.60.0.0/16`).
* **NSSF (`custom_configs/nssfcfg.yaml`)**: `supportedNssaiInPlmnList` and `nsiList` configured to support all relevant S-NSSAIs (specific ones for slicing, and the shared one for baseline).
* **UERANSIM gNB (`custom_configs/gnb.yaml`)**: `slices` list configured to support all S-NSSAIs being tested.
* **WebUI/UDM**:
    * For Slicing: Subscribers provisioned with distinct S-NSSAIs (SDs `"000065"`, `"000066"`).
    * For Baseline-Competing: Subscribers provisioned to use the shared S-NSSAI or default PDU session policy.
    * GPSI (MSISDN) fields ensured to be unique or blank.

### 3.2. NRF OAuth2 Configuration

* **Problem Resolution**: AMF "401 Unauthorized" errors during AUSF discovery were resolved by disabling NRF OAuth2.
* **`custom_configs/nrfcfg.yaml`**: `configuration.sbi.oauth` set to `false`.

### 3.3. PCF Configuration and WebUI QoS Simplification

* **Problem Resolution**: PCF `index out of range` panics during SM Policy creation were resolved.
* **`custom_configs/pcfcfg.yaml`**: Maintained as the original default version (1.0.2).
* **WebUI/UDM QoS Profile Simplification (Critical Fix)**: All configured **Flow Rules were removed** from UE subscriptions in the WebUI. Only basic Session AMBR and Default 5QI values were kept.

### 3.4. SMF User Plane Routing (`uerouting.yaml`)

* **Resolution**: Simplified to ensure valid routing paths to the "UPF" node.

### 3.5. NSSF Configuration (`nssfcfg.yaml`)

* **Problem Resolution**: NSSF "No TA" warnings resolved.
* **`custom_configs/nssfcfg.yaml`**: `amfSetList[].supportedNssaiAvailabilityData[].tai.tac` set to `"000001"`.

### 3.6. Required Packages in Containers

* **Resolution**: `iperf3` and `psmisc` (for `killall`) were installed in UPF and UERANSIM UE containers via the experiment script.

## 4. Experiment Design

### 4.1. Traffic Profiles (UE Configuration)

* **UE1 (High-Bandwidth Profile)**:
    * Target iperf3: `-b 75M -P 2` (total 150 Mbps UDP).
    * In "Slicing-Competing": Requests eMBB-High slice (SST=1, SD="000101" in `ue1.yaml`, maps to CN SD="000065").
* **UE2 (Medium-Bandwidth Profile)**:
    * Target iperf3: `-b 4M -P 10` (total 40 Mbps UDP).
    * In "Slicing-Competing": Requests eMBB-Medium slice (SST=1, SD="000102" in `ue2.yaml`, maps to CN SD="000066").
* Both UEs use DNN `internet`.

### 4.2. Experiment Scenarios Compared

1.  **Baseline-Competing**: UE1 (High-Traffic) and UE2 (Medium-Traffic) operate concurrently. Both UEs are configured to use a shared, default network policy (e.g., by omitting specific slice requests in their respective `.yaml` files or by requesting a common default S-NSSAI like `sst:1, sd:"000000"` which is mapped to a single best-effort PDU session policy in SMF and UDM).
2.  **Slicing-Competing**: UE1 operates in its eMBB-High slice (requesting S-NSSAI for SD="000065" via its YAML) and UE2 operates in its eMBB-Medium slice (requesting S-NSSAI for SD="000066" via its YAML) concurrently. Distinct QoS parameters are configured for these slices in the UDM/PCF (though UPF enforcement is limited).

### 4.3. Key Performance Indicators (KPIs)

* Throughput (Mbps, iperf3 UDP)
* RTT (ms, ping: average, 95th percentile)
* Jitter (ms, iperf3 UDP)
* Packet Loss Rate (%, iperf3 UDP & ping)

## 5. Experiment Execution Procedure

Executed using `run_experiment.sh` script for `TOTAL_REPETITIONS = 5` and `EXPERIMENT_DURATION = 180` seconds.

### 5.1. Script Workflow Summary for Competing Scenarios:

1.  **Initial Setup**: Ensures 5GC NFs are running; installs tools in UPF and UE containers.
2.  **Outer Loop (Repetitions)**: Iterates 5 times.
3.  **Scenario Execution (Baseline-Competing then Slicing-Competing)**:
    * **UE Configuration Prompt**: Pauses for manual confirmation/adjustment of `custom_configs/ueransim-ueX.yaml` to reflect either shared policy (for Baseline-Competing) or distinct slice requests (for Slicing-Competing).
    * Starts gNB, UE1, and UE2.
    * **PDU Session Verification**: Pauses for manual confirmation for both UEs.
    * **Cleans Old Results**: Deletes previous log/JSON files for the current scenario and repetition.
    * **iperf3 Servers on UPF**: Two `iperf3 -s` instances started on UPF on distinct ports (5201 for UE1 traffic, 5202 for UE2 traffic).
    * **Traffic Generation**: `ping` and `iperf3` clients run in background from UE1 and UE2.
    * **Wait & Collect**: Waits for test duration, then copies iperf3 JSON from UEs to host.
    * **Cleanup**: Stops iperf3 servers and UE containers.
4.  **Final gNB Stop**.

## 6. Data Analysis & Results (5 Repetitions, 180s Duration)

Data was collected and processed using `analyze_competing_scenarios.py`.

### 6.1. Summary Statistics (Average of 5 Repetitions)

| Scenario_Label                          | Avg_Throughput_Mbps | Std_Throughput_Mbps | Avg_Jitter_ms | Std_Jitter_ms | Avg_RTT_ms | Std_RTT_ms | Avg_RTT_95p_ms | Std_RTT_95p_ms |
| :-------------------------------------- | :------------------ | :------------------ | :------------ | :------------ | :--------- | :--------- | :------------- | :------------- |
| Baseline-Competing (UE1-HighTraffic)    | 149.999268          | 0.000055            | 0.005789      | 0.005007      | 0.0252     | 0.000837   | 0.067800       | 0.005541       |
| Baseline-Competing (UE2-MediumTraffic)  | 40.000181           | 0.000002            | 0.011180      | 0.005932      | 0.0254     | 0.000548   | 0.066610       | 0.007135       |
| Slicing-Competing (UE1-HighSlice)     | 149.999226          | 0.000016            | 0.003227      | 0.001538      | 0.0256     | 0.001517   | 0.068210       | 0.005656       |
| Slicing-Competing (UE2-MediumSlice)   | 40.000180           | 0.000002            | 0.007635      | 0.002371      | 0.0266     | 0.000894   | 0.069600       | 0.002074       |

*Packet loss (iperf3 and ping) was 0% for all scenarios and repetitions.*

### 6.2. Statistical Significance (Mann-Whitney U Test, p-values from 5 Repetitions)

* **Throughput (Mbps)**:
    * Baseline-Competing (UE1-HighTraffic) vs. Slicing-Competing (UE1-HighSlice): p=0.0593 (Not Significant at α=0.05)
    * Baseline-Competing (UE2-MediumTraffic) vs. Slicing-Competing (UE2-MediumSlice): p=0.2073 (Not Significant)
* **Jitter (ms)**:
    * Baseline-Competing (UE1-HighTraffic) vs. Slicing-Competing (UE1-HighSlice): p=0.8413 (Not Significant)
    * Baseline-Competing (UE2-MediumTraffic) vs. Slicing-Competing (UE2-MediumSlice): p=0.3095 (Not Significant)
* **Average RTT (ms)**:
    * Baseline-Competing (UE1-HighTraffic) vs. Slicing-Competing (UE1-HighSlice): p=0.3711 (Not Significant)
    * Baseline-Competing (UE2-MediumTraffic) vs. Slicing-Competing (UE2-MediumSlice): p=0.0420 (**Significant**)
* **95th Percentile RTT (ms)**:
    * Baseline-Competing (UE1-HighTraffic) vs. Slicing-Competing (UE1-HighSlice): p=0.8325 (Not Significant)
    * Baseline-Competing (UE2-MediumTraffic) vs. Slicing-Competing (UE2-MediumSlice): p=0.5296 (Not Significant)

*(Packet loss KPIs were not significantly different as they were consistently 0%).*

### 6.3. Interpretation of Results: "Baseline-Competing" vs. "Slicing-Competing"

This experiment compared the performance of two UEs with different traffic profiles under two competitive scenarios: "Baseline-Competing" (both UEs share a default, undifferentiated network policy) and "Slicing-Competing" (UEs are assigned to logically distinct S-NSSAIs intended for high and medium bandwidth eMBB services).

* **Throughput and Jitter Performance**:
    * For both UE1 (High-Traffic/High-Slice) and UE2 (Medium-Traffic/Medium-Slice), there were **no statistically significant differences in average throughput or jitter** when comparing the "Baseline-Competing" scenario to the "Slicing-Competing" scenario.
    * Both UEs consistently achieved their target iperf3 throughput rates (approx. 150 Mbps for UE1, approx. 40 Mbps for UE2) in both competitive setups, with 0% packet loss.
    * This suggests that, under the tested load conditions and with the existing UPF capabilities, the logical separation provided by S-NSSAIs did not translate into a measurable improvement or degradation in terms of achieved throughput or jitter for either UE profile compared to a shared policy environment.

* **Latency (RTT) Performance**:
    * **UE1 (High-Traffic/High-Slice)**: No statistically significant differences were observed in average RTT or 95th percentile RTT between the two competitive scenarios.
    * **UE2 (Medium-Traffic/Medium-Slice)**: A **statistically significant difference was found in average RTT** (p=0.0420). In the "Slicing-Competing" scenario, UE2's average RTT was slightly higher (0.0266 ms) compared to the "Baseline-Competing" scenario (0.0254 ms). However, the 95th percentile RTT did not show a significant difference (p=0.5296).
    * The slight but statistically significant increase in average RTT for UE2 when specific slicing was applied (compared to baseline competition) is an unexpected finding if slicing is presumed to improve or at least not degrade performance for a given traffic profile under contention. This could potentially indicate minor additional processing overhead related to slice-specific policy handling in the core network that manifests under load, or it could be within the noise floor of such low-latency measurements. Given the 95th percentile RTT was not significantly different, the practical impact of this average RTT change is minimal.

* **Overall Impact of Slicing under Contention**:
    * The results suggest that, for the KPIs measured (throughput, jitter, RTT, packet loss), **configuring distinct S-NSSAIs in the "Slicing-Competing" scenario did not offer a clear and consistent performance advantage or demonstrably better isolation for either UE compared to the "Baseline-Competing" scenario** where both UEs shared a default policy.
    * Both UEs were able to achieve their target throughputs in both competitive settings, and packet loss remained zero.
    * The primary statistically significant difference observed was a slight increase in average RTT for the medium-traffic UE (UE2) when specific slicing policies were active during contention, compared to when it competed under a shared default policy.

## 7. Known Limitations

* **QoS Enforcement by free5GC UPF (gtp5g)**: This is the most critical limitation. The default gtp5g kernel module has limited capabilities for strict GBR/MBR enforcement and QFI-based priority scheduling. The observed lack of strong performance differentiation or isolation benefits from slicing in this setup is likely attributable to this UPF limitation. While S-NSSAIs enable logical separation and policy assignment at the control plane, without robust data plane mechanisms, UEs largely share resources in a best-effort manner.
* **Simulation Environment**: Results are from a simulated RAN/UE environment.
* **Single Host Resource Contention**: All components run on a single host.

## 8. Conclusion

This study investigated the performance impact of S-NSSAI-based network slicing in a free5GC environment under concurrent traffic load, comparing it to a scenario where UEs with different traffic profiles competed under a shared default network policy. Experiments were conducted over 5 repetitions with a 180-second duration per test.

**Key Conclusions**:

1.  **Limited Impact of Logical Slicing on Throughput and Jitter in Competitive Scenarios**: For both the high-bandwidth (UE1) and medium-bandwidth (UE2) traffic profiles, introducing S-NSSAI-based logical slicing did not result in statistically significant improvements or degradations in average throughput or jitter when compared to a scenario where both UEs competed under a common, undifferentiated policy. Both UEs consistently achieved their target throughputs in both competitive settings, with negligible packet loss.
2.  **Latency (RTT) Observations**:
    * For the high-bandwidth UE (UE1), no significant difference in RTT (average or 95th percentile) was observed between the "Slicing-Competing" and "Baseline-Competing" scenarios.
    * For the medium-bandwidth UE (UE2), a statistically significant, albeit small, **increase in average RTT** was observed when specific slicing was applied during contention, compared to the baseline competing scenario. However, its 95th percentile RTT did not show a significant difference.
3.  **Implications of UPF QoS Limitations**: The overall lack of strong performance differentiation or clear isolation benefits attributable to S-NSSAI based slicing in this experiment is largely consistent with the known limitations of the default free5GC UPF (gtp5g) in enforcing granular QoS at the data plane. While slices can be logically defined and policies assigned, the actual traffic treatment in terms of rate enforcement and prioritization appears to be minimal in the tested UPF.
4.  **Recommendation for Slicing**: Based on these results, in environments with similar UPF capabilities and where network resources are not severely congested to the point of significant packet loss, **implementing S-NSSAI-based logical slicing alone may not yield substantial performance isolation or benefits over a well-provisioned shared network for the tested UDP traffic profiles.** The decision to implement slicing should consider whether the control-plane differentiation and potential for future integration with more capable UPFs outweigh the current lack of strong data-plane enforcement and any minor overheads. For scenarios demanding strict QoS guarantees and isolation, a UPF with more advanced traffic management features would likely be necessary.

Further analysis of resource consumption data (CPU, memory) from Prometheus is recommended to understand the load on different network functions under these competitive scenarios, which might offer additional context to these performance findings.