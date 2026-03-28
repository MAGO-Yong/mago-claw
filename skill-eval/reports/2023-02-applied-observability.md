# Applied Observability — Research Report

**Year:** 2023 (announced October 17, 2022)
**Topic Code:** 2023-02
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

### 1. Topic Alignment

**Definition (Gartner):** Applied observability uses data artifacts—logs, traces, API calls, dwell time, downloads, file transfers—as they're captured at digital touchpoints to make decisions. It goes beyond monitoring (watching what a system does) to using those observations to inform business and operational decisions in near-real-time. The focus is on exploiting data artifacts for competitive advantage.

**Key Insight:** Every digital interaction leaves traces. Applied observability is the practice of systematically capturing, analyzing, and acting on those traces—not just for IT operations but for business decision-making.

**Three Layers of Applied Observability:**
1. **System observability**: Traditional IT monitoring—metrics, logs, traces for infrastructure and applications
2. **User/business observability**: Tracking user behavior signals for product and business decisions
3. **Applied analytics**: Converting observation into decision and action at near-real-time speeds

**Distinction from Traditional Analytics:**
- Traditional analytics: Look at historical data to understand what happened (retrospective)
- Applied observability: Observe real-time signals and act immediately (prospective)
- Example: Analytics tells you customers abandoned checkout last week; observability tells you customers are abandoning checkout RIGHT NOW because of a 3-second latency spike → immediate remediation

**Adjacent Concepts:**
- **Digital Immune System** (also 2023 trend): System observability is a DIS component; applied observability extends to business decisions
- **AIOps**: AI applied to IT operations data; observability provides the data AIOps needs
- **Digital Experience Monitoring (DEM)**: Employee-facing observability; subset of applied observability
- **Product Analytics**: User behavior data for product decisions; part of applied observability
- **Data Fabric** (2022): Infrastructure that enables applied observability at scale

---

### 2. Context and Drivers

**Why 2023?** The confluence of three maturing capabilities:
1. **Instrumentation maturity**: OpenTelemetry standardized how systems emit telemetry data; widespread adoption
2. **AI/ML processing**: Large volumes of observability data processable with ML to find signal in noise
3. **Real-time processing**: Event streaming (Kafka, Flink) enabled near-real-time analysis of observability data

Gartner's framing: "Applied observability is the most powerful source of data-driven decision-making" because it captures what people actually DO (not what they say they do in surveys), and it captures it in real-time.

---

### 3. Foundational Research Findings

#### 3.1 Observability Market

- **IT observability market**: $2.3 billion (2022), growing ~20% annually
- Key platforms: Datadog ($1.7B revenue in 2022), Dynatrace, New Relic, Grafana Labs (open-source, huge community)
- **Product analytics market**: Amplitude, Mixpanel, Heap—user behavior observability
- **Log management**: Splunk, Elastic (ELK Stack), Sumo Logic

**OpenTelemetry Significance:**
Before OpenTelemetry, each observability vendor had proprietary instrumentation SDKs. OpenTelemetry created a vendor-neutral standard for emitting metrics, logs, and traces—organizations can instrument once and send to any backend. This drove significant adoption acceleration 2021-2023.

#### 3.2 Applied Observability Use Cases

**1. E-Commerce: Real-Time Conversion Optimization**
Amazon monitors thousands of observability signals in real-time during high-traffic events (Prime Day, Black Friday). If a checkout step latency increases by 50ms, automatic scaling triggers. If an error rate on payment processing spikes, degraded mode (alternative payment flow) activates. All of this is applied observability—observing and acting in real-time.

**2. Financial Services: Fraud Signal Detection**
Stripe's Radar fraud detection system observes transaction signals in real-time. Not just the transaction data but behavioral signals: typing cadence, mouse movement patterns, device fingerprints, network characteristics. These observability signals feed ML models that score transactions in <100ms.

**3. Manufacturing: Predictive Maintenance**
Siemens' industrial IoT platform observes machine sensor data (temperature, vibration, power draw). Applied observability: when sensor patterns match historical precursors to failure, maintenance is triggered proactively. Claimed outcome: 30-50% reduction in unplanned downtime.

**4. Healthcare: Patient Monitoring**
Hospital patient monitoring systems observe vital signs continuously. Applied observability: detect deterioration patterns before clinical symptoms appear. Epic's Deterioration Index uses this principle—watching dozens of vital sign trends to predict sepsis before clinical obvious symptoms appear.

**5. Digital Product Optimization:**
Airbnb uses applied observability to watch user sessions in real-time. When users are "rage clicking" (clicking the same element repeatedly, indicating frustration), engineers see this in dashboards and can identify product issues in hours rather than days waiting for support tickets.

