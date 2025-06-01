# Experiment Results (Performance Evaluation of 5G eMBB Network Slicing for Simulated Smart Factory Video Streams using free5GC)

**113-2 5G Network Foundation - Team 1**
Advisor: Shu-hao Liang
TA: Marnel Patrick Junior Altius
Student: Hua-chen Shih (M11351020), VO THANH TUNG (D11203820)

---

## 1. Introduction and Purpose

This document details the research methodology and experimental procedure for evaluating 5G Enhanced Mobile Broadband (eMBB) network slicing capabilities. The primary objective is to establish a software-based 5G network using Docker Compose, simulate video streaming traffic (UDP) typical of smart factory environments (e.g., machine vision, remote monitoring, AR/VR assisted operations), and assess the impact of different slice configurations on network Key Performance Indicators (KPIs) and container resource consumption.

The study employs free5GC as the 5G Core (5GC) and UERANSIM as the Radio Access Network (RAN) and User Equipment (UE) simulator, all containerized using Docker Compose for ease of deployment and management. KPIs including throughput, Round-Trip Time (RTT), jitter, and packet loss rate will be measured. Resource utilization (CPU, memory, network I/O) of the containerized Network Functions (NFs) will also be monitored.

Four primary scenarios are investigated:
1.  **Baseline:** A single UE (UE1) connection using its defined high-bandwidth traffic profile, with its S-NSSAI treated with default/best-effort QoS handling by the core network for this scenario.
2.  **High-Only:** A single UE (UE1) operating exclusively on a configured eMBB-High bandwidth slice, with corresponding S-NSSAI and QoS parameters defined in the core network.
3.  **Medium-Only:** A single UE (UE2) operating exclusively on a configured eMBB-Medium bandwidth slice, with corresponding S-NSSAI and QoS parameters defined in the core network.
4.  **Competing:** Both UE1 (eMBB-High) and UE2 (eMBB-Medium) active concurrently, generating traffic to assess slice isolation and performance under contention.

A significant consideration in this research is the default free5GC User Plane Function's (UPF) gtp5g kernel module, which, while supporting QoS parameter configuration, has known limitations in strictly enforcing Guaranteed Bit Rate (GBR) and Maximum Bit Rate (MBR) policies at the data plane level. This aspect is crucial in interpreting the performance results.

## 2. Experiment Environment

### 2.1. Host & Software Specifications

* **Host Machine:**
    * CPU: Intel® Core™ i7-10700  (8 Cores / 16 Threads)
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

* **Problem Resolution**: Ensured consistency in Slice Differentiator (SD) values. UE-requested SDs (`"000101"` for High, `"000102"` for Medium in `ueX.yaml`) were mapped to their Core Network (AMF-interpreted) equivalents (`"000065"` for High, `"000066"` for Medium) across all relevant NF configurations and UDM data.
* **AMF (`custom_configs/amfcfg.yaml`)**: `plmnSupportList[0].snssaiList` configured with `sd: "000065"` and `sd: "000066"`.
* **SMF (`custom_configs/smfcfg.yaml`)**: `snssaiInfos` and `userplaneInformation.upNodes.UPF.sNssaiUpfInfos` configured with `sd: "000065"` (Pool: `10.60.0.0/16`) and `sd: "000066"` (Pool: `10.61.0.0/16`).
* **NSSF (`custom_configs/nssfcfg.yaml`)**: `supportedNssaiInPlmnList` and `nsiList` configured with `sd: "000065"` (NSI: "101") and `sd: "000066"` (NSI: "102").
* **UERANSIM gNB (`custom_configs/gnb.yaml`)**: `slices` list configured with `sd: "000065"` and `sd: "000066"`.
* **WebUI/UDM**: Subscribers provisioned with corresponding S-NSSAIs (SDs `"000065"`, `"000066"`) and unique/blank GPSI values.

### 3.2. NRF OAuth2 Configuration

* **Problem Resolution**: AMF "401 Unauthorized" errors during AUSF discovery were resolved by disabling NRF OAuth2.
* **`custom_configs/nrfcfg.yaml`**: `configuration.sbi.oauth` set to `false`. This was a critical step for stable NF registration and discovery.

### 3.3. PCF Configuration and WebUI QoS Simplification

* **Problem Resolution**: PCF `index out of range` panics during SM Policy creation were resolved.
* **`custom_configs/pcfcfg.yaml`**: Maintained as the original default version (1.0.2).
* **WebUI/UDM QoS Profile Simplification (Critical Fix)**: All configured **Flow Rules were removed** from UE subscriptions in the WebUI. Only basic Session AMBR and Default 5QI values were kept. This stabilized PCF operation.

### 3.4. SMF User Plane Routing (`uerouting.yaml`)

* **Resolution**: Simplified to ensure valid routing paths to the "UPF" node for all SUPIs/DNNs.

### 3.5. NSSF Configuration (`nssfcfg.yaml`)

* **Problem Resolution**: NSSF "No TA" warnings were resolved by correcting the TAC format.
* **`custom_configs/nssfcfg.yaml`**: `amfSetList[].supportedNssaiAvailabilityData[].tai.tac` set to `"000001"`.

