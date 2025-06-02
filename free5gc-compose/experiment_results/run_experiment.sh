#!/bin/bash

# --- Global Settings ---
RESULTS_DIR_HOST="$HOME/free5gc-compose/experiment_results"
UPF_CONTAINER_NAME="upf"
GNB_CONTAINER_NAME="ueransim-gnb"
UE1_CONTAINER_NAME="ueransim-ue1"
UE2_CONTAINER_NAME="ueransim-ue2"
PING_TARGET="upf.free5gc.org"
EXPERIMENT_DURATION=300
WAIT_BUFFER=10
IPERF_SERVER_PORT_DEFAULT=5201 # Default iperf3 server port for single UE scenarios
TOTAL_REPETITIONS=5 # <--- Set your desired total number of repetitions here (3-5 recommended)

# Independent ports for Competing scenario
IPERF_SERVER_PORT_UE1_COMP=5201
IPERF_SERVER_PORT_UE2_COMP=5202


# --- Function Definitions ---

# Function: Install iperf3 and necessary tools (e.g., psmisc for killall) in a container
install_tools_in_container() {
  local container_name=$1
  echo "==> Installing iperf3 and psmisc (if needed) in ${container_name} container..."
  # Check if iperf3 is installed
  if ! sudo docker exec -it ${container_name} command -v iperf3 > /dev/null 2>&1; then
    echo "    --> iperf3 not installed, attempting to install..."
    sudo docker exec -it ${container_name} bash -c "apt-get update && apt-get install -y iperf3" > /dev/null 2>&1
    if sudo docker exec -it ${container_name} command -v iperf3 > /dev/null 2>&1; then
      echo "    --> iperf3 installed successfully."
    else
      echo "    --> Warning: iperf3 installation failed in ${container_name}."
    fi
  else
    echo "    --> iperf3 is already installed."
  fi
  # Check if killall is installed
  if ! sudo docker exec -it ${container_name} command -v killall > /dev/null 2>&1; then
    echo "    --> killall not installed, attempting to install psmisc..."
    sudo docker exec -it ${container_name} bash -c "apt-get update && apt-get install -y psmisc" > /dev/null 2>&1
     if sudo docker exec -it ${container_name} command -v killall > /dev/null 2>&1; then
      echo "    --> psmisc (killall) installed successfully."
    else
      echo "    --> Warning: psmisc (killall) installation failed in ${container_name}."
    fi
  else
    echo "    --> killall (psmisc) is already installed."
  fi
}

# Function: Wait for UE PDU session establishment
wait_for_pdu_session() {
  local ue_container_name=$1
  echo "==> Waiting for ${ue_container_name} to register and establish PDU session..."
  echo "    Please run in a new terminal: sudo docker compose -f ../docker-compose.yaml logs -f ${ue_container_name}"
  local PDU_SESSION_TIMEOUT=120 # Timeout for PDU session establishment (seconds)
  local start_time=$(date +%s)
  local pdu_established=false

  while [ $(($(date +%s) - start_time)) -lt ${PDU_SESSION_TIMEOUT} ]; do
    if sudo docker compose -f ../docker-compose.yaml logs ${ue_container_name} | grep -q "TUN interface\[uesimtun0,.*\] is up"; then
      echo "==> ${ue_container_name} PDU session established successfully!"
      pdu_established=true
      break
    fi
    sleep 2
  done

  if [ "$pdu_established" = false ]; then
    echo "Warning: ${ue_container_name} failed to establish PDU session within ${PDU_SESSION_TIMEOUT} seconds. Please check logs."
    read -p "Press Enter to continue or Ctrl+C to abort..."
  fi
}

# Function: Start a single iperf3 server (for single UE scenarios)
start_single_iperf_server() {
  local server_port=$1
  echo "==> Stopping any existing iperf3 servers in UPF (all ports)..."
  sudo docker exec -it ${UPF_CONTAINER_NAME} killall -q iperf3 2>/dev/null || true
  echo "==> Starting iperf3 server in UPF container (port ${server_port})..."
  sudo docker exec -d ${UPF_CONTAINER_NAME} bash -c "iperf3 -s -p ${server_port} > /tmp/iperf3_server_${server_port}.log 2>&1"
  sleep 3 
  echo "==> UPF iperf3 server started in background (port ${server_port}). Check /tmp/iperf3_server_${server_port}.log inside the container to confirm."
}

