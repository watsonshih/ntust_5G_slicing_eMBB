# Performance Evaluation of 5G eMBB Network Slicing for Simulated Smart Factory Video Streams using free5GC

**113-2 5G Network Foundation - Team 1**

Advisor: Shu-hao Liang

TA: Marnel Patrick Junior Altius

Student: Hua-chen Shih (M11351020), VO THANH TUNG (D11203820)

---

## 0. Quick start

**Start the experiment:**
```bash
cd ~/free5gc-compose/experiment_results/
chmod +x run_experiment.sh
 ./run_experiment.sh
```

**Analyze experiment results:**
```bash
cd ~/free5gc-compose/experiment_results/
python analyze_experiment_results.py
```

## 1. Introduction and Purpose

This document details the research methodology and experimental procedure for evaluating 5G Enhanced Mobile Broadband (eMBB) network slicing capabilities. The primary objective is to establish a software-based 5G network using Docker Compose, simulate video streaming traffic (UDP) typical of smart factory environments (e.g., machine vision, remote monitoring, AR/VR assisted operations), and assess the impact of different slice configurations on network Key Performance Indicators (KPIs) and container resource consumption.

The study employs free5GC as the 5G Core (5GC) and UERANSIM as the Radio Access Network (RAN) and User Equipment (UE) simulator, all containerized using Docker Compose for ease of deployment and management. KPIs including throughput, Round-Trip Time (RTT), jitter, and packet loss rate will be measured. Resource utilization (CPU, memory, network I/O) of the containerized Network Functions (NFs) will also be monitored.

The core comparison in this analysis focuses on two primary competitive scenarios:
1.  **Baseline-Competing:** Two UEs (UE1 with a high-bandwidth traffic profile, UE2 with a medium-bandwidth traffic profile) operate concurrently. Both UEs are configured to use a **shared, default network policy** (e.g., by requesting the same default S-NSSAI or by not requesting any specific slice, leading to a best-effort PDU session policy) without S-NSSAI-based QoS differentiation intended at the core network.
2.  **Slicing-Competing:** The same two UEs (UE1 and UE2) operate concurrently, but UE1 is configured to request a dedicated eMBB-High slice and UE2 requests a dedicated eMBB-Medium slice. These slices are identified by distinct S-NSSAIs, and corresponding (though potentially limited by UPF capabilities) QoS parameters are intended to be applied by the core network.

This comparative approach aims to determine if logical slice separation provides tangible performance benefits or improved isolation under contention, relative to a scenario where resources are shared under a common policy. A significant consideration is the default free5GC User Plane Function's (UPF) gtp5g kernel module, which has known limitations in strictly enforcing Guaranteed Bit Rate (GBR) and Maximum Bit Rate (MBR) policies at the data plane level.

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
    * In "Baseline-Competing": Requests a default/shared PDU session policy.
* **UE2 (Medium-Bandwidth Profile)**:
    * Target iperf3: `-b 4M -P 10` (total 40 Mbps UDP).
    * In "Slicing-Competing": Requests eMBB-Medium slice (SST=1, SD="000102" in `ue2.yaml`, maps to CN SD="000066").
    * In "Baseline-Competing": Requests a default/shared PDU session policy.
* Both UEs use DNN `internet`.

### 4.2. Experiment Scenarios Compared

1.  **Baseline-Competing**: UE1 (High-Traffic profile) and UE2 (Medium-Traffic profile) operate concurrently under a shared default network policy.
2.  **Slicing-Competing**: UE1 operates in its eMBB-High slice and UE2 operates in its eMBB-Medium slice concurrently.

### 4.3. Key Performance Indicators (KPIs)

* Throughput (Mbps, iperf3 UDP)
* RTT (ms, ping: average, 95th percentile)
* Jitter (ms, iperf3 UDP)
* Packet Loss Rate (%, iperf3 UDP & ping)

## 5. Experiment Execution Procedure

Executed using `run_experiment.sh` script for `TOTAL_REPETITIONS = 5` and `EXPERIMENT_DURATION = 180` seconds.

### 5.1. Script Workflow Summary for Competing Scenarios:

1.  **Initial Setup**: Starts all 5GC NFs. Installs `iperf3` and `psmisc` in UPF and UE containers.
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

This experiment focused on comparing the performance of two UEs with differing traffic demands under two competitive network conditions: one where both UEs operated under a shared default network policy ("Baseline-Competing"), and another where each UE was assigned to a logically distinct S-NSSAI ("Slicing-Competing").

