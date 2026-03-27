/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * ARSTA Project - Adaptive RRC State Transition Algorithm Simulation
 *
 * This simulation implements the ARSTA adaptive 5G NR RRC state management
 * algorithm with four modules:
 * 1. Traffic Prediction (EWMA inter-arrival time)
 * 2. Mobility-Aware DRX
 * 3. Handover-Aware State Locking
 * 4. Paging Optimization (RNA sizing)
 *
 * Author: ARSTA Project Team
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/internet-module.h"
#include "ns3/applications-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/config-store-module.h"

// NR module includes
#include "ns3/nr-module.h"
#include "ns3/nr-helper.h"
#include "ns3/nr-point-to-point-epc-helper.h"
#include "ns3/ideal-beamforming-helper.h"

#include <fstream>
#include <iomanip>
#include <map>
#include <sys/stat.h>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("5gRrcArsta");

// ============================================================================
// Power consumption constants (3GPP TR 38.840)
// ============================================================================
const double POWER_IDLE_MW = 5.0;        // RRC_IDLE: 5 mW
const double POWER_INACTIVE_MW = 15.0;   // RRC_INACTIVE: 15 mW
const double POWER_CONNECTED_MW = 900.0; // RRC_CONNECTED: 900 mW
const double POWER_TRANSITION_MW = 250.0; // State transition: 250 mW

// Global variables for statistics
static uint64_t g_totalTxBytes = 0;
static uint64_t g_totalRxBytes = 0;
static std::ofstream g_rrcStateFile;

// Forward declarations
class UeRrcMonitor;
static std::map<uint64_t, Ptr<Node>> g_imsiToNode;
static UeRrcMonitor* g_rrcMonitor = nullptr;

/**
 * \brief Convert RRC state enum to string
 * \param state The LteRrcSap::State value
 * \return String representation of the state
 */
std::string
RrcStateToString(uint16_t state)
{
    switch (state)
    {
    case 0:
        return "IDLE_START";
    case 1:
        return "IDLE_CELL_SEARCH";
    case 2:
        return "IDLE_WAIT_MIB_SIB1";
    case 3:
        return "IDLE_WAIT_MIB";
    case 4:
        return "IDLE_WAIT_SIB1";
    case 5:
        return "IDLE_CAMPED_NORMALLY";
    case 6:
        return "IDLE_WAIT_SIB2";
    case 7:
        return "IDLE_RANDOM_ACCESS";
    case 8:
        return "IDLE_CONNECTING";
    case 9:
        return "CONNECTED_NORMALLY";
    case 10:
        return "CONNECTED_HANDOVER";
    case 11:
        return "CONNECTED_PHY_PROBLEM";
    case 12:
        return "CONNECTED_REESTABLISHING";
    default:
        return "UNKNOWN_" + std::to_string(state);
    }
}

/**
 * \brief Convert custom ARSTA state to string
 * \param customState 0=IDLE, 1=INACTIVE, 2=CONNECTED
 * \return String representation
 */
std::string
CustomStateToString(int customState)
{
    switch (customState)
    {
    case 0:
        return "IDLE";
    case 1:
        return "INACTIVE";
    case 2:
        return "CONNECTED";
    default:
        return "UNKNOWN";
    }
}

// ============================================================================
// ARSTA UeRrcMonitor Class
// Implements all four ARSTA modules for adaptive RRC state management
// ============================================================================
class UeRrcMonitor
{
  public:
    /**
     * \brief Per-UE state tracking structure
     */
    struct UeState
    {
        uint64_t imsi;
        uint16_t rrcState;    // actual ns-3 RRC state (LteUeRrc::State)
        int customState;      // 0=IDLE, 1=INACTIVE, 2=CONNECTED
        double ewmaIat;       // EWMA inter-arrival time estimate (seconds)
        Time lastPktTime;     // Time of last packet arrival
        Time lastStateChange; // Time of last state change
        double velocity;      // m/s, updated from mobility model
        double rsrp;          // dBm, updated from PHY trace
        double rsrpPrev;      // Previous RSRP for gradient calculation
        Time rsrpLastUpdate;  // Time of last RSRP update
        double rsrpGradient;  // dRSRP/dt in dB/s
        bool hoLocked;        // true = state locked during HO window
        Time hoLockExpiry;    // When HO lock expires
        uint32_t drxCycleMs;  // Current DRX cycle in milliseconds
        uint16_t cellId;      // Current serving cell
    };

