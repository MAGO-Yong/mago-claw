# Wireless Value Realization — Research Report

**Year:** 2023 (announced October 17, 2022)
**Topic Code:** 2023-06
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

### 1. Topic Alignment

**Definition (Gartner):** Wireless value realization (WVR) refers to the increasing number of wireless networking and connectivity solutions available to enterprises—including 5G, Wi-Fi 6/6E, LPWAN, LEO satellite—that enable new business outcomes when actively applied. The key is "realization"—moving from infrastructure investment to actual business value creation.

**Gartner's Insight:** "Wireless" is expanding from simple connectivity to a business capability. A 5G private network isn't valuable because it connects devices—it's valuable because it enables specific business outcomes: automated factories, autonomous vehicles on campus, remote surgery, real-time supply chain visibility. The "realization" part means enterprises need strategies to extract business value from wireless investments.

**Wireless Technology Landscape (2023):**

| Technology | Key Characteristics | Primary Use Cases |
|------------|--------------------|--------------------|
| 5G (Public) | High bandwidth, wide coverage | Mobile broadband, enhanced consumer |
| 5G Private | Dedicated, secure, low latency | Industry 4.0, campus automation |
| Wi-Fi 6/6E | High density, 6GHz band | Office/campus, IoT |
| LPWAN (LoRaWAN, NB-IoT) | Low power, wide area, low data | IoT sensors, asset tracking |
| LEO Satellite (Starlink, OneWeb) | Global coverage, increasing speed | Remote/rural connectivity |
| DECT-2020 (5G NR-U) | Industrial wireless | Factory automation |

**Adjacent Concepts:**
- **5G**: Core technology enabler within WVR
- **Wi-Fi 6**: Specific wireless standard within WVR
- **IoT**: Primary user of LPWAN and private 5G
- **Edge Computing**: Wireless endpoints generate data; edge processes it locally
- **Autonomous Systems** (2022): Wireless connectivity enables autonomous operation

---

### 2. Context and Drivers

**5G Deployment Acceleration:**
By 2022, 5G networks had deployed in 65+ countries. US operators (Verizon, AT&T, T-Mobile) covered major metros. Enterprise 5G was beginning, with private 5G networks being piloted at factories, ports, and hospitals.

**Wi-Fi 6 Proliferation:**
Wi-Fi 6 (802.11ax) addressed the congestion and capacity issues of previous Wi-Fi generations:
- 4x increase in capacity per access point
- Better performance in high-density environments (arenas, offices, factories)
- Lower latency enabling real-time applications
- 802.11ax certification: 2.4/5 GHz; Wi-Fi 6E extended to 6 GHz for additional spectrum

**LEO Satellite Emergence:**
Starlink (SpaceX) demonstrated that Low Earth Orbit satellites could provide:
- Global coverage including maritime, remote, and developing regions
- Latency of 20-40ms (vs. 600ms for geostationary)
- Bandwidth of 100-300 Mbps for end users

Gartner prediction: By 2025, organizations exploiting pervasive wireless connectivity will realize 20% productivity improvements through edge-AI capabilities enabled by pervasive wireless.

---

### 3. Foundational Research Findings

#### 3.1 Private 5G Networks: The Enterprise Frontier

Private 5G is the most enterprise-specific wireless trend within WVR:

**What is Private 5G?**
A dedicated 5G network deployed within an organization's premises. Unlike public 5G (shared spectrum, shared infrastructure), private 5G uses:
- Dedicated spectrum (CBRS in US, 3.5GHz bands in Europe)
- On-premises or edge cloud infrastructure
- 5G SA (Standalone Architecture) for maximum capability
- Network slicing for traffic prioritization

**Why Private 5G over Wi-Fi?**
- Deterministic latency (critical for robotics, machine control)
- Better coverage in challenging environments (factories, warehouses, mines)
- Stronger security isolation
- Mobility support (handover between cells without disruption)
- Support for 10,000+ devices per cell

**Early Private 5G Deployments:**

**BMW Leipzig Plant:**
BMW deployed private 5G across their Leipzig manufacturing facility. Enables:
- Automated Guided Vehicles (AGVs) with 5G connectivity
- Real-time quality control camera feeds
- Worker augmented reality for assembly guidance
- Reported: 30% productivity improvement in connected production areas

**Port of Hamburg (Hamburger Hafen):**
Private 5G for port operations: crane automation, truck routing, container tracking. Key value: real-time data from all moving assets for operational optimization.

**University Hospital Aachen:**
Private 5G hospital network. Enables: mobile imaging carts with real-time data, AR-assisted surgery (surgeon viewing imaging data during procedure), telepresence for remote expert consultation.

**Nokia as Private 5G Leader:**
Nokia reported 400+ private wireless customers by 2022, including BMW, Volkswagen, Amazon warehouses, military bases. Nokia's DAC (Digital Automation Cloud) platform specifically targets enterprise private 5G deployment.