### 3.6. Required Packages in Containers

* **Resolution**: `iperf3` and `psmisc` (for `killall`) were installed in UPF and UERANSIM UE containers via the experiment script using `apt-get`.

## 4. Experiment Design

### 4.1. Slice Definitions & UE Configuration

* **eMBB-High Slice (UE1)**:
    * UE Request: SST=1, SD="000101". CN Equivalent: SD="000065".
    * Target iperf3: `-b 75M -P 2` (total 150 Mbps).
* **eMBB-Medium Slice (UE2)**:
    * UE Request: SST=1, SD="000102". CN Equivalent: SD="000066".
    * Target iperf3: `-b 4M -P 10` (total 40 Mbps).
* Both slices use DNN `internet`.

### 4.2. Experiment Scenarios

1.  **Baseline**: UE1 active, requesting its slice, treated with default QoS by CN.
2.  **High-Only**: UE1 active, eMBB-High slice specific QoS intended.
3.  **Medium-Only**: UE2 active, eMBB-Medium slice specific QoS intended.
4.  **Competing**: UE1 (eMBB-High) and UE2 (eMBB-Medium) active simultaneously.

### 4.3. Key Performance Indicators (KPIs)

* Throughput (Mbps, iperf3 UDP)
* RTT (ms, ping: average, 95th percentile)
* Jitter (ms, iperf3 UDP)
* Packet Loss Rate (%, iperf3 UDP & ping)
* Resource Consumption (CPU, Memory, Network I/O for NFs via Prometheus/cAdvisor - *analysis for this is separate from the provided Python script output*)

## 5. Experiment Execution Procedure

Executed using `run_experiment.sh` script for `TOTAL_REPETITIONS = 5` and `EXPERIMENT_DURATION = 300` seconds (script was tested with shorter durations).

### 5.1. Script Workflow Summary:

1.  **Initial Setup**: Starts all 5GC NFs. Installs `iperf3` and `psmisc` in UPF, UE1, and UE2 containers.
2.  **Outer Loop (Repetitions)**: Iterates 5 times.
3.  **Inner Loop (Scenarios)**: Sequentially executes Baseline, High-Only, Medium-Only, and Competing scenarios.
    * **UE Configuration Prompt**: Pauses for manual confirmation/adjustment of `custom_configs/ueransim-ueX.yaml` for the current scenario's slice definition.
    * Starts gNB and relevant UE(s).
    * **PDU Session Verification Prompt**: Pauses for manual confirmation of UE PDU session establishment.
    * **Cleans Old Results**: Deletes previous log/JSON files for the current scenario and repetition.
    * **iperf3 Server(s) on UPF**:
        * Single-UE scenarios: One `iperf3 -s` instance on `IPERF_SERVER_PORT_DEFAULT`.
        * Competing scenario: Two `iperf3 -s` instances on `IPERF_SERVER_PORT_UE1_COMP` (5201) and `IPERF_SERVER_PORT_UE2_COMP` (5202) respectively. Servers run in detached mode, logging to temporary files in UPF.
    * **Traffic Generation**: `ping` and `iperf3` clients are run in background from UE containers.
    * **Wait & Collect**: Waits for test duration, then copies iperf3 JSON from UEs to host.
    * **Cleanup**: Stops iperf3 server(s) and UE containers.
4.  **Final gNB Stop**: Stops gNB after all experiments.

## 6. Data Analysis & Preliminary Results

Data was collected and processed using `analyze_experiment_results.py`.

### 6.1. Summary Statistics (Average of 5 Repetitions)

| Scenario               | Avg_Throughput_Mbps | Std_Throughput_Mbps | Avg_Jitter_ms | Std_Jitter_ms | Avg_RTT_ms | Std_RTT_ms | Avg_RTT_95p_ms | Std_RTT_95p_ms |
| :--------------------- | :------------------ | :------------------ | :------------ | :------------ | :--------- | :--------- | :------------- | :------------- |
| Baseline (UE1)         | 149.999564          | 0.000015            | 0.006055      | 0.004803      | 0.0238     | 0.000837   | 0.060010       | 0.005790       |
| High-Only (UE1)        | 149.999569          | 0.000015            | 0.001971      | 0.000392      | 0.0238     | 0.001095   | 0.057250       | 0.012024       |
| Medium-Only (UE2)      | 39.999929           | 0.000003            | 0.006731      | 0.001845      | 0.0226     | 0.000548   | 0.036400       | 0.001949       |
| Competing (UE1-High)   | 149.999575          | 0.000038            | 0.003507      | 0.001667      | 0.0258     | 0.000837   | 0.068400       | 0.003782       |
| Competing (UE2-Medium) | 39.999926           | 0.000005            | 0.006554      | 0.001180      | 0.0274     | 0.000894   | 0.070020       | 0.002450       |

*Packet loss was 0% for all scenarios and repetitions.*

### 6.2. Statistical Significance (Mann-Whitney U Test, p-values)