    /**
     * \brief Constructor
     * \param outputDir Output directory for log files
     * \param rngRun RNG run number
     * \param ewmaAlpha EWMA smoothing factor (default 0.3)
     * \param hoLockThreshold RSRP gradient threshold for HO lock (default -2.0 dB/s)
     * \param inactivityThreshold Inactivity timer threshold in seconds
     */
    UeRrcMonitor(const std::string& outputDir, uint32_t rngRun, double ewmaAlpha = 0.3,
                 double hoLockThreshold = -2.0, double inactivityThreshold = 10.0)
        : m_ewmaAlpha(ewmaAlpha),
          m_hoLockThreshold(hoLockThreshold),
          m_inactivityThreshold(inactivityThreshold)
    {
        std::string filename =
            outputDir + "arsta_state_log_run" + std::to_string(rngRun) + ".csv";
        m_logFile.open(filename);
        if (m_logFile.is_open())
        {
            // Extended CSV header with ARSTA-specific columns
            m_logFile << "time_s,imsi,cell_id,old_state,new_state,custom_state,ewma_iat,"
                      << "velocity,drx_cycle_ms,ho_locked,rna_size" << std::endl;
        }
        else
        {
            NS_LOG_ERROR("Could not open ARSTA log file: " << filename);
        }
    }

    /**
     * \brief Destructor - close log file
     */
    ~UeRrcMonitor()
    {
        if (m_logFile.is_open())
        {
            m_logFile.close();
        }
    }

    /**
     * \brief Initialize UE state tracking
     * \param imsi UE IMSI
     */
    void InitUeState(uint64_t imsi)
    {
        if (m_ueStates.find(imsi) == m_ueStates.end())
        {
            UeState state;
            state.imsi = imsi;
            state.rrcState = 0;       // IDLE_START
            state.customState = 0;    // IDLE
            state.ewmaIat = 0.0;
            state.lastPktTime = Seconds(0);
            state.lastStateChange = Simulator::Now();
            state.velocity = 0.0;
            state.rsrp = -100.0;      // Initial RSRP (dBm)
            state.rsrpPrev = -100.0;
            state.rsrpLastUpdate = Seconds(0);
            state.rsrpGradient = 0.0;
            state.hoLocked = false;
            state.hoLockExpiry = Seconds(0);
            state.drxCycleMs = 160;   // Default DRX cycle
            state.cellId = 0;
            m_ueStates[imsi] = state;
        }
    }

    /**
     * \brief Module 1: EWMA Traffic Predictor
     * Updates EWMA of inter-arrival time on each packet arrival.
     * If ewmaIat > inactivityThreshold * 0.6, triggers early INACTIVE.
     * \param imsi UE IMSI
     * \param arrivalTime Packet arrival time
     */
    void OnPacketArrival(uint64_t imsi, Time arrivalTime)
    {
        InitUeState(imsi);
        UeState& state = m_ueStates[imsi];

        if (state.lastPktTime > Seconds(0))
        {
            double iat = (arrivalTime - state.lastPktTime).GetSeconds();
            if (state.ewmaIat == 0.0)
            {
                state.ewmaIat = iat;
            }
            else
            {
                // EWMA: new = alpha * current + (1-alpha) * old
                state.ewmaIat = m_ewmaAlpha * iat + (1.0 - m_ewmaAlpha) * state.ewmaIat;
            }

            // Check for early INACTIVE transition
            // Trigger if EWMA IAT exceeds 60% of inactivity threshold
            double earlyThreshold = m_inactivityThreshold * 0.6;
            if (state.ewmaIat > earlyThreshold && state.customState == 2 && !state.hoLocked)
            {
                int oldState = state.customState;
                state.customState = 1; // INACTIVE
                state.lastStateChange = arrivalTime;
                LogStateChange(imsi, oldState, state.customState, "EWMA_EARLY_INACTIVE");
                NS_LOG_INFO("ARSTA: IMSI " << imsi << " early INACTIVE (EWMA IAT="
                                            << state.ewmaIat << "s > " << earlyThreshold << "s)");
            }
        }
        state.lastPktTime = arrivalTime;

        // Packet arrival in IDLE/INACTIVE -> transition to CONNECTED
        if (state.customState != 2)
        {
            int oldState = state.customState;
            state.customState = 2; // CONNECTED
            state.lastStateChange = arrivalTime;
            LogStateChange(imsi, oldState, state.customState, "PACKET_ARRIVAL");
        }
    }

    /**
     * \brief Module 2: Velocity-Aware DRX Tuning
     * Adjusts DRX cycle based on UE velocity:
     * - v < 5 m/s: drxCycle = 160ms (pedestrian/stationary)
     * - 5 <= v < 15: drxCycle = 80ms (urban mobility)
     * - v >= 15: drxCycle = 20ms (vehicular)
     * \param imsi UE IMSI
     */
    void UpdateDrxCycle(uint64_t imsi)
    {
        if (m_ueStates.find(imsi) == m_ueStates.end())
        {
            return;
        }

        UeState& state = m_ueStates[imsi];
        uint32_t newDrxCycle;

        if (state.velocity < 5.0)
        {
            newDrxCycle = 160; // Pedestrian/stationary: long DRX
        }
        else if (state.velocity < 15.0)
        {
            newDrxCycle = 80; // Urban mobility: medium DRX
        }
        else
        {
            newDrxCycle = 20; // Vehicular: short DRX
        }

        if (newDrxCycle != state.drxCycleMs)
        {
            NS_LOG_INFO("ARSTA: IMSI " << imsi << " DRX cycle changed from "
                                        << state.drxCycleMs << "ms to " << newDrxCycle
                                        << "ms (velocity=" << state.velocity << " m/s)");
            state.drxCycleMs = newDrxCycle;
        }
    }

