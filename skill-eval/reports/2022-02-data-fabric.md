# Data Fabric — Research Report

**Year:** 2022
**Topic Code:** 2022-02
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

### 1. Topic Alignment

**Definition (Gartner):** A data fabric is a flexible, resilient integration of data sources across platforms and business users, making data available everywhere it's needed—regardless of where it resides. It uses continuous analytics over existing metadata assets to discover patterns in data use and reuse, suggesting what data integrations are needed, and automating data pipelines dynamically.

**The Key Differentiator:** A data fabric doesn't just connect data—it has an intelligence layer (using metadata analytics) that learns how data is used and proactively suggests and automates integrations. This is distinct from traditional data integration which is manually configured and static.

**Adjacent Concepts:**
- **Data Warehouse / Data Lake**: Specific architectural patterns for storing and analyzing data—a data fabric connects these and other sources rather than replacing them
- **Data Mesh**: Competing architectural philosophy—data mesh is federated and domain-owned; data fabric is centralized-intelligence with federated data. They're often complementary rather than mutually exclusive.
- **ETL/ELT pipelines**: Traditional data integration patterns—data fabric automates and intelligently manages these
- **Master Data Management (MDM)**: Governing definitions and quality of critical business entities—integrates with data fabric
- **Data Catalog**: Inventory and documentation of data assets—a component within data fabric
- **iPaaS (Integration Platform as a Service)**: Cloud-based integration middleware—data fabric is broader in scope

---

### 2. Context and Drivers

**The Data Silo Problem:**
Gartner framed data fabric as addressing the explosion of data and application silos over the previous decade. By 2021-2022:
- Average large enterprise had 900+ cloud applications
- Data lived in hundreds of separate systems (SaaS, on-premises, multi-cloud)
- Data engineering teams couldn't keep up with integration requests
- The result: 80% of data analysts' time spent on data preparation/access rather than analysis

**The Staffing Paradox:**
Data silo count grew while D&A (Data and Analytics) team sizes stayed flat or shrank relative to demand. Data fabric was positioned as a "force multiplier"—enabling smaller teams to manage larger data estates through automation and intelligence.

**Gartner Claim:** Data fabric can cut data management efforts by up to 70% and accelerate time-to-value by 40%.

---

### 3. Foundational Research Findings

#### 3.1 Data Fabric Architecture

A complete data fabric has several architectural layers:

**1. Data Connectivity Layer:**
Connects to sources—databases, APIs, files, streaming data, SaaS applications. Uses connectors (pre-built) and APIs (custom).

**2. Metadata Management Layer:**
Captures technical metadata (schemas, lineage, data types), business metadata (definitions, ownership, policies), and operational metadata (usage patterns, quality metrics). The intelligence engine operates on this metadata.

**3. Data Governance Layer:**
Policy enforcement, data quality rules, access control, privacy compliance. Metadata-driven governance means rules are applied consistently across all connected sources.

**4. Data Integration Intelligence Layer:**
The "intelligent" part—ML models that analyze metadata to:
- Identify semantically similar data across sources
- Recommend new integration opportunities
- Automate pipeline creation and maintenance
- Detect data quality issues before they propagate

**5. Data Access Layer:**
APIs, SQL interfaces, semantic layers enabling consumers to access data without knowing its physical location.

#### 3.2 Market Landscape

**Enterprise Vendors:**
- **IBM**: IBM Cloud Pak for Data (comprehensive data fabric platform)
- **Informatica**: IDMC (Intelligent Data Management Cloud)—strongest MDM + fabric integration
- **Talend**: Talend Data Fabric (acquired by Qlik 2023)
- **Denodo**: Pure-play data virtualization (core fabric component)
- **InterSystems**: IRIS Data Platform with fabric capabilities
- **SAP**: SAP Datasphere (formerly SAP Data Warehouse Cloud)

**Cloud Provider Versions:**
- **Google Cloud**: Dataplex (data fabric for BigQuery ecosystem)
- **AWS**: AWS Glue + Lake Formation as fabric components (not fully integrated)
- **Microsoft**: Microsoft Fabric (2023)—most complete cloud-native data fabric offering

**Forrester Wave Recognition:** Talend, Informatica, TIBCO, IBM as Leaders in Enterprise Data Fabric (Q2 2022).

#### 3.3 Real-World Applications

**Financial Services (Data Governance at Scale):**
A global bank managing 500+ data systems needs unified governance—who can see which customer data, under what regulatory framework. Data fabric with unified policy layer enables this without duplicating data governance tooling across each system.