* **Throughput and Jitter Performance**:
    * For both UE1 (High-Traffic profile) and UE2 (Medium-Traffic profile), there were **no statistically significant differences in average throughput or jitter** when comparing the "Baseline-Competing" scenario to the "Slicing-Competing" scenario.
    * Both UEs consistently achieved their target iperf3 throughput rates (approx. 150 Mbps for UE1, approx. 40 Mbps for UE2) in both competitive setups, with 0% packet loss.
    * This indicates that under the tested load conditions and with the existing UPF capabilities, the logical separation provided by S-NSSAIs did not translate into a measurable improvement or degradation in terms of achieved throughput or jitter for either UE profile compared to a shared policy environment.

* **Latency (RTT) Performance**:
    * **UE1 (High-Traffic/High-Slice)**: No statistically significant differences were observed in average RTT or 95th percentile RTT between the Baseline-Competing and Slicing-Competing scenarios.
    * **UE2 (Medium-Traffic/Medium-Slice)**:
        * A **statistically significant difference was found in average RTT** (p=0.0420). In the "Slicing-Competing" scenario, UE2's average RTT was slightly higher (0.0266 ms) compared to the "Baseline-Competing" scenario (0.0254 ms).
        * The 95th percentile RTT for UE2 did not show a statistically significant difference between the two competitive scenarios (p=0.5296).
    * The slight but statistically significant increase in average RTT for UE2 when specific slicing was applied (compared to baseline competition) suggests that the process of policy application or traffic handling for distinct slices might have introduced a minor additional latency for the medium slice in the competing environment. However, given that the 95th percentile RTT was not significantly different and the absolute difference in averages is very small (0.0012 ms), the practical impact of this specific finding on user experience might be negligible in this simulated setup.

