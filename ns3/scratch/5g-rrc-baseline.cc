/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * ARSTA Project - 3GPP Static-Timer Baseline Simulation
 *
 * This simulation implements the baseline 5G NR RRC state management
 * using static inactivity timers as per 3GPP specifications.
 * Used as comparison point for the ARSTA adaptive algorithm.
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
#include <sys/stat.h>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("5gRrcBaseline");

// Global variables for statistics
static uint64_t g_totalTxBytes = 0;
static uint64_t g_totalRxBytes = 0;
static std::ofstream g_rrcStateFile;

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
 * \brief Callback for RRC state transition tracing
 * \param context The trace context path
 * \param imsi UE IMSI
 * \param cellId Cell ID
 * \param oldState Previous RRC state
 * \param newState New RRC state
 */
void
RrcStateTransitionCallback(std::string context,
                           uint64_t imsi,
                           uint16_t cellId,
                           uint16_t oldState,
                           uint16_t newState)
{
    double timeS = Simulator::Now().GetSeconds();
    
    // Write to CSV file
    if (g_rrcStateFile.is_open())
    {
        g_rrcStateFile << std::fixed << std::setprecision(6) << timeS << ","
                       << imsi << "," << cellId << ","
                       << RrcStateToString(oldState) << ","
                       << RrcStateToString(newState) << std::endl;
    }

    NS_LOG_INFO("Time=" << timeS << "s IMSI=" << imsi << " CellId=" << cellId
                        << " " << RrcStateToString(oldState) << " -> "
                        << RrcStateToString(newState));
}

/**
 * \brief Callback to track transmitted bytes
 * \param oldValue Previous byte count
 * \param newValue Current byte count
 */
void
TxCallback(uint64_t oldValue, uint64_t newValue)
{
    g_totalTxBytes += (newValue - oldValue);
}

/**
 * \brief Callback to track received bytes
 * \param oldValue Previous byte count
 * \param newValue Current byte count
 */
void
RxCallback(uint64_t oldValue, uint64_t newValue)
{
    g_totalRxBytes += (newValue - oldValue);
}

/**
 * \brief Create output directory if it doesn't exist
 * \param path Directory path
 * \return true if successful
 */
bool
CreateDirectory(const std::string& path)
{
    struct stat info;
    if (stat(path.c_str(), &info) != 0)
    {
        // Directory doesn't exist, create it
        std::string cmd = "mkdir -p " + path;
        int result = system(cmd.c_str());
        return (result == 0);
    }
    return true;
}