    /**
     * \brief Module 3: Handover-Aware State Locking
     * If RSRP gradient < -2.0 dB/s, locks state in CONNECTED
     * Lock expiry = Now + velocity * 10ms
     * \param imsi UE IMSI
     */
    void CheckHandoverLock(uint64_t imsi)
    {
        if (m_ueStates.find(imsi) == m_ueStates.end())
        {
            return;
        }

        UeState& state = m_ueStates[imsi];
        Time now = Simulator::Now();

        // Check if current lock has expired
        if (state.hoLocked && now >= state.hoLockExpiry)
        {
            state.hoLocked = false;
            NS_LOG_INFO("ARSTA: IMSI " << imsi << " HO lock expired");
        }

        // Check for new HO lock condition
        if (!state.hoLocked && state.rsrpGradient < m_hoLockThreshold)
        {
            state.hoLocked = true;
            // Lock duration proportional to velocity: velocity * 10ms
            double lockDurationMs = std::max(50.0, state.velocity * 10.0);
            state.hoLockExpiry = now + MilliSeconds(static_cast<uint64_t>(lockDurationMs));

            // Force CONNECTED state during lock
            if (state.customState != 2)
            {
                int oldState = state.customState;
                state.customState = 2;
                state.lastStateChange = now;
                LogStateChange(imsi, oldState, state.customState, "HO_LOCK_CONNECTED");
            }

            NS_LOG_INFO("ARSTA: IMSI " << imsi << " HO lock activated (RSRP gradient="
                                        << state.rsrpGradient << " dB/s, lock duration="
                                        << lockDurationMs << " ms)");
        }
    }

    /**
     * \brief Module 4: RNA (Registration Notification Area) Sizing
     * Returns RNA size based on velocity for paging optimization:
     * - v < 3 m/s: "small" (fewer cells, less paging overhead)
     * - 3 <= v < 15: "medium"
     * - v >= 15: "large" (more cells for fast-moving UEs)
     * Note: Logged to CSV, not enforced in simulation
     * \param velocity UE velocity in m/s
     * \return RNA size string
     */
    std::string GetRnaSize(double velocity) const
    {
        if (velocity < 3.0)
        {
            return "small";
        }
        else if (velocity < 15.0)
        {
            return "medium";
        }
        else
        {
            return "large";
        }
    }

    /**
     * \brief Update UE velocity from mobility model
     * \param imsi UE IMSI
     * \param velocity New velocity in m/s
     */
    void UpdateVelocity(uint64_t imsi, double velocity)
    {
        InitUeState(imsi);
        m_ueStates[imsi].velocity = velocity;
        UpdateDrxCycle(imsi);
    }

    /**
     * \brief Update RSRP measurement and calculate gradient
     * \param imsi UE IMSI
     * \param rsrp New RSRP value in dBm
     */
    void UpdateRsrp(uint64_t imsi, double rsrp)
    {
        InitUeState(imsi);
        UeState& state = m_ueStates[imsi];
        Time now = Simulator::Now();

        if (state.rsrpLastUpdate > Seconds(0))
        {
            double timeDelta = (now - state.rsrpLastUpdate).GetSeconds();
            if (timeDelta > 0)
            {
                // Calculate RSRP gradient: dB/s
                state.rsrpGradient = (rsrp - state.rsrpPrev) / timeDelta;
            }
        }

        state.rsrpPrev = state.rsrp;
        state.rsrp = rsrp;
        state.rsrpLastUpdate = now;

        // Check for HO lock after RSRP update
        CheckHandoverLock(imsi);
    }

