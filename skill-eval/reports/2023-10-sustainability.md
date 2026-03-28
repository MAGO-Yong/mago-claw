# Sustainability — Research Report

**Year:** 2023 (announced October 17, 2022)
**Topic Code:** 2023-10
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

### 1. Topic Alignment

**Definition (Gartner):** Sustainable technology refers to a framework of digital solutions that enables environmental, social and governance (ESG) outcomes for the enterprise and its customers. It encompasses green IT (reducing technology's own environmental impact), technology that enables sustainability in other domains, and technology supporting the measurement and reporting of sustainability outcomes.

**Three Dimensions of Sustainable Technology:**

1. **IT Sustainability (Greening IT)**: Reducing technology's own carbon footprint
   - Energy-efficient hardware and data centers
   - Cloud consolidation (hyperscalers more efficient than corporate data centers)
   - Software efficiency (better code uses less compute, less energy)
   - E-waste management (responsible device lifecycle)

2. **Technology Enabling Sustainability (IT for Green)**: Technology helping non-IT domains become sustainable
   - Smart building management systems
   - Supply chain emissions tracking
   - Precision agriculture (reducing water, fertilizer, pesticide use)
   - Grid optimization and renewable energy management

3. **ESG Reporting Technology**: Measuring and reporting sustainability outcomes
   - Carbon accounting software
   - Scope 1, 2, 3 emissions calculation and tracking
   - Sustainability disclosure automation (SEC, EU CSRD requirements)

**Adjacent Concepts:**
- **Sustainable Technology** (2024 trend—the term shifted): Same concept, continued from 2023
- **Energy-Efficient Computing** (2025 trend): AI's energy footprint drove this to its own trend
- **Digital Twins**: Can model energy and environmental impacts before physical changes
- **AI for Climate**: Specific application domain (climate modeling, material discovery)

---

### 2. Context and Drivers

**Corporate Net Zero Commitments:**
By 2022, 2,000+ companies globally had made some form of net zero commitment, including 70% of S&P 500 companies. These commitments required technology to:
- Measure current emissions (baselines)
- Track progress toward targets
- Identify and implement reduction opportunities
- Report to stakeholders, regulators, and investors

**Regulatory Pressure:**
- **EU Corporate Sustainability Reporting Directive (CSRD)**: Required sustainability reporting for 50,000+ EU companies from 2024
- **SEC Climate Disclosure Rule** (US, 2024): Required Scope 1, 2, and some Scope 3 emissions disclosure
- **TCFD** (Task Force on Climate-related Financial Disclosures): Increasingly mandated by regulators and investors

**Investor Demand:**
- ESG investing reached $40 trillion in 2022 (Bloomberg Intelligence)
- BlackRock: Made climate risk a central investment criterion
- Institutional investors requiring sustainability reporting for capital access

---

### 3. Foundational Research Findings

#### 3.1 IT's Own Environmental Impact

Technology's carbon footprint is substantial:
- **Data centers**: 1-1.5% of global electricity consumption (estimates vary); growing with AI
- **ICT sector overall**: 2-4% of global CO2 emissions (pre-GenAI acceleration)
- **AI training energy cost**: Training GPT-3 estimated to emit 552 tons CO2e; GPT-4 training costs significantly higher
- **End-user devices**: Smartphones, laptops, TVs, IoT sensors collectively massive energy users

**Hyperscaler Commitments:**
- **Microsoft**: Carbon negative by 2030; remove all historical emissions by 2050; 100% renewable energy by 2025
- **Google**: Carbon neutral since 2007; 100% renewable energy 24/7 by 2030; net zero by 2030
- **Amazon**: Net zero by 2040; Climate Pledge; largest corporate buyer of renewable energy globally

**Efficient Cloud vs. Enterprise Data Centers:**
Accenture research: Migrating enterprise workloads from on-premises data centers to leading cloud providers reduces energy consumption by 65-84%. Cloud's efficiency advantage is genuine and significant.

#### 3.2 Technology Enabling Sustainability

**Smart Building Management:**
- BMS (Building Management Systems): HVAC, lighting, elevator optimization
- IoT sensors enabling dynamic optimization based on occupancy, weather, energy prices
- Siemens Desigo CC: Building management platform; reported 20-30% energy reduction in deployed buildings
- Microsoft's own buildings: AI-optimized HVAC reduced energy use 15% at campus level

**Supply Chain Emissions Tracking:**
Scope 3 emissions (upstream supply chain and downstream product use) are often 70-90% of a company's total emissions—but the hardest to measure.
- **Watershed**: Carbon accounting platform; raised $70M to track Scope 3 supply chain emissions
- **Salesforce Net Zero Cloud**: ESG reporting and carbon accounting
- **SAP Sustainability**: ERP integration for supply chain emissions

**Precision Agriculture:**
- John Deere's precision agriculture tech: Variable rate seeding and fertilization, reducing input use 10-20%
- Climate FieldView (Bayer): Data-driven crop management reducing water and chemical use
- Drone monitoring: Crop health surveillance enabling targeted (vs. blanket) pesticide application

**Renewable Energy Management:**
- Virtual Power Plants (VPP): Software aggregating distributed renewable sources (rooftop solar, batteries) into grid resources
- Energy markets: AI-driven energy trading optimizing renewable integration
- Building demand response: Commercial buildings reducing consumption during peak demand

#### 3.3 ESG Reporting Technology

The ESG data market was emerging and chaotic in 2022-2023:

**Carbon Accounting Platforms:**
- Watershed, Sweep, Greenly, Persefoni, Sinai—venture-backed startups
- Salesforce Net Zero Cloud—enterprise platform
- SAP Sustainability—ERP-integrated approach
- IBM Environmental Intelligence Suite

**Data Quality Problem:**
Scope 3 emissions calculation is notoriously difficult:
- Relies on supplier data that may be unavailable or inaccurate
- Emission factors used vary significantly across methodologies
- "Spend-based" vs. "activity-based" calculation approaches produce very different results
- Greenwashing risk: Companies can present favorable numbers through methodology choices

**Regulatory Complexity:**
Multiple overlapping frameworks:
- GHG Protocol (most widely used)
- GRI Standards
- SASB Standards (industry-specific)
- TCFD
- EU ESRS (European Sustainability Reporting Standards)

Harmonization efforts ongoing; no single global standard.

#### 3.4 AI's Sustainability Paradox

By late 2022, a tension was emerging that would become a major 2024-2025 topic:
- **AI consumes massive energy**: GenAI models require enormous computing power for training and inference
- **AI can improve sustainability**: The same AI can optimize energy systems, reduce waste, improve efficiency

This tension (AI as both energy consumer and sustainability enabler) drove Gartner's 2025 trend "Energy-Efficient Computing."

---

### 4. Value Proposition

1. **Regulatory compliance**: Meet CSRD, SEC, and other mandatory sustainability disclosure requirements
2. **Capital access**: Institutional investors requiring ESG disclosure
3. **Operating cost reduction**: Energy efficiency directly reduces costs
4. **Talent attraction**: 40%+ of employees (especially under 35) consider sustainability in employment decisions
5. **Risk management**: Climate-related business risks are real and growing

---

## Round 2: Deep-Dive — Scope 3 Emissions: The Hard Problem

### Research Question

**Most practically difficult challenge:** Scope 3 emissions (supply chain and downstream use) represent 70-90% of most companies' emissions but are notoriously difficult to measure accurately. What approaches are emerging to address this?

### Deep Findings

#### The Scope 3 Problem

**GHG Protocol definitions:**
- Scope 1: Direct emissions from owned operations (company vehicles, natural gas)
- Scope 2: Indirect emissions from purchased electricity
- Scope 3: All other indirect emissions in value chain (15 categories including supply chain, business travel, employee commuting, use of sold products)

**Why Scope 3 is hard:**
- Data comes from thousands of suppliers, not your own systems
- Suppliers vary in their data quality and reporting maturity
- Multiple calculation methodologies (spend-based, activity-based, supplier-specific)
- Different standards require different scope 3 coverage

**The Spend-Based Fallback:**
When activity data is unavailable, companies use spend-based estimates: multiply spending on a category by an emissions factor for that category. This is inaccurate (same dollar spent on different suppliers can have very different emissions) but tractable.

#### Emerging Solutions

**Supplier Data Platforms:**
- **EcoVadis**: 70,000+ supplier sustainability assessments; creates supplier-level emissions data
- **Sedex**: Supply chain sustainability data platform; 60,000+ members
- **CDP Supply Chain**: 800+ corporate signatories; 18,000+ suppliers reporting through CDP

**Blockchain-Based Traceability:**
Some industries using blockchain to track emissions through supply chain:
- IBM Food Trust for agricultural supply chains
- Limitations: Data entry quality problem; blockchain doesn't improve accuracy of human-entered data

**Standardization:**
- WBCSD Value Chain Carbon Transparency Pathfinder: Industry initiative for standardized Scope 3 data exchange via API
- ISO 14064 updates addressing supply chain methodology
- GHG Protocol Scope 3 Technical Guidance (2011, under revision)

#### Realistic Enterprise Approach

Given current limitations, enterprises should:
1. **Start with Scope 1 and 2**: These are tractable and required first
2. **Identify "hotspot" Scope 3 categories**: Not all 15 categories are equal; identify 2-3 categories representing 80%+ of Scope 3
3. **Spend-based estimate for baseline**: Imperfect but establishes direction and magnitude
4. **Supplier engagement for priority categories**: Work with top 50-100 suppliers to get actual data
5. **Build toward activity-based data**: Over 3-5 years, progressively improve data quality

### Round 2 Conclusion

Sustainable technology is simultaneously a compliance necessity (regulatory requirements growing) and a business opportunity (energy efficiency reduces costs; supply chain visibility reduces risk). The biggest implementation challenge is Scope 3 emissions data—enterprises should set realistic timelines (3-5 years for meaningful Scope 3 accuracy) and prioritize hotspot categories rather than attempting comprehensive measurement from day one. The technology infrastructure for sustainability measurement is rapidly maturing; the data quality and organizational process challenges are the harder near-term problem.

---

## Sources

1. Gartner 2023 Strategic Technology Trends
2. EU Corporate Sustainability Reporting Directive (CSRD) text
3. SEC Climate Disclosure Rule (2024)
4. Bloomberg Intelligence: ESG investing statistics
5. Accenture: Cloud migration energy efficiency research
6. Microsoft, Google, Amazon sustainability commitments and reports
7. CDP Supply Chain report (2022)
8. WBCSD Carbon Transparency Pathfinder documentation

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~1,200 words*