* **Throughput (Mbps)**:
    * Baseline (UE1) vs. High-Only (UE1): p=0.7533 (Not Significant)
    * Baseline (UE1) vs. Medium-Only (UE2): p=0.0079 (**Significant**)
    * High-Only (UE1) vs. Medium-Only (UE2): p=0.0079 (**Significant**)
    * High-Only (UE1) vs. Competing (UE1-High): p=0.9166 (Not Significant)
    * Medium-Only (UE2) vs. Competing (UE2-Medium): p=0.3457 (Not Significant for throughput mean, although the previous 2-rep run showed p=0.0212. With 5 reps, the average throughput for UE2 in competing is 39.999926 vs 39.999929 in medium-only, which is virtually identical.)
* **Jitter (ms)**:
    * High-Only (UE1) vs. Medium-Only (UE2): p=0.0079 (**Significant**). (High-Only Avg: 0.001971 ms, Medium-Only Avg: 0.006731 ms).
    * Other jitter comparisons were not statistically significant with 5 repetitions.
* **Average RTT (ms)**:
    * Baseline (UE1) vs. Medium-Only (UE2): p=0.0434 (**Significant**). (Baseline Avg: 0.0258 ms, Medium-Only Avg: 0.0226 ms).
    * High-Only (UE1) vs. Competing (UE1-High): p=0.0285 (**Significant**). (High-Only Avg: 0.0238 ms, Competing UE1-High Avg: 0.0258 ms).
    * Medium-Only (UE2) vs. Competing (UE2-Medium): p=0.0099 (**Significant**). (Medium-Only Avg: 0.0226 ms, Competing UE2-Medium Avg: 0.0274 ms).
* **95th Percentile RTT (ms)**:
    * Baseline (UE1) vs. Medium-Only (UE2): p=0.0119 (**Significant**).
    * High-Only (UE1) vs. Medium-Only (UE2): p=0.0117 (**Significant**).
    * Medium-Only (UE2) vs. Competing (UE2-Medium): p=0.0114 (**Significant**). (Medium-Only Avg 95p RTT: 0.03640 ms, Competing UE2-Medium Avg 95p RTT: 0.07002 ms).

### 6.3. Interpretation of Results

* **Slice Configuration & Baseline**: Configuring a slice for UE1 (High-Only) did not significantly alter its throughput, average RTT, or jitter compared to the Baseline when UE1 was the only active UE. This is expected as both achieved the target rate.
* **Throughput Differentiation**: The system successfully delivered different target throughputs to UE1 (High) and UE2 (Medium) when they ran independently, primarily due to the iperf3 client's `-b` parameter.
* **Isolation & Contention**:
    * **UE1 (High Slice) Performance during Contention**: When UE2 (Medium) was active, UE1's throughput and jitter did not significantly change. However, its **average RTT showed a statistically significant, albeit small, increase** (from 0.0238ms to 0.0258ms). This suggests a minor impact on latency for the high-priority slice during contention.
    * **UE2 (Medium Slice) Performance during Contention**: When UE1 (High) was active, UE2's **average RTT and 95th percentile RTT significantly increased**. Its average throughput remained very close to its target and did not show a statistically significant drop with 5 repetitions (unlike the preliminary p-value with 2 repetitions). This indicates that while UE2 could still achieve its target bandwidth, its latency experience degraded noticeably under contention from the high-bandwidth slice.
* **Jitter**: The eMBB-High slice (UE1) consistently showed significantly lower jitter than the eMBB-Medium slice (UE2) when run independently.

## 7. Known Limitations

* **QoS Enforcement by free5GC UPF (gtp5g)**: The default gtp5g kernel module has limited capabilities for strict GBR/MBR enforcement and QFI-based priority scheduling. Observed performance differences are more likely due to achieved target rates set by iperf3 clients and overall system/UPF processing capacity rather than fine-grained QoS policy execution by the UPF data plane. The impact on latency during contention, however, does suggest some level of resource competition.
* **Simulation Environment**: Results are from a simulated RAN/UE environment on a single host.
* **Resource Contention**: All components run on a single host, which can lead to resource contention.

## 8. Conclusion

The configured network slicing in free5GC, within a Dockerized UERANSIM environment, allowed for the logical separation of UE traffic based on S-NSSAI.
* The "eMBB-High" slice (UE1) largely maintained its target throughput and relatively stable latency/jitter even when competing with the "eMBB-Medium" slice (UE2), although a small statistically significant increase in average RTT was observed for UE1 during contention.
* The "eMBB-Medium" slice (UE2) was more noticeably impacted by the presence of the "eMBB-High" slice, experiencing statistically significant increases in both average RTT and 95th percentile RTT. Its average throughput, however, remained close to its target even under contention with 5 repetitions.
* The results highlight that while logical slicing and policy differentiation (e.g., distinct IP pools, different 5QI in configuration) are possible, the actual data plane performance isolation, particularly for latency-sensitive aspects of lower-priority slices, is influenced by the UPF's QoS enforcement capabilities and overall system load. The observed significant RTT increases for the medium slice under contention suggest that without more robust data plane QoS enforcement, higher-demand slices can degrade the latency performance of others.

Further analysis should include resource consumption data from Prometheus to correlate these network KPIs with NF-level resource utilization.