    /**
     * \brief Handle RRC state transition from ns-3
     * \param imsi UE IMSI
     * \param cellId Cell ID
     * \param oldState Previous ns-3 RRC state
     * \param newState New ns-3 RRC state
     */
    void OnRrcStateChange(uint64_t imsi, uint16_t cellId, uint16_t oldState, uint16_t newState)
    {
        InitUeState(imsi);
        UeState& state = m_ueStates[imsi];

        state.rrcState = newState;
        state.cellId = cellId;

        // Map ns-3 RRC state to custom state
        int newCustomState = state.customState;
        if (newState == 9 || newState == 10) // CONNECTED_NORMALLY or CONNECTED_HANDOVER
        {
            newCustomState = 2; // CONNECTED
        }
        else if (newState == 5) // IDLE_CAMPED_NORMALLY
        {
            // Only go to IDLE if not HO locked
            if (!state.hoLocked)
            {
                newCustomState = 0; // IDLE
            }
        }

        // Update custom state if changed and not HO locked
        if (newCustomState != state.customState)
        {
            if (state.hoLocked && newCustomState < 2)
            {
                NS_LOG_INFO("ARSTA: IMSI " << imsi << " state change blocked by HO lock");
            }
            else
            {
                int oldCustomState = state.customState;
                state.customState = newCustomState;
                state.lastStateChange = Simulator::Now();
                LogStateChange(imsi, oldCustomState, newCustomState, "RRC_TRANSITION");
            }
        }

        // Log the ns-3 RRC transition
        LogRrcTransition(imsi, cellId, oldState, newState);
    }

    /**
     * \brief Log state change to CSV file
     * \param imsi UE IMSI
     * \param oldState Previous custom state
     * \param newState New custom state
     * \param reason Reason for state change
     */
    void LogStateChange(uint64_t imsi, int oldState, int newState, const std::string& reason)
    {
        if (!m_logFile.is_open())
        {
            return;
        }

        UeState& state = m_ueStates[imsi];
        double timeS = Simulator::Now().GetSeconds();

        m_logFile << std::fixed << std::setprecision(6) << timeS << ","
                  << imsi << "," << state.cellId << ","
                  << CustomStateToString(oldState) << ","
                  << CustomStateToString(newState) << ","
                  << newState << ","
                  << std::setprecision(4) << state.ewmaIat << ","
                  << std::setprecision(2) << state.velocity << ","
                  << state.drxCycleMs << ","
                  << (state.hoLocked ? "true" : "false") << ","
                  << GetRnaSize(state.velocity) << std::endl;

        NS_LOG_INFO("ARSTA StateChange: t=" << timeS << "s IMSI=" << imsi
                                             << " " << CustomStateToString(oldState) << " -> "
                                             << CustomStateToString(newState)
                                             << " reason=" << reason);
    }

    /**
     * \brief Log ns-3 RRC transition to global CSV
     */
    void LogRrcTransition(uint64_t imsi, uint16_t cellId, uint16_t oldState, uint16_t newState)
    {
        if (!g_rrcStateFile.is_open())
        {
            return;
        }

        UeState& state = m_ueStates[imsi];
        double timeS = Simulator::Now().GetSeconds();

        // Extended CSV with ARSTA columns
        g_rrcStateFile << std::fixed << std::setprecision(6) << timeS << ","
                       << imsi << "," << cellId << ","
                       << RrcStateToString(oldState) << ","
                       << RrcStateToString(newState) << ","
                       << state.customState << ","
                       << std::setprecision(4) << state.ewmaIat << ","
                       << std::setprecision(2) << state.velocity << ","
                       << state.drxCycleMs << ","
                       << (state.hoLocked ? "true" : "false") << ","
                       << GetRnaSize(state.velocity) << std::endl;
    }

    /**
     * \brief Get UE state for external access
     * \param imsi UE IMSI
     * \return Pointer to UE state or nullptr
     */
    UeState* GetUeState(uint64_t imsi)
    {
        auto it = m_ueStates.find(imsi);
        if (it != m_ueStates.end())
        {
            return &(it->second);
        }
        return nullptr;
    }

    /**
     * \brief Calculate total energy consumption across all UEs
     * \return Total energy in mJ
     */
    double CalculateTotalEnergy() const
    {
        double totalEnergy = 0.0;
        // Note: This is a simplified calculation
        // Real implementation would integrate power over time per state
        for (const auto& pair : m_ueStates)
        {
            const UeState& state = pair.second;
            double stateDuration = (Simulator::Now() - state.lastStateChange).GetSeconds();
            double power = 0.0;
            switch (state.customState)
            {
            case 0:
                power = POWER_IDLE_MW;
                break;
            case 1:
                power = POWER_INACTIVE_MW;
                break;
            case 2:
                power = POWER_CONNECTED_MW;
                break;
            }
            totalEnergy += power * stateDuration;
        }
        return totalEnergy;
    }

  private:
    std::map<uint64_t, UeState> m_ueStates;
    std::ofstream m_logFile;
    double m_ewmaAlpha;
    double m_hoLockThreshold;
    double m_inactivityThreshold;
};

// ============================================================================
// Trace Callbacks
// ============================================================================

/**
 * \brief Callback for RRC state transition tracing
 */
