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

Four primary scenarios are investigated:
1.  **Baseline:** A single UE (UE1) connection using its defined high-bandwidth traffic profile, but without relying on specific slice-based QoS differentiation at the core network (i.e., the S-NSSAI requested is treated with default/best-effort QoS by SMF/PCF for this scenario).
2.  **High-Only:** A single UE (UE1) operating exclusively on a configured eMBB-High bandwidth slice, with corresponding S-NSSAI and QoS parameters defined in the core network.
3.  **Medium-Only:** A single UE (UE2) operating exclusively on a configured eMBB-Medium bandwidth slice, with corresponding S-NSSAI and QoS parameters defined in the core network.
4.  **Competing:** Both UE1 (eMBB-High) and UE2 (eMBB-Medium) are active concurrently, generating traffic to assess slice isolation and performance under contention.

A significant consideration in this research is the default free5GC User Plane Function's (UPF) gtp5g kernel module, which, while supporting QoS parameter configuration, has known limitations in strictly enforcing Guaranteed Bit Rate (GBR) and Maximum Bit Rate (MBR) policies at the data plane level. This aspect will be crucial in interpreting the performance results.

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

* The environment is deployed using `docker-compose` based on the `free5gc-compose` project structure.
* All free5GC NFs (NRF, AMF, SMF, UPF, PCF, AUSF, UDM, UDR, NSSF, CHF), MongoDB, WebUI, Prometheus, cAdvisor, and UERANSIM components (gNB, UEs) are run as Docker containers.
* Custom configuration files from a designated directory (e.g., `./custom_configs/`) are volume-mounted into respective containers.
* The `gtp5g` kernel module (compatible with the free5GC version) must be compiled and installed on the host machine.
* Host IP forwarding and NAT (MASQUERADE) rules are configured to allow UEs to access external networks via the UPF, if required by the test.

## 3. Core Network Configuration & Troubleshooting Summary

Achieving a stable multi-slice environment involved several critical configuration adjustments based on an iterative troubleshooting process. The key final settings and resolutions are detailed below:

### 3.1. S-NSSAI (Single Network Slice Selection Assistance Information) Configuration