**Healthcare (Data Interoperability):**
HL7 FHIR (Fast Healthcare Interoperability Resources) mandates are driving healthcare data fabric adoption. Hospital networks connecting EHR, claims, lab, and pharmacy data through a fabric for unified patient views.

**Retail (Supply Chain Intelligence):**
Retailers connecting supplier data, inventory systems, demand signals, and logistics platforms through data fabric to enable real-time supply chain optimization—especially critical post-pandemic supply chain disruptions.

#### 3.4 Data Mesh vs. Data Fabric Debate

This debate was significant 2021-2023. Clarification:

**Data Mesh** (Zhamak Dehghani, 2019):
- Federated architecture—each domain owns and serves its own data as a product
- Organizational philosophy focused on decentralization
- Requires strong platform and governance infrastructure

**Data Fabric:**
- Centralized intelligence layer spanning all data sources
- Technology architecture with automation and ML
- Compatible with data mesh—you can use data fabric infrastructure to implement data mesh principles

Most enterprises implementing one benefit from elements of the other. The debate produced more heat than practical guidance.

---

### 4. Value Proposition

1. **Faster data access**: Analysts and applications get data faster through automated integration
2. **Better data quality**: Governance layer catches quality issues consistently
3. **Reduced integration maintenance**: Intelligent automation reduces manual pipeline maintenance
4. **Governance at scale**: Policy-driven access control across hundreds of data sources
5. **AI/ML enablement**: Clean, accessible data is a prerequisite for AI programs

---

## Round 2: Deep-Dive — Microsoft Fabric as the Practical Case

### Research Question

**Most relevant development for enterprises:** Microsoft Fabric (2023) represents the most accessible enterprise data fabric offering. What does it include, and how does it compare to the established enterprise vendors?

### Deep Findings

#### Microsoft Fabric (GA: November 2023)

Microsoft Fabric is a comprehensive analytics platform that integrates:
- **OneLake**: A unified data lake (like S3/ADLS, but integrated) as the single data store
- **Data Factory**: ETL/ELT pipelines
- **Synapse Analytics**: SQL analytics
- **Synapse Data Engineering**: Spark-based processing
- **Data Science**: ML model development
- **Real-Time Analytics**: KQL-based streaming analytics
- **Power BI**: Business intelligence (the end-user layer)
- **Data Activator**: Automated business alerts from data

**Key Advantage:** Everything uses OneLake storage in a unified compute—no data copying between services. This solves the "data silos between your data tools" problem that traditional cloud data stacks create.

**Pricing:** Capacity-based (F SKUs) rather than per-service—potentially simpler cost model for enterprises already in Microsoft ecosystem.

**Adoption:** Reached 20,000+ tenants in first year (2024)—rapid adoption driven by Microsoft 365 integration.

**Limitations:**
- Azure-only (no multi-cloud)
- New product; maturity gaps vs. Informatica or IBM
- Fabric Copilot (AI) still developing

#### Established Enterprise Fabric vs. Microsoft Fabric

| Criterion | IBM/Informatica/Talend | Microsoft Fabric |
|-----------|----------------------|-----------------|
| Maturity | High | Medium (young product) |
| Multi-cloud | Yes | Azure-only |
| Governance depth | Excellent | Good |
| Total cost | High | Potentially lower for M365 customers |
| AI integration | Growing | Deep (Copilot native) |
| Implementation complexity | High | Medium |

### Round 2 Conclusion

Data fabric is maturing from concept to product category. Microsoft Fabric's 2023 launch democratized access for Microsoft-ecosystem enterprises. For organizations starting their data fabric journey, Microsoft Fabric is the fastest path to value if they're Azure-invested. For multi-cloud or complex governance requirements, established vendors (Informatica, IBM) remain the stronger choice. The most important success factor remains the same regardless of platform: clear data product ownership and consistent data governance culture.

---

## Sources

1. Gartner 2022 Strategic Technology Trends
2. Forrester Wave: Enterprise Data Fabric Q2 2022
3. Microsoft Fabric documentation and blog (2023)
4. IBM Cloud Pak for Data documentation
5. Informatica IDMC product information
6. Gartner: Data fabric can cut management efforts 70%, accelerate time-to-value 40%
7. Network Computing: "Top Data Fabric Trends for Enterprises in 2022 and Beyond"

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~1,100 words*