void
RrcStateTransitionCallback(std::string context,
                           uint64_t imsi,
                           uint16_t cellId,
                           uint16_t oldState,
                           uint16_t newState)
{
    if (g_rrcMonitor != nullptr)
    {
        g_rrcMonitor->OnRrcStateChange(imsi, cellId, oldState, newState);
    }

    NS_LOG_INFO("Time=" << Simulator::Now().GetSeconds() << "s IMSI=" << imsi
                        << " CellId=" << cellId << " " << RrcStateToString(oldState)
                        << " -> " << RrcStateToString(newState));
}

/**
 * \brief Callback to track transmitted bytes
 */
void
TxCallback(uint64_t oldValue, uint64_t newValue)
{
    g_totalTxBytes += (newValue - oldValue);
}

/**
 * \brief Callback to track received bytes
 */
void
RxCallback(uint64_t oldValue, uint64_t newValue)
{
    g_totalRxBytes += (newValue - oldValue);
}

/**
 * \brief Callback for packet reception (for traffic prediction)
 */
void
PacketRxCallback(std::string context, Ptr<const Packet> packet)
{
    // Extract IMSI from context path
    // Context format: /NodeList/X/...
    std::size_t start = context.find("/NodeList/") + 10;
    std::size_t end = context.find("/", start);
    uint32_t nodeId = std::stoi(context.substr(start, end - start));

    // Find IMSI for this node
    for (const auto& pair : g_imsiToNode)
    {
        if (pair.second->GetId() == nodeId)
        {
            if (g_rrcMonitor != nullptr)
            {
                g_rrcMonitor->OnPacketArrival(pair.first, Simulator::Now());
            }
            break;
        }
    }
}

/**
 * \brief Periodic velocity update from mobility model
 */
void
UpdateUeVelocities(NodeContainer& ueNodes, const std::map<uint32_t, uint64_t>& nodeToImsi)
{
    for (uint32_t i = 0; i < ueNodes.GetN(); ++i)
    {
        Ptr<Node> node = ueNodes.Get(i);
        Ptr<MobilityModel> mobility = node->GetObject<MobilityModel>();
        if (mobility != nullptr)
        {
            Vector vel = mobility->GetVelocity();
            double speed = std::sqrt(vel.x * vel.x + vel.y * vel.y + vel.z * vel.z);

            auto it = nodeToImsi.find(node->GetId());
            if (it != nodeToImsi.end() && g_rrcMonitor != nullptr)
            {
                g_rrcMonitor->UpdateVelocity(it->second, speed);
            }
        }
    }

    // Schedule next velocity update (every 100ms)
    Simulator::Schedule(MilliSeconds(100), &UpdateUeVelocities, std::ref(ueNodes),
                        std::ref(nodeToImsi));
}

/**
 * \brief Create output directory if it doesn't exist
 */
bool
CreateDirectory(const std::string& path)
{
    struct stat info;
    if (stat(path.c_str(), &info) != 0)
    {
        std::string cmd = "mkdir -p " + path;
        int result = system(cmd.c_str());
        return (result == 0);
    }
    return true;
}