* **Overall Impact of Slicing under Contention**:
    * The results suggest that, for most KPIs measured (throughput, jitter, 95p RTT, and UE1's average RTT), **configuring distinct S-NSSAIs ("Slicing-Competing") did not demonstrate a clear performance advantage or improved isolation over a shared policy environment ("Baseline-Competing")** for either the high-bandwidth or medium-bandwidth UE under the tested conditions.
    * The only statistically significant degradation when moving from "Baseline-Competing" to "Slicing-Competing" was a very small increase in the average RTT for UE2.
    * This implies that when the network is not severely congested to the point of inducing packet loss or drastic throughput drops, the benefits of logical-only slicing (without strong data plane enforcement) may be limited. In such scenarios, the overhead of managing distinct slice policies might even introduce marginal latency increases for some traffic, although this requires careful interpretation given the very low absolute latency values.

## 7. Known Limitations

* **QoS Enforcement by free5GC UPF (gtp5g)**: This is the most critical limitation. The default gtp5g kernel module has limited capabilities for strict GBR/MBR enforcement and QFI-based priority scheduling. The observed lack of strong performance differentiation or isolation benefits from slicing in this setup is likely attributable to this UPF limitation.
* **Simulation Environment**: Results are from a simulated RAN/UE environment on a single host.
* **Single Host Resource Contention**: All components run on a single host.

## 8. Conclusion

This study investigated the performance impact of S-NSSAI-based network slicing in a free5GC environment under concurrent traffic load, comparing it to a scenario where UEs with different traffic profiles competed under a shared default network policy. Experiments were conducted over 5 repetitions with a 180-second duration per test.

**Key Conclusions**:

1.  **Limited Performance Differentiation through Logical Slicing Alone**: In the tested competitive scenarios, the introduction of S-NSSAI-based logical slicing did not yield statistically significant improvements in throughput, jitter, or (for the most part) RTT for either the high-bandwidth or medium-bandwidth UE when compared to a scenario where both UEs shared a common default policy. Both UEs consistently achieved their target throughputs with zero packet loss regardless of the competitive policy configuration (shared vs. sliced).
2.  **Latency for Medium-Traffic UE**: A minor but statistically significant increase in *average* RTT was observed for the medium-traffic UE (UE2) when specific S-NSSAI-based slicing was applied during contention, compared to the baseline shared-policy contention. However, its 95th percentile RTT did not show a significant difference, suggesting the practical impact of this average RTT increase was likely minimal in this low-latency environment.
3.  **Impact of UPF QoS Capabilities**: The findings underscore the critical role of the User Plane Function's (UPF) QoS enforcement capabilities. The observed lack of strong performance isolation or benefit from logical slicing in this free5GC setup (using the default gtp5g kernel module) is consistent with its known limitations in strictly enforcing data plane QoS differentiation (e.g., GBR, MBR, priority scheduling).
4.  **Recommendation on Slicing Strategy**: Based on these results, in environments with similar UPF QoS enforcement limitations and where network capacity is not the primary constraining factor for the offered load, **implementing S-NSSAI-based logical slicing might not provide substantial performance advantages or isolation over a well-managed shared network policy.** The decision to implement slicing should therefore be carefully weighed. If strict QoS guarantees and robust isolation are paramount, a UPF with more advanced traffic management and enforcement features would be essential. In scenarios where overall demand is well within system capacity, the overhead or minor performance variations introduced by slice management (as hinted by UE2's average RTT) might not justify its implementation without more effective data plane mechanisms. **It suggests that a "one-size-fits-all" slicing approach may not always be optimal; instead, slicing should be strategically applied where clear differentiation and guaranteed service levels are critical and can be enforced by the underlying infrastructure.**

Further analysis of resource consumption data from Prometheus is recommended to correlate these network KPIs with NF-level resource utilization under different competitive scenarios.

## 9. References

1. How to deploy a free5GC network slice on OpenStack, accessed on May 6, 2025, [https://free5gc.org/blog/20230726/network\_slice/](https://free5gc.org/blog/20230726/network_slice/)  
2. Article Sharing: Evaluating Dedicated Slices of Different Configurations in 5G Core, accessed on May 6, 2025, [https://free5gc.org/blog/20231213/20231213/](https://free5gc.org/blog/20231213/20231213/)  
3. 5G Network Slicing \- free5GC, accessed on May 6, 2025, [https://free5gc.org/blog/20241230/20241230/](https://free5gc.org/blog/20241230/20241230/)  
4. UE Connection State Not Updating \- General Discussions \- free5GC, accessed on May 6, 2025, [https://forum.free5gc.org/t/ue-connection-state-not-updating/2542](https://forum.free5gc.org/t/ue-connection-state-not-updating/2542)  
5. Getting Error when Testing UERANSIM against free5GC \- Q/A, accessed on May 6, 2025, [https://forum.free5gc.org/t/getting-error-when-testing-ueransim-against-free5gc/1642](https://forum.free5gc.org/t/getting-error-when-testing-ueransim-against-free5gc/1642)  
6. lasseufpa/free5gc-slicing \- GitHub, accessed on May 6, 2025, [https://github.com/lasseufpa/free5gc-slicing](https://github.com/lasseufpa/free5gc-slicing)  
7. SD-Core as a Cloud Managed Service, accessed on May 6, 2025, [https://docs.sd-core.aetherproject.org/main/overview/architecture.html](https://docs.sd-core.aetherproject.org/main/overview/architecture.html)  
8. www.etsi.org, accessed on May 6, 2025, [https://www.etsi.org/deliver/etsi\_tr/138900\_138999/138913/17.00.00\_60/tr\_138913v170000p.pdf](https://www.etsi.org/deliver/etsi_tr/138900_138999/138913/17.00.00_60/tr_138913v170000p.pdf)  
9. ETSI TR 138 913 V17.0.0 (2022-05) \- iTeh Standards, accessed on May 6, 2025, [https://cdn.standards.iteh.ai/samples/65613/34a39b71d5fc43cabf517b474a3bcfe0/ETSI-TR-138-913-V17-0-0-2022-05-.pdf](https://cdn.standards.iteh.ai/samples/65613/34a39b71d5fc43cabf517b474a3bcfe0/ETSI-TR-138-913-V17-0-0-2022-05-.pdf)  
10. Error while running ueransim \- Q/A \- free5GC, accessed on May 6, 2025, [https://forum.free5gc.org/t/error-while-running-ueransim/1909](https://forum.free5gc.org/t/error-while-running-ueransim/1909)  
11. free5gc-compose/README.md at master \- GitHub, accessed on May 6, 2025, [https://github.com/free5gc/free5gc-compose/blob/master/README.md](https://github.com/free5gc/free5gc-compose/blob/master/README.md)  
12. Monitoring Docker container metrics using cAdvisor | Prometheus, accessed on May 6, 2025, [https://prometheus.io/docs/guides/cadvisor/](https://prometheus.io/docs/guides/cadvisor/)  
13. cadvisor/docs/storage/prometheus.md at master · google/cadvisor ..., accessed on May 6, 2025, [https://github.com/google/cadvisor/blob/master/docs/storage/prometheus.md](https://github.com/google/cadvisor/blob/master/docs/storage/prometheus.md)  
14. Simplifying the Process for UE using Beyond Communication Capabilities in 5G System \- DiVA portal, accessed on May 6, 2025, [http://www.diva-portal.org/smash/get/diva2:1899525/FULLTEXT01.pdf](http://www.diva-portal.org/smash/get/diva2:1899525/FULLTEXT01.pdf)  
15. The joint orchestration of edge applications and UPF CNFs over edge-cloud continuum infrastructure in 6G, accessed on May 6, 2025, [https://journals.pan.pl/Content/133222/PDF/22\_4790\_Jozwiak\_L\_sk\_new.pdf](https://journals.pan.pl/Content/133222/PDF/22_4790_Jozwiak_L_sk_new.pdf)  
16. free5gc/gtp5g: GTP-U Linux Kernel Module \- GitHub, accessed on May 6, 2025, [https://github.com/free5gc/gtp5g](https://github.com/free5gc/gtp5g)  