* **Initial Problem**: Misalignments in Slice Differentiator (SD) values between UERANSIM UE requests (e.g., `sd: "000101"` in `ueX.yaml`) and how they are interpreted/configured within the Core Network NFs (e.g., AMF expecting `sd: "000065"`). This led to slice selection failures or PDU session rejections with "DNN not supported in slice" errors.
* **Resolution & Detailed Configuration**:
    * **Mapping**: It was established that UE-requested SD values `"000101"` (for eMBB-High) and `"000102"` (for eMBB-Medium) correspond to `"000065"` and `"000066"` respectively within the Core Network (AMF, SMF, NSSF).
    * **UERANSIM UE (`custom_configs/ue1.yaml`, `custom_configs/ue2.yaml`)**:
        * UE1 (eMBB-High request): `sessions.slice.sd` was set to `"000101"`. `configured-nssai` and `default-nssai` also reflected this (sst:1, sd:"000101").
        * UE2 (eMBB-Medium request): `sessions.slice.sd` was set to `"000102"`. `configured-nssai` and `default-nssai` also reflected this (sst:1, sd:"000102").
    * **AMF (`custom_configs/amfcfg.yaml`)**:
        * `plmnSupportList[0].snssaiList` configured to support the AMF-interpreted SD values:
            ```yaml
            plmnSupportList:
              - plmnId: { mcc: "208", mnc: "93" }
                snssaiList:
                  - sst: 1
                    sd: "000065" # Corresponds to UE1's "000101" request
                  - sst: 1
                    sd: "000066" # Corresponds to UE2's "000102" request
            ```
    * **SMF (`custom_configs/smfcfg.yaml`)**:
        * `snssaiInfos[].sNssai.sd` updated to use the core network SD values:
            ```yaml
            snssaiInfos:
              - sNssai: { sst: 1, sd: "000065" } # eMBB-High (matches AMF)
                dnnInfos: [{ dnn: internet, dns: { ipv4: 8.8.8.8 } }]
              - sNssai: { sst: 1, sd: "000066" } # eMBB-Medium (matches AMF)
                dnnInfos: [{ dnn: internet, dns: { ipv4: 8.8.8.8 } }]
            ```
        * `userplaneInformation.upNodes.UPF.sNssaiUpfInfos[].sNssai.sd` also aligned:
            ```yaml
            sNssaiUpfInfos:
              - sNssai: { sst: 1, sd: "000065" } # eMBB-High
                dnnUpfInfoList: [{ dnn: internet, pools: [{ cidr: "10.60.0.0/16" }] }]
              - sNssai: { sst: 1, sd: "000066" } # eMBB-Medium
                dnnUpfInfoList: [{ dnn: internet, pools: [{ cidr: "10.61.0.0/16" }] }]
            ```
    * **NSSF (`custom_configs/nssfcfg.yaml`)**:
        * `supportedNssaiInPlmnList[].supportedSnssaiList` and `nsiList[].snssai.sd` were configured to include `"000065"` and `"000066"` mapped to appropriate NSI IDs (e.g., "101" and "102" respectively).
    * **UERANSIM gNB (`custom_configs/gnb.yaml`)**:
        * `slices` list was configured with the core network interpreted SD values:
            ```yaml
            slices:
              - sst: 1
                sd: "000065"
              - sst: 1
                sd: "000066"
            ```
    * **WebUI/UDM Subscriber Data**:
        * UE1 (imsi-...001) was provisioned with S-NSSAI (SST:1, SD:"000065") for DNN "internet".
        * UE2 (imsi-...002) was provisioned with S-NSSAI (SST:1, SD:"000066") for DNN "internet".
        * GPSI (MSISDN) fields were ensured to be unique or blank to prevent "duplicate gpsi" errors during UE provisioning.

### 3.2. NRF OAuth2 Configuration

* **Initial Problem**: AMF experienced "401 Unauthorized" errors when attempting to discover AUSF via NRF, or NFs logged "OAuth2 required but not supported by NRF" if NRF had OAuth2 disabled while clients expected it. This caused UE registration failures.
* **Resolution & Detailed Configuration**: NRF OAuth2 was **disabled** to simplify NF interactions and resolve authentication/authorization issues between NFs.
    * In `custom_configs/nrfcfg.yaml`:
        ```yaml
        configuration:
          sbi:
            # ... other sbi settings ...
            oauth: false # Set to false
        ```
    * This change required a full environment restart (`sudo docker compose down --remove-orphans && sudo docker compose up -d`) for all NFs. Subsequently, other NFs (AMF, PCF, SMF, etc.) logged `OAuth2 setting receive from NRF: false`.

### 3.3. PCF Configuration and WebUI QoS Simplification

* **Initial Problem**: PCF consistently panicked (`runtime error: index out of range`) in `smpolicy.go:263` when SMF made `Npcf_SMPolicyControl_Create` requests. This blocked PDU session establishment.
* **Resolution & Detailed Configuration**:
    * **`custom_configs/pcfcfg.yaml`**: Ensured this file was the original default version (1.0.2), without any custom `smPolicyData` blocks. The `logger.level` was set to `debug` during troubleshooting. The `serviceList` included `npcf-smpolicycontrol` with `suppFeat: "3fff"`.
        ```yaml
        # custom_configs/pcfcfg.yaml (relevant parts)
        info:
          version: 1.0.2
        # ...
        serviceList:
          - serviceName: npcf-am-policy-control
          - serviceName: npcf-smpolicycontrol
            suppFeat: "3fff"
          # ... other services ...
        logger:
          level: info # Set to info for performance runs, debug for troubleshooting
        ```
    * **WebUI/UDM QoS Profile Simplification (Critical Fix)**: The PCF panic was resolved by **removing all configured Flow Rules** for the UE subscriptions (for both S-NSSAI `"000065"`/DNN `internet` and `"000066"`/DNN `internet`) in the free5GC WebUI. Only basic Session AMBR and Default 5QI values were retained.