#### 3.2 Wi-Fi 6 Enterprise Value

Wi-Fi 6 delivered measurable improvements in enterprise environments:
- **Financial services trading floor**: 40% increase in capacity with Wi-Fi 6 infrastructure; eliminated performance degradation during peak trading hours
- **University campuses**: Wi-Fi 6 supporting 50,000+ concurrent devices across campuses with equal performance for all students
- **Healthcare**: Wi-Fi 6 enabling reliable connected medical devices (previously an IoT reliability problem on older Wi-Fi)

#### 3.3 LPWAN for IoT at Scale

Low Power Wide Area Networks (LoRaWAN, NB-IoT, Sigfox) enable IoT at massive scale:
- **Smart city**: 100,000+ sensors for smart parking, waste bin monitoring, street lighting—all LPWAN connected
- **Agriculture**: Soil moisture, temperature sensors across thousands of acres; LPWAN provides multi-year battery life
- **Asset tracking**: Supply chain tracking for pallets, containers—LoRaWAN enables tracking without GPS power cost

#### 3.4 Starlink Enterprise Applications

Starlink Business (launched 2021) enabling:
- **Maritime**: Real-time connectivity on vessels globally; Carnival Cruises deployed on all ships
- **Aviation**: Starlink aviation service: 600+ aircraft globally by 2023 (Delta, Hawaiian Airlines)
- **Remote operations**: Mining, oil & gas operations with previously no connectivity option
- **Backup connectivity**: Enterprise WAN backup at remote sites

---

### 4. Value Framework: From Connectivity to Business Outcome

Gartner's WVR framing emphasizes that wireless investment only creates value when connected to specific business outcomes:

| Wireless Technology | Business Outcome | Value Metric |
|--------------------|-----------------|----|
| Private 5G (factory) | Automated production | % throughput increase |
| Wi-Fi 6 (hospital) | Clinical mobility | % nurse documentation time saved |
| LPWAN (logistics) | Asset visibility | % reduction in lost assets |
| LEO Satellite (remote) | Business continuity | % downtime reduction |

---

## Round 2: Deep-Dive — Private 5G vs. Wi-Fi: The Enterprise Decision

### Research Question

**Most practical question for enterprise buyers:** When should an enterprise choose Private 5G over Wi-Fi 6 for a new wireless deployment?

### Deep Findings

#### Decision Framework

The "right" wireless technology depends on the specific use case requirements:

**Choose Wi-Fi 6/6E when:**
- Indoor environments with manageable interference
- High device density but moderate latency requirements (>10ms tolerable)
- Existing Wi-Fi infrastructure to leverage
- Budget constraints (Wi-Fi 6 ~$300-500 per AP vs. 5G node $2,000-10,000+)
- Primarily data/video traffic (not real-time control)

**Choose Private 5G when:**
- Real-time control systems (robotics, machine control) requiring <10ms latency
- Large campus/outdoor area requiring consistent coverage
- High device mobility (AGVs, forklifts, workers covering large distances)
- Mission-critical reliability requirement (99.999% uptime)
- Challenging RF environment (metal structures, interference)

**Hybrid approach (increasingly common):**
- Wi-Fi 6 for office/general areas (cost-efficient)
- Private 5G for production/logistics areas (performance-critical)
- Single management plane connecting both

**Cost Reality:**
Private 5G TCO is 5-10x higher than Wi-Fi for equivalent coverage. The ROI justification requires significant operational improvement—BMW's 30% productivity improvement easily justifies investment; a general office would not.

#### Timeline for Private 5G Mainstream

Based on early deployments and market trajectories:
- **2022-2024**: Innovator/early adopter phase; manufacturing, mining, healthcare
- **2025-2027**: Early majority; standardization drives cost reduction
- **2028+**: Mainstream; private 5G as competitive baseline for industrial facilities

GSMA predicted: 440+ private 5G networks deployed globally by end of 2023 (actual deployments may be higher, definitions vary).

### Round 2 Conclusion

Wireless value realization is realized technology-agnostic: identify the business outcome, then select the wireless technology that best enables it at acceptable cost. For most enterprises, Wi-Fi 6 suffices for office and general commercial applications. Private 5G justifies investment for industrial automation, large outdoor campuses, and high-reliability real-time applications. The decision framework (use case requirements → technology selection → value metrics) ensures wireless investments create business value rather than just infrastructure capability.

---

## Sources

1. Gartner 2023 Strategic Technology Trends
2. Nokia Digital Automation Cloud: 400+ private wireless customers (Nokia press release, 2022)
3. BMW Leipzig private 5G case study (Nokia/BMW joint announcement)
4. Port of Hamburg private 5G (Ericsson case study)
5. Starlink Business deployment statistics (SpaceX press releases)
6. GSMA: 440+ private 5G networks prediction
7. Wi-Fi Alliance: Wi-Fi 6 certification program data

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~1,100 words*