# Function: Stop all iperf3 servers
stop_all_iperf_servers() {
  echo "==> Stopping all iperf3 servers on UPF..."
  sudo docker exec -it ${UPF_CONTAINER_NAME} killall -q iperf3 2>/dev/null || true
  echo "    iperf3 servers on UPF have been attempted to stop."
}

# Function: Run test for a single UE (using default or specified server port)
run_single_ue_test() {
  local ue_name_param=$1
  local scenario_tag=$2
  local repetition_num=$3
  local iperf_params_custom=$4
  local server_port_to_use=${5:-$IPERF_SERVER_PORT_DEFAULT}

  local ue_log_file="${ue_name_param}_${scenario_tag}_ping_rep${repetition_num}.log"
  local iperf_log_file_tmp="/tmp/${ue_name_param}_${scenario_tag}_iperf_rep${repetition_num}.json"
  local iperf_log_file_host="${ue_name_param}_${scenario_tag}_iperf_rep${repetition_num}.json"

  echo "==== Cleaning up old result files (if any) for ${scenario_tag} - ${ue_name_param} Rep ${repetition_num} ===="
  rm -f "${RESULTS_DIR_HOST}/${ue_log_file}"
  rm -f "${RESULTS_DIR_HOST}/${iperf_log_file_host}"
  sudo docker exec ${ue_name_param} rm -f ${iperf_log_file_tmp} 2>/dev/null || true
  echo "Old files cleanup complete."

  echo "==== Starting execution for ${ue_name_param} - ${scenario_tag} - Repetition ${repetition_num} ===="
  echo "==> Recording experiment start time: $(date +%Y%m%d_%H%M%S_%N)"

  if [[ "$scenario_tag" != "competing_high" && "$scenario_tag" != "competing_medium" ]]; then
    start_single_iperf_server "${server_port_to_use}"
  fi

  echo "==> Starting ping on ${ue_name_param} (duration ${EXPERIMENT_DURATION} seconds)..."
  sudo docker exec ${ue_name_param} ping -i 0.2 -c $((EXPERIMENT_DURATION * 5)) ${PING_TARGET} > "${RESULTS_DIR_HOST}/${ue_log_file}" &
  local ping_pid=$!

  echo "==> Starting iperf3 client on ${ue_name_param} (port ${server_port_to_use}, duration ${EXPERIMENT_DURATION} seconds)..."
  sudo docker exec ${ue_name_param} bash -c "iperf3 -u -c ${PING_TARGET} -p ${server_port_to_use} ${iperf_params_custom} -t ${EXPERIMENT_DURATION} -J --logfile ${iperf_log_file_tmp}" &
  local iperf_pid=$!

  echo "==> ${ue_name_param} iperf3 (PID: ${iperf_pid}) and ping (PID: ${ping_pid}) started in background."
  
  if [[ "$scenario_tag" != "competing_high" && "$scenario_tag" != "competing_medium" ]]; then
    echo "==> Waiting ${EXPERIMENT_DURATION} seconds for the test to complete (plus ${WAIT_BUFFER} seconds buffer)..."
    sleep $((EXPERIMENT_DURATION + WAIT_BUFFER))
    echo "==> Test duration elapsed."

    echo "==> Copying iperf3 results for ${ue_name_param}..."
    if sudo docker cp ${ue_name_param}:${iperf_log_file_tmp} "${RESULTS_DIR_HOST}/${iperf_log_file_host}"; then
        echo "iperf3 results copied to ${RESULTS_DIR_HOST}/${iperf_log_file_host}"
    else
        echo "Warning: Failed to copy ${iperf_log_file_tmp}."
    fi
    stop_all_iperf_servers
  fi
  
  echo "==> Scenario ${ue_name_param} - ${scenario_tag} - Repetition ${repetition_num} finished."
  echo "==> Recording experiment end time: $(date +%Y%m%d_%H%M%S_%N)"
  echo "========================================================"
  sleep 5
}