### 3.4. SMF User Plane Routing (`uerouting.yaml`)

* **Initial Problem**: Potential SMF errors due to complex or misconfigured UPF topology/paths in `uerouting.yaml`.
* **Resolution**: `custom_configs/uerouting.yaml` was simplified to ensure a clear path to the single "UPF" node for all relevant SUPIs and DNNs. For example:
    ```yaml
    # custom_configs/uerouting.yaml (simplified example)
    UERoutingInfo:
     - SUPI: "imsi-208930000000001"
       AN: "gNB1"
       PathList:
         - DestinationIP: "0.0.0.0/0"
           UPF: "UPF"
     - SUPI: "imsi-208930000000002"
       AN: "gNB1"
       PathList:
         - DestinationIP: "0.0.0.0/0"
           UPF: "UPF"
    ```

### 3.5. NSSF Configuration (`nssfcfg.yaml`)

* **Initial Problem**: NSSF logs showed warnings: `No TA ... tac:"000001" ... in NSSF configuration`, while the `tac` in `nssfcfg.yaml` was set to `"1"`.
* **Resolution & Detailed Configuration**: The `tac` value within the `amfSetList[].supportedNssaiAvailabilityData[].tai` section was changed to `"000001"` (matching the 6-digit hex format used by AMF/gNB).
    ```yaml
    # custom_configs/nssfcfg.yaml (relevant part)
    amfSetList:
      - amfSetId: "1"
        supportedNssaiAvailabilityData:
          - tai:
              plmnId: { mcc: "208", mnc: "93" }
              tac: "000001" # Corrected TAC format
            supportedSnssaiList:
              - { sst: 1, sd: "000065" }
              - { sst: 1, sd: "000066" }
              # Other SDs like "010203", "112233" were also present under this TAC
    ```

### 3.6. Required Packages in Containers

* **Initial Problem**: `iperf3`, `pkill`, and `killall` commands were not available by default in UERANSIM UE or UPF containers.
* **Resolution**: The `iperf3` and `psmisc` (which provides `killall`) packages were installed in these containers using `apt-get update && apt-get install -y iperf3 psmisc`. This is handled by the experiment script.

## 4. Experiment Design

### 4.1. Slice Definitions & UE Configuration

* **eMBB-High Slice (Targeted by UE1)**:
    * UE Request (`custom_configs/ue1.yaml`): SST=1, SD="000101"
    * Core Network Processing (AMF, SMF, NSSF, WebUI/UDM): Interpreted as SST=1, SD="000065"
    * Target iperf3 (UE1): `-b 75M -P 2` (total 150 Mbps target)
* **eMBB-Medium Slice (Targeted by UE2)**:
    * UE Request (`custom_configs/ue2.yaml`): SST=1, SD="000102"
    * Core Network Processing (AMF, SMF, NSSF, WebUI/UDM): Interpreted as SST=1, SD="000066"
    * Target iperf3 (UE2): `-b 4M -P 10` (total 40 Mbps target)
* Both slices utilize the DNN `internet`.

### 4.2. Experiment Scenarios

1.  **Baseline**: UE1 active, requesting slice (SST=1, SD="000101"), treated with default/best-effort QoS handling by the core network for this scenario.
2.  **High-Only**: UE1 active, requesting slice (SST=1, SD="000101"), with specific eMBB-High QoS parameters intended at the core network.
3.  **Medium-Only**: UE2 active, requesting slice (SST=1, SD="000102"), with specific eMBB-Medium QoS parameters intended at the core network.
4.  **Competing**: UE1 (requesting eMBB-High) and UE2 (requesting eMBB-Medium) active simultaneously.

### 4.3. Key Performance Indicators (KPIs)