// ============================================================================
// Main Function
// ============================================================================
int
main(int argc, char* argv[])
{
    // ============================
    // Command line parameters (baseline + ARSTA-specific)
    // ============================
    uint32_t numUes = 20;
    double simTime = 300.0;
    uint32_t rngRun = 1;
    double inactivityTimer = 10.0;
    std::string outputDir = "results/raw/";

    // ARSTA-specific parameters
    double ewmaAlpha = 0.3;
    double hoLockThreshold = -2.0; // dB/s

    CommandLine cmd(__FILE__);
    cmd.AddValue("numUes", "Number of UEs in simulation", numUes);
    cmd.AddValue("simTime", "Total simulation time in seconds", simTime);
    cmd.AddValue("rngRun", "RNG run number for reproducibility", rngRun);
    cmd.AddValue("inactivityTimer", "RRC inactivity timer in seconds", inactivityTimer);
    cmd.AddValue("outputDir", "Output directory for results", outputDir);
    cmd.AddValue("ewmaAlpha", "EWMA smoothing factor for traffic prediction", ewmaAlpha);
    cmd.AddValue("hoLockThreshold", "RSRP gradient threshold for HO lock (dB/s)", hoLockThreshold);
    cmd.Parse(argc, argv);

    // Set RNG seed for reproducibility
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(rngRun);

    // Create output directory
    CreateDirectory(outputDir);

    // Open RRC state transition CSV file with ARSTA extended header
    std::string rrcFilename = outputDir + "rrc_transitions_arsta_run" + std::to_string(rngRun) + ".csv";
    g_rrcStateFile.open(rrcFilename);
    if (!g_rrcStateFile.is_open())
    {
        NS_FATAL_ERROR("Could not open RRC state file: " << rrcFilename);
    }
    // Extended CSV header with ARSTA columns
    g_rrcStateFile << "time_s,imsi,cell_id,old_state,new_state,custom_state,ewma_iat,"
                   << "velocity,drx_cycle_ms,ho_locked,rna_size" << std::endl;

    // Create ARSTA monitor
    g_rrcMonitor = new UeRrcMonitor(outputDir, rngRun, ewmaAlpha, hoLockThreshold, inactivityTimer);

    NS_LOG_UNCOND("=== ARSTA 5G-NR Adaptive RRC Simulation ===");
    NS_LOG_UNCOND("Parameters:");
    NS_LOG_UNCOND("  Number of UEs: " << numUes);
    NS_LOG_UNCOND("  Simulation time: " << simTime << " s");
    NS_LOG_UNCOND("  RNG run: " << rngRun);
    NS_LOG_UNCOND("  Inactivity timer: " << inactivityTimer << " s");
    NS_LOG_UNCOND("  EWMA alpha: " << ewmaAlpha);
    NS_LOG_UNCOND("  HO lock threshold: " << hoLockThreshold << " dB/s");
    NS_LOG_UNCOND("  Output directory: " << outputDir);

    // ============================
    // Network topology setup
    // ============================
    Ptr<NrPointToPointEpcHelper> epcHelper = CreateObject<NrPointToPointEpcHelper>();
    Ptr<IdealBeamformingHelper> idealBeamformingHelper = CreateObject<IdealBeamformingHelper>();
    Ptr<NrHelper> nrHelper = CreateObject<NrHelper>();

    nrHelper->SetBeamformingHelper(idealBeamformingHelper);
    nrHelper->SetEpcHelper(epcHelper);

    // ============================
    // Spectrum configuration: 3.5 GHz FR1, 40 MHz BW, numerology mu=1
    // ============================
    double centralFrequencyBand = 3.5e9;
    double bandwidthBand = 40e6;
    uint16_t numerology = 1;

    BandwidthPartInfoPtrVector allBwps;
    CcBwpCreator ccBwpCreator;

    CcBwpCreator::SimpleOperationBandConf bandConf(centralFrequencyBand,
                                                    bandwidthBand,
                                                    1,
                                                    BandwidthPartInfo::UMa);

    OperationBandInfo band = ccBwpCreator.CreateOperationBandContiguousCc(bandConf);

    idealBeamformingHelper->SetAttribute("BeamformingMethod",
                                          TypeIdValue(DirectPathBeamforming::GetTypeId()));

    nrHelper->InitializeOperationBand(&band);
    allBwps = CcBwpCreator::GetAllBwps({band});

    // ============================
    // Create gNB nodes: equilateral triangle (500m sides)
    // ============================
    NodeContainer gnbNodes;
    gnbNodes.Create(3);

    Ptr<ListPositionAllocator> gnbPositionAlloc = CreateObject<ListPositionAllocator>();
    gnbPositionAlloc->Add(Vector(0.0, 0.0, 25.0));
    gnbPositionAlloc->Add(Vector(500.0, 0.0, 25.0));
    gnbPositionAlloc->Add(Vector(250.0, 433.0, 25.0));

    MobilityHelper gnbMobility;
    gnbMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    gnbMobility.SetPositionAllocator(gnbPositionAlloc);
    gnbMobility.Install(gnbNodes);

    // ============================
    // Create UE nodes with RandomWaypointMobility
    // ============================
    NodeContainer ueNodes;
    ueNodes.Create(numUes);

    double minX = -50.0;
    double maxX = 550.0;
    double minY = -50.0;
    double maxY = 500.0;

    Ptr<RandomRectanglePositionAllocator> uePositionAlloc =
        CreateObject<RandomRectanglePositionAllocator>();
    uePositionAlloc->SetAttribute("X", StringValue("ns3::UniformRandomVariable[Min=" +
                                                    std::to_string(minX) + "|Max=" +
                                                    std::to_string(maxX) + "]"));
    uePositionAlloc->SetAttribute("Y", StringValue("ns3::UniformRandomVariable[Min=" +
                                                    std::to_string(minY) + "|Max=" +
                                                    std::to_string(maxY) + "]"));

    MobilityHelper ueMobility;
    ueMobility.SetMobilityModel(
        "ns3::RandomWaypointMobilityModel",
        "Speed", StringValue("ns3::UniformRandomVariable[Min=1.0|Max=10.0]"),
        "Pause", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"),
        "PositionAllocator", PointerValue(uePositionAlloc));

    ueMobility.SetPositionAllocator(uePositionAlloc);
    ueMobility.Install(ueNodes);

    // Set UE heights to 1.5m
    for (uint32_t i = 0; i < ueNodes.GetN(); ++i)
    {
        Ptr<MobilityModel> mm = ueNodes.Get(i)->GetObject<MobilityModel>();
        Vector pos = mm->GetPosition();
        pos.z = 1.5;
        mm->SetPosition(pos);
    }

    // ============================
    // Configure gNB/UE transmission parameters
    // ============================
    nrHelper->SetGnbPhyAttribute("TxPower", DoubleValue(43.0));
    nrHelper->SetGnbPhyAttribute("Numerology", UintegerValue(numerology));
    nrHelper->SetUePhyAttribute("TxPower", DoubleValue(23.0));

    // ============================
    // Install NR devices
    // ============================
    NetDeviceContainer gnbDevices = nrHelper->InstallGnbDevice(gnbNodes, allBwps);
    NetDeviceContainer ueDevices = nrHelper->InstallUeDevice(ueNodes, allBwps);

    for (auto it = gnbDevices.Begin(); it != gnbDevices.End(); ++it)
    {
        DynamicCast<NrGnbNetDevice>(*it)->UpdateConfig();
    }
    for (auto it = ueDevices.Begin(); it != ueDevices.End(); ++it)
    {
        DynamicCast<NrUeNetDevice>(*it)->UpdateConfig();
    }

    // ============================
    // Install internet stack
    // ============================
    InternetStackHelper internet;
    internet.Install(ueNodes);

    Ipv4InterfaceContainer ueIpIface = epcHelper->AssignUeIpv4Address(ueDevices);

    Ipv4StaticRoutingHelper ipv4RoutingHelper;
    for (uint32_t u = 0; u < ueNodes.GetN(); ++u)
    {
        Ptr<Node> ueNode = ueNodes.Get(u);
        Ptr<Ipv4StaticRouting> ueStaticRouting =
            ipv4RoutingHelper.GetStaticRouting(ueNode->GetObject<Ipv4>());
        ueStaticRouting->SetDefaultRoute(epcHelper->GetUeDefaultGatewayAddress(), 1);
    }

    nrHelper->AttachToClosestEnb(ueDevices, gnbDevices);

    // ============================
    // Build IMSI to Node mapping for velocity updates
    // ============================
    std::map<uint32_t, uint64_t> nodeToImsi;
    for (uint32_t i = 0; i < ueDevices.GetN(); ++i)
    {
        Ptr<NrUeNetDevice> ueDevice = DynamicCast<NrUeNetDevice>(ueDevices.Get(i));
        if (ueDevice != nullptr)
        {
            uint64_t imsi = ueDevice->GetImsi();
            Ptr<Node> node = ueDevice->GetNode();
            nodeToImsi[node->GetId()] = imsi;
            g_imsiToNode[imsi] = node;
            g_rrcMonitor->InitUeState(imsi);
        }
    }

    // ============================
    // Install applications
    // ============================
    NodeContainer remoteHostContainer;
    remoteHostContainer.Create(1);
    Ptr<Node> serverNode = remoteHostContainer.Get(0);
    internet.Install(remoteHostContainer);

    PointToPointHelper p2ph;
    p2ph.SetDeviceAttribute("DataRate", DataRateValue(DataRate("100Gb/s")));
    p2ph.SetDeviceAttribute("Mtu", UintegerValue(1500));
    p2ph.SetChannelAttribute("Delay", TimeValue(MilliSeconds(10)));

    NetDeviceContainer internetDevices = p2ph.Install(epcHelper->GetPgwNode(), serverNode);

    Ipv4AddressHelper ipv4h;
    ipv4h.SetBase("1.0.0.0", "255.0.0.0");
    Ipv4InterfaceContainer internetIpIfaces = ipv4h.Assign(internetDevices);

    Ptr<Ipv4StaticRouting> remoteHostStaticRouting =
        ipv4RoutingHelper.GetStaticRouting(serverNode->GetObject<Ipv4>());
    remoteHostStaticRouting->AddNetworkRouteTo(Ipv4Address("7.0.0.0"),
                                                Ipv4Mask("255.0.0.0"),
                                                1);

    uint16_t dlPort = 1234;
    ApplicationContainer serverApps;
    ApplicationContainer clientApps;

    for (uint32_t u = 0; u < ueNodes.GetN(); ++u)
    {
        PacketSinkHelper packetSinkHelper("ns3::UdpSocketFactory",
                                           InetSocketAddress(Ipv4Address::GetAny(), dlPort + u));
        serverApps.Add(packetSinkHelper.Install(ueNodes.Get(u)));

        OnOffHelper onOffHelper("ns3::UdpSocketFactory",
                                 InetSocketAddress(ueIpIface.GetAddress(u), dlPort + u));
        onOffHelper.SetAttribute("DataRate", DataRateValue(DataRate("1Mbps")));
        onOffHelper.SetAttribute("PacketSize", UintegerValue(1024));
        onOffHelper.SetAttribute("OnTime",
                                  StringValue("ns3::ExponentialRandomVariable[Mean=2.0]"));
        onOffHelper.SetAttribute("OffTime",
                                  StringValue("ns3::ExponentialRandomVariable[Mean=8.0]"));
        clientApps.Add(onOffHelper.Install(serverNode));
    }

    serverApps.Start(Seconds(0.1));
    clientApps.Start(Seconds(0.5));
    serverApps.Stop(Seconds(simTime - 0.1));
    clientApps.Stop(Seconds(simTime - 0.5));

    // ============================
    // Connect trace callbacks
    // ============================
    Config::Connect("/NodeList/*/DeviceList/*/LteUeRrc/StateTransition",
                    MakeCallback(&RrcStateTransitionCallback));

    Config::ConnectWithoutContext("/NodeList/*/ApplicationList/*/$ns3::PacketSink/Rx",
                                   MakeCallback(&RxCallback));
    Config::ConnectWithoutContext("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/Tx",
                                   MakeCallback(&TxCallback));

    // Connect packet sink for traffic prediction
    Config::Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/Rx",
                    MakeCallback(&PacketRxCallback));

    // ============================
    // Schedule periodic velocity updates
    // ============================
    Simulator::Schedule(Seconds(1.0), &UpdateUeVelocities, std::ref(ueNodes),
                        std::ref(nodeToImsi));

    // ============================
    // Install FlowMonitor
    // ============================
    FlowMonitorHelper flowMonHelper;
    Ptr<FlowMonitor> flowMonitor = flowMonHelper.InstallAll();

    // ============================
    // Run simulation
    // ============================
    NS_LOG_UNCOND("\nStarting ARSTA simulation...");

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();

    // ============================
    // Collect and save results
    // ============================
    std::string flowMonFilename = outputDir + "flowmon_arsta_run" + std::to_string(rngRun) + ".xml";
    flowMonitor->SerializeToXmlFile(flowMonFilename, true, true);

    flowMonitor->CheckForLostPackets();
    Ptr<Ipv4FlowClassifier> classifier =
        DynamicCast<Ipv4FlowClassifier>(flowMonHelper.GetClassifier());
    FlowMonitor::FlowStatsContainer stats = flowMonitor->GetFlowStats();

    uint64_t totalTxPackets = 0;
    uint64_t totalRxPackets = 0;
    uint64_t totalTxBytesFlow = 0;
    uint64_t totalRxBytesFlow = 0;
    double totalDelay = 0.0;
    uint32_t flowCount = 0;

    for (auto& flow : stats)
    {
        totalTxPackets += flow.second.txPackets;
        totalRxPackets += flow.second.rxPackets;
        totalTxBytesFlow += flow.second.txBytes;
        totalRxBytesFlow += flow.second.rxBytes;
        if (flow.second.rxPackets > 0)
        {
            totalDelay += flow.second.delaySum.GetSeconds();
        }
        flowCount++;
    }

    // Calculate energy (simplified)
    double totalEnergy = g_rrcMonitor->CalculateTotalEnergy();

    g_rrcStateFile.close();

    // ============================
    // Print summary
    // ============================
    NS_LOG_UNCOND("\n=== ARSTA Simulation Complete ===");
    NS_LOG_UNCOND("Summary:");
    NS_LOG_UNCOND("  Total TX bytes: " << totalTxBytesFlow);
    NS_LOG_UNCOND("  Total RX bytes: " << totalRxBytesFlow);
    NS_LOG_UNCOND("  Total TX packets: " << totalTxPackets);
    NS_LOG_UNCOND("  Total RX packets: " << totalRxPackets);
    NS_LOG_UNCOND("  Packet delivery ratio: "
                  << (totalTxPackets > 0 ? (100.0 * totalRxPackets / totalTxPackets) : 0) << "%");
    NS_LOG_UNCOND("  Average delay: "
                  << (totalRxPackets > 0 ? (totalDelay / totalRxPackets * 1000) : 0) << " ms");
    NS_LOG_UNCOND("  Number of flows: " << flowCount);
    NS_LOG_UNCOND("  Estimated energy consumption: " << totalEnergy << " mJ");
    NS_LOG_UNCOND("  Simulation duration: " << simTime << " seconds");
    NS_LOG_UNCOND("\nARSTA Parameters Used:");
    NS_LOG_UNCOND("  EWMA alpha: " << ewmaAlpha);
    NS_LOG_UNCOND("  HO lock threshold: " << hoLockThreshold << " dB/s");
    NS_LOG_UNCOND("\nOutput files:");
    NS_LOG_UNCOND("  RRC transitions: " << rrcFilename);
    NS_LOG_UNCOND("  ARSTA state log: " << outputDir << "arsta_state_log_run" << rngRun << ".csv");
    NS_LOG_UNCOND("  FlowMonitor XML: " << flowMonFilename);

    // Cleanup
    delete g_rrcMonitor;
    g_rrcMonitor = nullptr;

    Simulator::Destroy();

    return 0;
}
