# Anywhere Operations — Research Report

**Year:** 2021
**Topic Code:** 2021-05
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

### 1. Topic Alignment

**Definition (Gartner):** Anywhere operations is an IT operating model designed to support customers everywhere, enable employees everywhere, and manage the deployment of business services across distributed infrastructures. It goes beyond "work from home"—it addresses how organizations deliver business services and value when both employees and customers may be in any location.

**Five Core Dimensions (Gartner's framework):**
1. **Collaboration and productivity**: Tools enabling effective work regardless of location (Microsoft Teams, Slack, Zoom)
2. **Secure remote access**: Zero-trust network architecture, VPN replacement, identity-first security
3. **Cloud and edge infrastructure**: Applications and services accessible from any location
4. **Quantification of digital experience**: Monitoring and measuring digital experience quality for remote workers and customers
5. **Automation to support remote operations**: Reducing need for physical presence in IT operations and service delivery

**Adjacent Concepts:**
- **Remote Work / Work From Home**: A subset of anywhere operations—AO addresses the full organizational model
- **Digital Transformation**: AO is a specific pattern of digital transformation
- **Zero Trust Architecture**: Critical enabler of secure anywhere access
- **Digital Experience Monitoring (DEM)**: The "quantification" component of AO
- **Distributed Enterprise** (2022 Gartner trend): Evolution of anywhere operations concept

---

### 2. Context and Drivers

Announced October 2020 as a direct response to COVID-19, Anywhere Operations was perhaps the most immediately relevant trend in Gartner's 2021 list. By Q2 2020, most knowledge workers globally were forced to work remotely; retail, hospitality, and services companies were forced to redesign customer interaction models.

**Pre-Pandemic State:**
- Most IT infrastructure assumed on-premises workers
- VPN solutions were sized for 10-20% of workforce; COVID required 80-100%
- Customer interactions still primarily in-person or via call center (physical)

**Pandemic Catalyst:**
- Remote workforce scale jumped from ~20% to ~70-80% for knowledge workers in March-April 2020
- Customer interactions shifted to digital (online ordering, telemedicine, digital banking)
- IT teams needed to support remote infrastructure without physical access to offices

---

### 3. Foundational Research Findings

#### 3.1 Market Impact and Scale

- **Video conferencing market**: Grew from $3.9 billion (2019) to $7.2 billion (2021)—Zoom alone grew revenue 326% in FY2021
- **Endpoint security market**: Grew 25%+ in 2020 as remote devices became the attack surface
- **Digital adoption platforms**: Grew to serve remote onboarding and training needs
- **Cloud communication platforms**: Microsoft Teams grew from 20M to 145M daily active users March 2020 to April 2021

#### 3.2 Technology Components

**Collaboration Infrastructure:**
- Microsoft 365 / Teams (dominant enterprise stack)
- Google Workspace / Meet
- Zoom (video-first)
- Slack (messaging-first, now part of Salesforce)

**Secure Access:**
- Zero Trust Network Access (ZTNA) replacing VPN: Zscaler, Palo Alto Prisma, Cloudflare
- MDM/UEM: Microsoft Intune, Jamf, VMware Workspace ONE
- Identity: Okta, Azure AD, Ping Identity

**Digital Experience Monitoring:**
- Nexthink, Riverbed (SteelConnect), Lakeside Software
- Monitor application performance, device health, network quality from employee perspective

**Automation/Remote IT Operations:**
- AIOps platforms: Splunk, ServiceNow (IT Operations)
- Remote support: TeamViewer, Bomgar
- Infrastructure as Code: Terraform, Ansible for remote-managed infrastructure

#### 3.3 Organizational Impact

**Work Model Evolution:**
Gartner predicted in 2021 that by end of 2023, 40% of organizations would have applied anywhere operations. What actually happened was more nuanced:
- Full remote: Most professional services, tech companies (~25% maintained full remote)
- Hybrid: Became the dominant model for knowledge workers (~55%)
- Return to office: Financial services, government pushed for return (~20%)

**Real Impact on IT Organizations:**
- Help desk volume increased 35-40% during initial remote transition
- Network security incidents increased (home devices, consumer wifi, shadow IT)
- Employee experience monitoring became critical—IT teams needed visibility into remote worker digital experience

#### 3.4 Customer Operations Anywhere

Less discussed but equally important: the "customers anywhere" dimension.

**Telemedicine**: Healthcare visits migrated to telehealth platforms. Teladoc, Amwell saw explosive growth 2020-2021. By 2021, telehealth represented ~30% of primary care visits (vs. <1% pre-pandemic).

**Digital Banking**: In-person bank branch visits fell 30-40% permanently. Banks accelerated digital onboarding to allow account opening without branch visit.

**Contactless Retail**: Curbside pickup, BOPIS (buy online, pick up in-store), and delivery became standard. Starbucks' mobile app ordering (28% of US transactions pre-pandemic) became template for contactless retail.

#### 3.5 Maturity and Evolution

By 2022, Gartner renamed/evolved "anywhere operations" to "distributed enterprise" in their 2022 trends list, reflecting the shift from crisis response to strategic operating model.

By 2024, anywhere operations had largely become baseline expectations—it was no longer "strategic" but "operational necessity." Companies that didn't build AO capability during COVID faced lasting competitive disadvantage in talent recruitment (remote options expected) and customer satisfaction (digital channels required).

---

### 4. Value Proposition

**For Organizations:**
- Business continuity in disruption scenarios
- Access to global talent pool (no geographic constraints)
- Reduced physical real estate costs
- 24/7 service delivery potential

**For Employees:**
- Work-life integration (not just balance)
- Reduced commuting time (productivity gain)
- Geographic flexibility

**For Customers:**
- 24/7 digital access to services
- Reduced friction in routine transactions
- Consistent experience across physical/digital touchpoints

---

## Round 2: Deep-Dive — The Digital Experience Gap

### Research Question

**Most important unresolved question:** How do organizations measure and optimize the digital experience for remote employees and customers when traditional monitoring tools don't capture the full picture?

### Deep Findings

#### The Measurement Problem

Traditional IT monitoring watched networks, servers, and applications from the infrastructure side. Remote work created a new problem: the employee's experience depends on:
- Their home internet quality (ISP, WiFi, neighbors downloading, router age)
- Their device's health (local CPU, memory, background processes)
- Application performance (cloud latency, API response times)
- Meeting quality (camera, microphone, video codec)

IT had visibility into none of the first three. This "last mile" blindspot created situations where IT said "servers are fine" but employees reported constant technical problems.

#### Digital Experience Monitoring (DEM) Solutions

DEM platforms address this by installing lightweight agents on employee endpoints that monitor:
- Application response times from the user's perspective
- Device performance metrics (CPU, memory, disk)
- Network path quality (traceroute, packet loss)
- Meeting quality (jitter, latency, audio quality)
- Digital adoption patterns (are employees using tools effectively?)

**Nexthink**: Pioneer in end-user experience monitoring; integrates with ITSM tools to correlate experience data with tickets
**Lakeside SysTrack**: Deep device analytics
**Riverbed SteelConnect**: Network performance monitoring with user-experience focus

#### Emerging Best Practices

Organizations successfully managing anywhere operations typically:
1. Establish baseline digital experience scores before IT changes
2. Monitor experience in near-real-time, not just on complaint
3. Use experience data to proactively remediate before employees report problems
4. Connect experience metrics to business outcomes (call center handle time, developer velocity)
5. Share experience dashboards with employees (transparency builds trust)

### Round 2 Conclusion

The "quantification of digital experience" is the least mature and most strategically important component of anywhere operations. Organizations investing in DEM and connecting experience data to business outcomes are moving from reactive IT support to proactive experience management—a significant competitive advantage for talent retention and productivity.

---

## Sources

1. Gartner 2021 Strategic Technology Trends
2. Zoom FY2021 annual report
3. Microsoft Teams growth statistics (Microsoft press releases 2021)
4. Gartner prediction: 40% of organizations applying anywhere operations by 2023
5. Teladoc and Amwell telehealth growth statistics (company earnings reports)
6. Nexthink and Lakeside SysTrack product documentation
7. Forrester Research: Remote work impact on IT operations (2021)

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~1,150 words*