* **Throughput (Mbps)**: Measured using iperf3 (UDP).
* **End-to-End Latency (RTT, ms)**: Measured using ping (average and 95th percentile).
* **Jitter (ms)**: Reported by iperf3 (UDP).
* **Packet Loss Rate (%)**: Reported by iperf3 (UDP) and ping.
* **Resource Consumption**: CPU utilization (%), Memory usage (MB), Network I/O (Bytes/sec) for NF containers, to be collected via Prometheus & cAdvisor.

## 5. Experiment Execution Procedure

The `run_experiment.sh` script automates the execution of the four scenarios for `TOTAL_REPETITIONS` (e.g., 5 times).

### 5.1. Script Overview:

1.  **Setup**: Ensures 5GC NFs are running; installs `iperf3` and `psmisc` in UPF and UE containers.
2.  **Loop through Repetitions**: For each repetition number from 1 to `TOTAL_REPETITIONS`.
3.  **Loop through Scenarios**:
    * **Pre-Scenario Manual Step**: Prompts user to ensure `custom_configs/ueransim-ueX.yaml` files are correctly set for the current scenario (slice SD values).
    * Starts gNB and relevant UE(s).
    * **UE PDU Session Check**: Prompts user to verify PDU session establishment for active UE(s).
    * **File Cleanup**: Deletes result files from previous runs for the current scenario and repetition number.
    * **iperf3 Server(s)**:
        * For single-UE scenarios: Starts one `iperf3 -s` instance on UPF on port `IPERF_SERVER_PORT_DEFAULT`.
        * For Competing scenario: Starts **two** `iperf3 -s` instances on UPF, one on `IPERF_SERVER_PORT_UE1_COMP` (e.g., 5201) for UE1, and another on `IPERF_SERVER_PORT_UE2_COMP` (e.g., 5202) for UE2.
    * **Traffic Generation**: `ping` and `iperf3` clients are started in the background for each active UE, targeting the appropriate UPF server port(s).
    * **Wait**: Script waits for `EXPERIMENT_DURATION` (e.g., 300 seconds for formal runs) plus a buffer.
    * **Collect Results**: Copies iperf3 JSON from UEs to host; ping logs are already on host.
    * **Cleanup**: Stops iperf3 server(s) and then the UE container(s) for the scenario.
4.  **Final Cleanup**: Stops gNB after all repetitions and scenarios are complete.

### 5.2. Manual Configuration Reminder during Script Execution:

The script will pause and require manual intervention/confirmation for:
* Ensuring the correct `custom_configs/ueransim-ueX.yaml` is configured for the slice definition of the upcoming scenario.
* Confirming UEs have successfully established PDU sessions.

## 6. Data Analysis

After data collection:
1.  **Parsing**: The `analyze_experiment_results.py` Python script parses iperf3 JSON files and ping log files.
2.  **Aggregation**: Results are compiled into a Pandas DataFrame.
3.  **Summary Statistics**: Mean, standard deviation are calculated for each KPI per scenario.
4.  **Statistical Testing**: Mann-Whitney U tests are performed to compare KPIs between scenario pairs (p < 0.05 for significance).
5.  **Resource Consumption**: Prometheus data for CPU, memory, and network I/O of NFs will be queried for each test run's timeframe and analyzed.

## 7. Known Limitations

* **QoS Enforcement**: The default free5GC UPF (gtp5g) does not strictly enforce MBR/GBR or provide advanced QFI-based scheduling. Observed performance differentiation may be limited.
* **Simulation Environment**: Results are from a simulated RAN/UE environment.
* **Single Host Resource Contention**: All components run on a single host.

## 8. Example Output Files (Collected in `experiment_results/`)

`run_experiment.sh`
- `ueransim-ue1_baseline_iperf_repN.json`
- `ueransim-ue1_baseline_ping_repN.log`
- `ueransim-ue1_high_only_iperf_repN.json`
- `ueransim-ue2_medium_only_ping_repN.log`
- `ueransim-ue1_competing_high_iperf_repN.json`
- `ueransim-ue2_competing_medium_iperf_repN.json`

`analyze_experiment_results.py`
* `all_experiment_raw_results.csv`
* `experiment_summary_statistics.csv`
* `mann_whitney_u_test_results.csv`

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