# --- Main Experiment Flow ---
mkdir -p "${RESULTS_DIR_HOST}"
cd "${RESULTS_DIR_HOST}" || { echo "Error: Could not change to results directory ${RESULTS_DIR_HOST}"; exit 1; }

echo "==> Ensuring all free5GC components are running (current directory: $(pwd), parent should be free5gc-compose)..."
sudo docker compose -f ../docker-compose.yaml up -d 

install_tools_in_container "${UPF_CONTAINER_NAME}"

for REP_NUM in $(seq 1 ${TOTAL_REPETITIONS})
do
  echo ""
  echo "##########################################################"
  echo "********** Starting Experiment ${REP_NUM} / ${TOTAL_REPETITIONS} **********"
  echo "##########################################################"
  echo ""

  # --- Scenario 1: Baseline (using UE1) ---
  echo "====== Scenario 1: Baseline (UE1) - Repetition ${REP_NUM} ======"
  echo "!!!!!! Please manually ensure the slice configuration in custom_configs/ueransim-ue1.yaml is for the Baseline scenario !!!!!!"
  echo "(e.g., comment out the slice section, or use an S-NSSAI that has no special GBR/MBR in SMF)"
  #read -p "After confirming UE1 YAML configuration, press Enter to continue Baseline Rep ${REP_NUM}..."
  sleep 3
  sudo docker compose -f ../docker-compose.yaml up -d "${GNB_CONTAINER_NAME}" "${UE1_CONTAINER_NAME}"
  install_tools_in_container "${UE1_CONTAINER_NAME}" 
  wait_for_pdu_session "${UE1_CONTAINER_NAME}"
  run_single_ue_test "${UE1_CONTAINER_NAME}" "baseline" "${REP_NUM}" "-b 75M -P 2" "${IPERF_SERVER_PORT_DEFAULT}"
  sudo docker compose -f ../docker-compose.yaml stop "${UE1_CONTAINER_NAME}" 
  sleep 5

  # --- Scenario 2: High-Only (UE1) ---
  echo "====== Scenario 2: High-Only (UE1) - Repetition ${REP_NUM} ======"
  echo "!!!!!! Please manually ensure the slice configuration in custom_configs/ueransim-ue1.yaml is for eMBB-High (e.g., sd: \"000101\") !!!!!!"
  #read -p "After confirming UE1 YAML configuration, press Enter to continue High-Only Rep ${REP_NUM}..."
  sleep 3
  sudo docker compose -f ../docker-compose.yaml up -d "${UE1_CONTAINER_NAME}" 
  install_tools_in_container "${UE1_CONTAINER_NAME}" 
  wait_for_pdu_session "${UE1_CONTAINER_NAME}"
  run_single_ue_test "${UE1_CONTAINER_NAME}" "high_only" "${REP_NUM}" "-b 75M -P 2" "${IPERF_SERVER_PORT_DEFAULT}"
  sudo docker compose -f ../docker-compose.yaml stop "${UE1_CONTAINER_NAME}"
  sleep 5

  # --- Scenario 3: Medium-Only (UE2) ---
  echo "====== Scenario 3: Medium-Only (UE2) - Repetition ${REP_NUM} ======"
  echo "!!!!!! Please manually ensure the slice configuration in custom_configs/ueransim-ue2.yaml is for eMBB-Medium (e.g., sd: \"000102\") !!!!!!"
  #read -p "After confirming UE2 YAML configuration, press Enter to continue Medium-Only Rep ${REP_NUM}..."
  sleep 3
  sudo docker compose -f ../docker-compose.yaml up -d "${UE2_CONTAINER_NAME}" 
  install_tools_in_container "${UE2_CONTAINER_NAME}" 
  wait_for_pdu_session "${UE2_CONTAINER_NAME}"
  run_single_ue_test "${UE2_CONTAINER_NAME}" "medium_only" "${REP_NUM}" "-b 4M -P 10" "${IPERF_SERVER_PORT_DEFAULT}"
  sudo docker compose -f ../docker-compose.yaml stop "${UE2_CONTAINER_NAME}"
  sleep 5

  # --- Scenario 4: Competing (UE1 and UE2 simultaneously) ---
  echo "====== Scenario 4: Competing (UE1 & UE2) - Repetition ${REP_NUM} ======"
  echo "!!!!!! Please manually ensure UE1 YAML (High, sd: \"000101\") and UE2 YAML (Medium, sd: \"000102\") configurations are correct !!!!!!"
  #read -p "After confirming UE1 and UE2 YAML configurations, press Enter to continue Competing Rep ${REP_NUM}..."
  sleep 3
  # Ensure gNB is running (if it was stopped after individual scenarios)
  sudo docker compose -f ../docker-compose.yaml up -d "${GNB_CONTAINER_NAME}" 
  sudo docker compose -f ../docker-compose.yaml up -d "${UE1_CONTAINER_NAME}" "${UE2_CONTAINER_NAME}"
  install_tools_in_container "${UE1_CONTAINER_NAME}"
  install_tools_in_container "${UE2_CONTAINER_NAME}"
  wait_for_pdu_session "${UE1_CONTAINER_NAME}"
  wait_for_pdu_session "${UE2_CONTAINER_NAME}"

  echo "==== Starting execution for Competing scenario - Repetition ${REP_NUM} ===="
  echo "==> Recording experiment start time: $(date +%Y%m%d_%H%M%S_%N)"
  
  echo "==> Stopping any existing iperf3 servers in UPF (all ports)..."
  sudo docker exec -it ${UPF_CONTAINER_NAME} killall -q iperf3 2>/dev/null || true
  sleep 1
  echo "==> Starting iperf3 server for UE1 in UPF container (port ${IPERF_SERVER_PORT_UE1_COMP})..."
  sudo docker exec -d ${UPF_CONTAINER_NAME} bash -c "iperf3 -s -p ${IPERF_SERVER_PORT_UE1_COMP} > /tmp/iperf3_server_ue1_rep${REP_NUM}.log 2>&1"
  sleep 2

  echo "==> Starting iperf3 server for UE2 in UPF container (port ${IPERF_SERVER_PORT_UE2_COMP})..."
  sudo docker exec -d ${UPF_CONTAINER_NAME} bash -c "iperf3 -s -p ${IPERF_SERVER_PORT_UE2_COMP} > /tmp/iperf3_server_ue2_rep${REP_NUM}.log 2>&1"
  sleep 2
  echo "==> UPF iperf3 server instances started in background."

  UE1_COMP_PING_LOG="${UE1_CONTAINER_NAME}_competing_high_ping_rep${REP_NUM}.log"
  UE1_COMP_IPERF_TMP="/tmp/${UE1_CONTAINER_NAME}_competing_high_iperf_rep${REP_NUM}.json"
  UE1_COMP_IPERF_HOST="${UE1_CONTAINER_NAME}_competing_high_iperf_rep${REP_NUM}.json"
  IPERF_PARAMS_UE1_COMP_FULL="-u -c ${PING_TARGET} -p ${IPERF_SERVER_PORT_UE1_COMP} -b 75M -P 2 -t ${EXPERIMENT_DURATION} -J --logfile ${UE1_COMP_IPERF_TMP}"

  UE2_COMP_PING_LOG="${UE2_CONTAINER_NAME}_competing_medium_ping_rep${REP_NUM}.log"
  UE2_COMP_IPERF_TMP="/tmp/${UE2_CONTAINER_NAME}_competing_medium_iperf_rep${REP_NUM}.json"
  UE2_COMP_IPERF_HOST="${UE2_CONTAINER_NAME}_competing_medium_iperf_rep${REP_NUM}.json"
  IPERF_PARAMS_UE2_COMP_FULL="-u -c ${PING_TARGET} -p ${IPERF_SERVER_PORT_UE2_COMP} -b 4M -P 10 -t ${EXPERIMENT_DURATION} -J --logfile ${UE2_COMP_IPERF_TMP}"

  echo "==> Cleaning up old result files for Competing scenario..."
  rm -f "${RESULTS_DIR_HOST}/${UE1_COMP_PING_LOG}" "${RESULTS_DIR_HOST}/${UE1_COMP_IPERF_HOST}"
  rm -f "${RESULTS_DIR_HOST}/${UE2_COMP_PING_LOG}" "${RESULTS_DIR_HOST}/${UE2_COMP_IPERF_HOST}"
  sudo docker exec ${UE1_CONTAINER_NAME} rm -f ${UE1_COMP_IPERF_TMP} 2>/dev/null || true
  sudo docker exec ${UE2_CONTAINER_NAME} rm -f ${UE2_COMP_IPERF_TMP} 2>/dev/null || true
  echo "Old files cleanup complete."

  echo "==> Starting ping and iperf3 on ${UE1_CONTAINER_NAME} (High) (port ${IPERF_SERVER_PORT_UE1_COMP})..."
  sudo docker exec ${UE1_CONTAINER_NAME} ping -i 0.2 -c $((EXPERIMENT_DURATION * 5)) ${PING_TARGET} > "${RESULTS_DIR_HOST}/${UE1_COMP_PING_LOG}" &
  PING_PID_COMP_UE1=$!
  sudo docker exec ${UE1_CONTAINER_NAME} bash -c "iperf3 ${IPERF_PARAMS_UE1_COMP_FULL}" &
  IPERF_PID_COMP_UE1=$!

  echo "==> Starting ping and iperf3 on ${UE2_CONTAINER_NAME} (Medium) (port ${IPERF_SERVER_PORT_UE2_COMP})..."
  sudo docker exec ${UE2_CONTAINER_NAME} ping -i 0.2 -c $((EXPERIMENT_DURATION * 5)) ${PING_TARGET} > "${RESULTS_DIR_HOST}/${UE2_COMP_PING_LOG}" &
  PING_PID_COMP_UE2=$!
  sudo docker exec ${UE2_CONTAINER_NAME} bash -c "iperf3 ${IPERF_PARAMS_UE2_COMP_FULL}" &
  IPERF_PID_COMP_UE2=$!

  echo "==> Competing scenario traffic started. iperf3 PIDs: UE1=${IPERF_PID_COMP_UE1}, UE2=${IPERF_PID_COMP_UE2}. Ping PIDs: UE1=${PING_PID_COMP_UE1}, UE2=${PING_PID_COMP_UE2}."
  echo "==> Waiting ${EXPERIMENT_DURATION} seconds for the test to complete (plus ${WAIT_BUFFER} seconds buffer)..."
  
  # More reliably wait for all background processes
  # Wait for iperf first (usually the longest running)
  wait $IPERF_PID_COMP_UE1 2>/dev/null
  wait $IPERF_PID_COMP_UE2 2>/dev/null
  # Then wait for ping (they might have already finished due to the -c parameter)
  wait $PING_PID_COMP_UE1 2>/dev/null
  wait $PING_PID_COMP_UE2 2>/dev/null
  
  sleep ${WAIT_BUFFER} 
  echo "==> Competing scenario test duration elapsed."

  echo "==> Copying iperf3 results for Competing scenario..."
  if sudo docker cp ${UE1_CONTAINER_NAME}:${UE1_COMP_IPERF_TMP} "${RESULTS_DIR_HOST}/${UE1_COMP_IPERF_HOST}"; then
      echo "UE1 Competing iperf results copied."
  else
      echo "Warning: Failed to copy UE1 Competing iperf results."
  fi
  if sudo docker cp ${UE2_CONTAINER_NAME}:${UE2_COMP_IPERF_TMP} "${RESULTS_DIR_HOST}/${UE2_COMP_IPERF_HOST}"; then
      echo "UE2 Competing iperf results copied."
  else
      echo "Warning: Failed to copy UE2 Competing iperf results."
  fi

  stop_all_iperf_servers
  echo "==> Competing scenario - Repetition ${REP_NUM} finished."
  echo "==> Recording experiment end time: $(date +%Y%m%d_%H%M%S_%N)"
  echo "========================================================"
  sudo docker compose -f ../docker-compose.yaml stop "${UE1_CONTAINER_NAME}" "${UE2_CONTAINER_NAME}"
  sleep 5

done # End of experiment repetition loop

echo "All ${TOTAL_REPETITIONS} repetitions for all scenarios have been completed!"
echo "Stopping gNB..."
sudo docker compose -f ../docker-compose.yaml stop "${GNB_CONTAINER_NAME}"
echo "Script execution finished."