int
main(int argc, char* argv[])
{
    // ============================
    // Command line parameters
    // ============================
    uint32_t numUes = 20;
    double simTime = 300.0;         // seconds
    uint32_t rngRun = 1;
    double inactivityTimer = 10.0;  // seconds (3GPP default range: 1-40s)
    std::string outputDir = "results/raw/";

    CommandLine cmd(__FILE__);
    cmd.AddValue("numUes", "Number of UEs in simulation", numUes);
    cmd.AddValue("simTime", "Total simulation time in seconds", simTime);
    cmd.AddValue("rngRun", "RNG run number for reproducibility", rngRun);
    cmd.AddValue("inactivityTimer", "RRC inactivity timer in seconds", inactivityTimer);
    cmd.AddValue("outputDir", "Output directory for results", outputDir);
    cmd.Parse(argc, argv);

    // Set RNG seed for reproducibility
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(rngRun);

    // Create output directory
    CreateDirectory(outputDir);

    // Open RRC state transition CSV file
    std::string rrcFilename = outputDir + "rrc_transitions_run" + std::to_string(rngRun) + ".csv";
    g_rrcStateFile.open(rrcFilename);
    if (!g_rrcStateFile.is_open())
    {
        NS_FATAL_ERROR("Could not open RRC state file: " << rrcFilename);
    }
    // Write CSV header
    g_rrcStateFile << "time_s,imsi,cell_id,old_state,new_state" << std::endl;

    NS_LOG_UNCOND("=== ARSTA 5G-NR RRC Baseline Simulation ===");
    NS_LOG_UNCOND("Parameters:");
    NS_LOG_UNCOND("  Number of UEs: " << numUes);
    NS_LOG_UNCOND("  Simulation time: " << simTime << " s");
    NS_LOG_UNCOND("  RNG run: " << rngRun);
    NS_LOG_UNCOND("  Inactivity timer: " << inactivityTimer << " s");
    NS_LOG_UNCOND("  Output directory: " << outputDir);

    // ============================
    // Network topology setup
    // ============================

    // Create NR helpers
    Ptr<NrPointToPointEpcHelper> epcHelper = CreateObject<NrPointToPointEpcHelper>();
    Ptr<IdealBeamformingHelper> idealBeamformingHelper = CreateObject<IdealBeamformingHelper>();
    Ptr<NrHelper> nrHelper = CreateObject<NrHelper>();

    nrHelper->SetBeamformingHelper(idealBeamformingHelper);
    nrHelper->SetEpcHelper(epcHelper);

    // ============================
    // Spectrum configuration
    // 3.5 GHz FR1, 40 MHz BW, numerology mu=1 (30 kHz SCS)
    // ============================
    double centralFrequencyBand = 3.5e9;  // 3.5 GHz
    double bandwidthBand = 40e6;          // 40 MHz
    uint16_t numerology = 1;              // 30 kHz subcarrier spacing

    // Configure the spectrum
    BandwidthPartInfoPtrVector allBwps;
    CcBwpCreator ccBwpCreator;

    CcBwpCreator::SimpleOperationBandConf bandConf(centralFrequencyBand,
                                                    bandwidthBand,
                                                    1,  // number of CCs
                                                    BandwidthPartInfo::UMa);
    
    OperationBandInfo band = ccBwpCreator.CreateOperationBandContiguousCc(bandConf);

    // Configure ideal beamforming
    idealBeamformingHelper->SetAttribute("BeamformingMethod",
                                          TypeIdValue(DirectPathBeamforming::GetTypeId()));

    // Initialize the band
    nrHelper->InitializeOperationBand(&band);
    allBwps = CcBwpCreator::GetAllBwps({band});

    // ============================
    // Create gNB nodes
    // Equilateral triangle: (0,0,25), (500,0,25), (250,433,25)
    // ============================
    NodeContainer gnbNodes;
    gnbNodes.Create(3);

    // Set gNB positions
    Ptr<ListPositionAllocator> gnbPositionAlloc = CreateObject<ListPositionAllocator>();
    gnbPositionAlloc->Add(Vector(0.0, 0.0, 25.0));      // gNB 1
    gnbPositionAlloc->Add(Vector(500.0, 0.0, 25.0));    // gNB 2
    gnbPositionAlloc->Add(Vector(250.0, 433.0, 25.0));  // gNB 3 (sqrt(3)/2 * 500 ≈ 433)

    MobilityHelper gnbMobility;
    gnbMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    gnbMobility.SetPositionAllocator(gnbPositionAlloc);
    gnbMobility.Install(gnbNodes);

    // ============================
    // Create UE nodes with RandomWaypointMobility
    // ============================
    NodeContainer ueNodes;
    ueNodes.Create(numUes);

    // Define the mobility area (cover the triangle area with some margin)
    double minX = -50.0;
    double maxX = 550.0;
    double minY = -50.0;
    double maxY = 500.0;

    // Position allocator for random initial positions
    Ptr<RandomRectanglePositionAllocator> uePositionAlloc =
        CreateObject<RandomRectanglePositionAllocator>();
    uePositionAlloc->SetAttribute("X", StringValue("ns3::UniformRandomVariable[Min=" +
                                                    std::to_string(minX) + "|Max=" +
                                                    std::to_string(maxX) + "]"));
    uePositionAlloc->SetAttribute("Y", StringValue("ns3::UniformRandomVariable[Min=" +
                                                    std::to_string(minY) + "|Max=" +
                                                    std::to_string(maxY) + "]"));

    // Random waypoint mobility configuration
    MobilityHelper ueMobility;
    ueMobility.SetMobilityModel(
        "ns3::RandomWaypointMobilityModel",
        "Speed", StringValue("ns3::UniformRandomVariable[Min=1.0|Max=10.0]"),
        "Pause", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"),
        "PositionAllocator", PointerValue(uePositionAlloc));
    
    ueMobility.SetPositionAllocator(uePositionAlloc);
    ueMobility.Install(ueNodes);

    // Set UE heights to 1.5m (typical pedestrian height)
    for (uint32_t i = 0; i < ueNodes.GetN(); ++i)
    {
        Ptr<MobilityModel> mm = ueNodes.Get(i)->GetObject<MobilityModel>();
        Vector pos = mm->GetPosition();
        pos.z = 1.5;
        mm->SetPosition(pos);
    }

    // ============================
    // Configure gNB transmission parameters
    // TxPower = 43 dBm
    // ============================
    nrHelper->SetGnbPhyAttribute("TxPower", DoubleValue(43.0));
    nrHelper->SetGnbPhyAttribute("Numerology", UintegerValue(numerology));

    // Configure UE transmission parameters
    nrHelper->SetUePhyAttribute("TxPower", DoubleValue(23.0));  // Typical UE Tx power

    // ============================
    // Install NR devices
    // ============================
    NetDeviceContainer gnbDevices = nrHelper->InstallGnbDevice(gnbNodes, allBwps);
    NetDeviceContainer ueDevices = nrHelper->InstallUeDevice(ueNodes, allBwps);

    // Update device configurations
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

    // Assign IP addresses
    Ipv4InterfaceContainer ueIpIface = epcHelper->AssignUeIpv4Address(ueDevices);

    // Set default routes for UEs
    Ipv4StaticRoutingHelper ipv4RoutingHelper;
    for (uint32_t u = 0; u < ueNodes.GetN(); ++u)
    {
        Ptr<Node> ueNode = ueNodes.Get(u);
        Ptr<Ipv4StaticRouting> ueStaticRouting =
            ipv4RoutingHelper.GetStaticRouting(ueNode->GetObject<Ipv4>());
        ueStaticRouting->SetDefaultRoute(epcHelper->GetUeDefaultGatewayAddress(), 1);
    }

    // Attach UEs to the network (automatic cell selection)
    nrHelper->AttachToClosestEnb(ueDevices, gnbDevices);

    // ============================
    // Install applications
    // OnOff traffic: rate=1Mbps, ON=ExponentialRV[Mean=2], OFF=ExponentialRV[Mean=8]
    // ============================
    Ptr<Node> remoteHost = epcHelper->GetPgwNode();

    // Remote host already has internet stack via EPC helper
    // Create a remote server node
    NodeContainer remoteHostContainer;
    remoteHostContainer.Create(1);
    Ptr<Node> serverNode = remoteHostContainer.Get(0);
    internet.Install(remoteHostContainer);

    // Point-to-point link to remote host
    PointToPointHelper p2ph;
    p2ph.SetDeviceAttribute("DataRate", DataRateValue(DataRate("100Gb/s")));
    p2ph.SetDeviceAttribute("Mtu", UintegerValue(1500));
    p2ph.SetChannelAttribute("Delay", TimeValue(MilliSeconds(10)));

    NetDeviceContainer internetDevices = p2ph.Install(epcHelper->GetPgwNode(), serverNode);
    
    Ipv4AddressHelper ipv4h;
    ipv4h.SetBase("1.0.0.0", "255.0.0.0");
    Ipv4InterfaceContainer internetIpIfaces = ipv4h.Assign(internetDevices);
    Ipv4Address remoteHostAddr = internetIpIfaces.GetAddress(1);

    // Add route from remote host to UEs
    Ptr<Ipv4StaticRouting> remoteHostStaticRouting =
        ipv4RoutingHelper.GetStaticRouting(serverNode->GetObject<Ipv4>());
    remoteHostStaticRouting->AddNetworkRouteTo(Ipv4Address("7.0.0.0"),
                                                Ipv4Mask("255.0.0.0"),
                                                1);

    // Install OnOff applications (downlink: server -> UE)
    uint16_t dlPort = 1234;
    ApplicationContainer serverApps;
    ApplicationContainer clientApps;

    for (uint32_t u = 0; u < ueNodes.GetN(); ++u)
    {
        // Packet sink on UE
        PacketSinkHelper packetSinkHelper("ns3::UdpSocketFactory",
                                           InetSocketAddress(Ipv4Address::GetAny(), dlPort + u));
        serverApps.Add(packetSinkHelper.Install(ueNodes.Get(u)));

        // OnOff application on remote host
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

    // Start applications with slight stagger to avoid synchronization
    serverApps.Start(Seconds(0.1));
    clientApps.Start(Seconds(0.5));
    serverApps.Stop(Seconds(simTime - 0.1));
    clientApps.Stop(Seconds(simTime - 0.5));

    // ============================
    // Connect trace callbacks for RRC state transitions
    // ============================
    Config::Connect("/NodeList/*/DeviceList/*/LteUeRrc/StateTransition",
                    MakeCallback(&RrcStateTransitionCallback));

    // Track bytes for statistics
    Config::ConnectWithoutContext("/NodeList/*/ApplicationList/*/$ns3::PacketSink/Rx",
                                   MakeCallback(&RxCallback));
    Config::ConnectWithoutContext("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/Tx",
                                   MakeCallback(&TxCallback));

    // ============================
    // Install FlowMonitor
    // ============================
    FlowMonitorHelper flowMonHelper;
    Ptr<FlowMonitor> flowMonitor = flowMonHelper.InstallAll();

    // ============================
    // Run simulation
    // ============================
    NS_LOG_UNCOND("\nStarting simulation...");

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();

    // ============================
    // Collect and save results
    // ============================
    
    // Save FlowMonitor results to XML
    std::string flowMonFilename = outputDir + "flowmon_run" + std::to_string(rngRun) + ".xml";
    flowMonitor->SerializeToXmlFile(flowMonFilename, true, true);

    // Calculate statistics from FlowMonitor
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

    // Close RRC state file
    g_rrcStateFile.close();

    // ============================
    // Print summary to stdout
    // ============================
    NS_LOG_UNCOND("\n=== Simulation Complete ===");
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
    NS_LOG_UNCOND("  Simulation duration: " << simTime << " seconds");
    NS_LOG_UNCOND("\nOutput files:");
    NS_LOG_UNCOND("  RRC transitions: " << rrcFilename);
    NS_LOG_UNCOND("  FlowMonitor XML: " << flowMonFilename);

    Simulator::Destroy();

    return 0;
}