#### 3.3 Technical Architecture

**Data Ingestion Layer:**
- OpenTelemetry SDK (instrumentation standard)
- eBPF (extended Berkeley Packet Filter): Low-overhead kernel-level observation without code changes
- Distributed tracing: Linking events across microservices into coherent user journeys

**Stream Processing Layer:**
- Apache Kafka: Event streaming backbone
- Apache Flink, Spark Streaming: Real-time analytics on streams
- KSQL (Kafka SQL): SQL-like queries on real-time data streams

**Storage and Analysis:**
- Time-series databases (Prometheus, InfluxDB, Timescale) for metrics
- Column-store databases (ClickHouse, BigQuery, Redshift) for analytics
- Search engines (Elasticsearch, OpenSearch) for log analysis

**Action Layer:**
- Automated alerting (PagerDuty, OpsGenie)
- Workflow automation (triggered by observability events)
- ML-powered anomaly detection and recommendation

#### 3.4 Maturity Assessment

**System observability**: High maturity—standardized tooling, widespread enterprise adoption
**User/behavioral observability**: High for digital products; lower for enterprise applications
**Real-time business observability**: Early majority—the "applied" part is where most enterprises are still developing capability
**Cross-system correlation**: Medium—linking system behavior to business outcomes is harder

---

### 4. Value Proposition

1. **Earlier problem detection**: Hours or minutes vs. days waiting for support tickets
2. **Faster recovery**: Real-time observation enables real-time remediation
3. **Better decisions**: Decisions based on actual behavior vs. sampled surveys
4. **Competitive intelligence**: Observing customer behavior patterns reveals competitive opportunities
5. **Developer efficiency**: Faster debugging and root cause analysis

---

## Round 2: Deep-Dive — eBPF as the Next Observability Frontier

### Research Question

**Most technically interesting emerging development:** eBPF (extended Berkeley Packet Filter) is enabling a new approach to observability that doesn't require application code changes. What is it and why does it matter?

### Deep Findings

#### What eBPF Is

eBPF allows custom programs to run in the Linux kernel's execution context—observing any system call, network event, or file system operation without modifying the observed application. It's like having an X-ray machine for software: you can see exactly what's happening inside any process.

**Before eBPF:**
- Observability required instrumenting application code (adding telemetry libraries)
- This meant: each language had different instrumentation; old/legacy apps couldn't be instrumented; instrumentation added overhead
- Result: Large portions of enterprise application estates had no observability

**With eBPF:**
- Kernel-level observation of any process without code changes
- Zero-overhead for uninstrumented legacy applications
- Complete visibility into network traffic, system calls, file operations, CPU usage per process

**Key eBPF-based Observability Products:**
- **Cilium**: Network observability and security using eBPF (CNCF project; 100+ enterprise adopters)
- **Pixie**: Open-source Kubernetes observability using eBPF (acquired by New Relic)
- **Parca**: Continuous profiling using eBPF
- **Grafana Beyla**: Auto-instrumentation using eBPF—zero-code approach to application observability

#### Enterprise Value

eBPF-based observability offers:
1. **Legacy application coverage**: Observe applications that can't be modified (SAP, Oracle ERP, older Java apps)
2. **Security observability**: Detect malicious process behavior at kernel level (runtime security)
3. **Network troubleshooting**: Complete visibility into container-to-container and external traffic
4. **Performance profiling**: Identify CPU bottlenecks at function level without instrumentation overhead

**Adoption trajectory:**
- Cilium: 30,000+ GitHub stars; adopted by Google, Apple, Meta, Goldman Sachs for networking
- Tetragon (Isovalent): Runtime security enforcement using eBPF
- Meta, Netflix, Cloudflare, Uber: All have engineering blog posts on eBPF production use

### Round 2 Conclusion

Applied observability is becoming comprehensive through eBPF—eliminating the coverage gap in legacy and uninstrumented systems that previously left blind spots in enterprise observability. Organizations should add eBPF-based tools (especially Cilium for Kubernetes networking and Grafana Beyla for auto-instrumentation) to their observability stack to achieve complete coverage. The "applied" dimension—using observability data for real-time business decisions—requires this complete coverage; partial observability leads to partial decisions.

---

## Sources

1. Gartner 2023 Strategic Technology Trends
2. Datadog Annual Report 2022 ($1.7B revenue)
3. OpenTelemetry documentation (opentelemetry.io)
4. Brendan Gregg's eBPF documentation and research (brendangregg.com)
5. Cilium project documentation and case studies (cilium.io)
6. Stripe Engineering Blog: Fraud detection architecture
7. Siemens MindSphere/IoT predictive maintenance case studies
8. Epic Systems Deterioration Index research papers

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~1,200 words*
