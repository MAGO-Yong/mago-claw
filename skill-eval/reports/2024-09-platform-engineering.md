# Platform Engineering — 2024 Edition

**Year:** 2024 (also 2023)
**Topic Code:** 2024-09
**Research Date:** 2026-03-22

---

## Round 1: Overview

Platform Engineering appeared in both 2023 and 2024 Gartner lists. For foundational treatment see `2023-05-platform-engineering.md`. This report covers 2024-specific evolution.

**2024 Context:** By October 2023, Platform Engineering had moved from "innovative concept" to "mainstream practice." Gartner's 2024 inclusion reflected continued urgency—not enough organizations had implemented it yet, and the AI-era added new dimensions.

**New 2024 Dimensions:**
1. **GenAI in platform engineering tools**: AI-assisted infrastructure provisioning, AI-powered developer portals
2. **Developer portals as AI hubs**: Internal AI tool governance through the IDP
3. **Platform engineering for AI/ML**: MLOps infrastructure as a platform engineering domain

---

### 2. 2024 Market Developments

#### 2.1 Backstage Ecosystem Explosion

Backstage went from "Spotify's tool everyone is curious about" to "the de facto standard":
- CNCF graduation (November 2022): Backstage became a CNCF graduated project
- 1,000+ company adopters by end 2023 including Netflix, Expedia, Ikea, LinkedIn
- 200+ open-source plugins available
- "Backstage-as-a-Service" commercial offerings launched: Roadie, Frontside

**New Backstage Capabilities:**
- Backstage AI: AI-powered search and chatbot interface to service catalog
- Software catalog integration with cost data (cloud spend per service)
- Permission framework: Enterprise-grade RBAC for plugin access control

#### 2.2 Platform Engineering for AI/ML

A new dimension emerged: AI/ML workloads need their own platform engineering. The complexity of MLOps (data pipelines, training infrastructure, model serving, monitoring) mirrors the complexity of microservices—the same solution applies.

**AI Platform Engineering components:**
- **Feature stores**: Feast, Tecton—centralized feature management as platform service
- **Model registry**: MLflow, Amazon SageMaker Model Registry—track model artifacts and metadata
- **Training orchestration**: Kubeflow, Apache Airflow—manage training pipelines
- **Model serving**: Seldon, KServe, Triton—standardized model deployment
- **ML monitoring**: Evidently, Arize—drift detection as platform service

Companies like DoorDash, Doordash, Spotify, and LinkedIn published their AI platform engineering infrastructure—demonstrating this pattern at scale.

#### 2.3 Platform Engineering and GenAI

GenAI tools are becoming platform services:
- Deploy LLM APIs (OpenAI, Anthropic, or self-hosted) as internal platform services
- API gateway managing model routing, rate limiting, cost tracking
- Prompt template library maintained as platform artifact
- Model evaluation infrastructure shared across teams
- Cost allocation to teams consuming LLM services

Shopify, Netflix, and Airbnb have all published on their internal AI platform infrastructure—treating GenAI as a platform-provided capability rather than individual team infrastructure.

#### 2.4 Gartner 2024 Prediction Evolution

"By 2026, 80% of large software engineering organizations will establish platform engineering teams."

**Progress assessment (October 2023 baseline):**
- CNCF: 52% of organizations had a platform team or dedicated platform function
- Thoughtworks Technology Radar: Platform Engineering moved from "Trial" to "Adopt"
- Annual State of DevOps: Platform engineering teams correlated with elite DevOps performers

The 80% target by 2026 appeared achievable but not certain—progress was concentrated in tech companies; traditional enterprises lagged.

#### 2.5 Developer Portals as AI Governance Hubs

An emerging 2024 pattern: internal developer portals (IDPs) becoming the governance layer for AI tools.

**What this looks like:**
- All approved AI tools catalogued in Backstage service catalog
- Teams can discover which AI tools are approved and how to access them
- AI tool documentation, usage examples, cost allocation in unified portal
- Model evaluation results published in portal
- Compliance attestation for AI tool usage tracked through portal

This positions platform engineering as directly relevant to the "AI governance" challenge—IDP becomes the single pane of glass for enterprise AI infrastructure.

---

### 3. Value Proposition (2024 Update)

Original platform engineering value: Developer velocity, standardization, reduced cognitive load.

**Added in 2024:**
- **AI/ML infrastructure standardization**: Consistent, reproducible AI development pipeline
- **GenAI governance**: IDP as governance hub for approved AI tools
- **Cost visibility**: Cloud cost per service, AI API cost per team
- **Compliance**: Policy enforcement automated through platform (security scanning, license checks)

---

## Round 2: Deep-Dive — GenAI Integration in Developer Platforms

### Research Question

**Most significant 2024 development:** How is GenAI being integrated into developer platforms themselves (not just as services they provide)?

### Deep Findings

#### GitHub Copilot Enterprise vs. IDE-Level Integration

The developer platform itself is becoming AI-augmented:

**GitHub Copilot Enterprise (launched March 2024):**
- Code completion and chat available throughout GitHub (not just IDE)
- Codebase-aware: Understands your organization's repositories, not just public GitHub
- Pull request summaries: AI-generated PR descriptions and review notes
- Discussion summaries: Summarizing long issue threads
- Knowledge base: Answer questions about your codebase from natural language

**GitLab Duo:**
GitLab's equivalent to GitHub Copilot; integrated throughout GitLab platform:
- Code suggestions in IDE
- Root cause analysis for failed CI/CD pipelines (AI explains why the build broke)
- Vulnerability explanation (security scanner findings explained in plain language)
- Documentation generation from code

**The Platform-AI Integration Pattern:**
AI is embedded at every platform touchpoint:
- Development: Code completion (Copilot, Cursor)
- Testing: AI test generation (Testim, Diffblue)
- Code review: AI review assistant (GitHub Copilot, CodeRabbit)
- Documentation: AI doc generation
- Deployment: AI-powered release decisions (detect anomalies in deployment metrics)
- Operations: AIOps for incident detection and resolution

**Consequence for Platform Engineering:**
Platform teams are now responsible for selecting, deploying, and governing these AI-augmented platform tools. This is a new responsibility that didn't exist in 2022.

#### Measuring Platform Engineering + AI Impact

DORA metrics remain the standard, but AI augmentation adds new measures:
- AI-assisted deployments vs. total deployments (adoption)
- Developer satisfaction with AI tools (NPS)
- Time saved per developer per week from AI assistance
- AI code acceptance rate (quality signal)
- AI cost per developer per month (economic efficiency)

Shopify's platform engineering team published 2024: AI coding tools reduced code review time by 35%; pull request velocity increased 20%.

### Round 2 Conclusion

Platform engineering in 2024 has two new mandates: (1) build the AI/ML infrastructure platform that data science teams need, and (2) govern the GenAI developer tools that software engineers are using. Organizations that treat these as separate concerns (MLOps separate from DevOps platform) will have fragmented infrastructure. The winning pattern is unified platform engineering covering software development AND AI/ML development workflows, with a single developer portal as the governance hub for all.

---

## Sources

1. Gartner 2024 Strategic Technology Trends
2. CNCF Backstage graduation (November 2022)
3. CNCF Annual Survey 2023 (platform engineering data)
4. GitHub Copilot Enterprise launch (March 2024)
5. GitLab Duo documentation
6. Shopify engineering blog: AI platform tools impact (2024)
7. DORA State of DevOps 2023

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~900 words*
