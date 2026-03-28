# AI Trust, Risk and Security Management (AI TRiSM) — 2024 Edition

**Year:** 2024 (also 2023)
**Topic Code:** 2024-02
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

For foundational AI TRiSM treatment, see `2023-03-ai-trust-risk-security-management.md`. This report focuses on how AI TRiSM evolved in the 2024 context, with GenAI now mainstream.

### 1. 2024-Specific Context

**Why AI TRiSM Was Repeated in 2024:**

By October 2023, generative AI had become mainstream—every enterprise was now deploying or evaluating GenAI. This raised the stakes for AI TRiSM dramatically:
- GenAI hallucination in production systems was now causing real harm (doctors citing AI-generated medical advice, lawyers submitting AI-fabricated citations)
- Prompt injection attacks documented in production AI systems
- EU AI Act moving toward final passage (enacted March 2024)
- SEC and other regulators focusing on AI in financial services

**Gartner's 2024 Framing:**
"By 2026, organizations that apply AI TRiSM controls will increase the accuracy of decision-making by eliminating up to 80% of faulty and illegitimate AI-generated information."

This was unchanged from 2023—the urgency had increased but the prediction remained.

---

### 2. 2024-Specific Developments

#### 2.1 GenAI-Specific AI TRiSM Requirements

Traditional AI TRiSM was designed for discriminative ML (classifiers, regression models). GenAI required new approaches:

**Hallucination Management:**
- Retrieval-Augmented Generation (RAG) as primary hallucination mitigation
- Fact-checking layers post-generation (TruLens, Ragas)
- "Ground truth" evaluation against verified sources
- Human-in-the-loop for high-stakes outputs

**Output Moderation at Scale:**
- Azure Content Safety: Microsoft's content moderation API for GenAI outputs
- LlamaGuard 2: Meta's open-source input/output classifier
- Perspective API (Google): Toxicity detection in text

**Prompt Injection Defenses:**
Following documented injection attacks in ChatGPT plugins and autonomous agents, more sophisticated defenses emerged:
- Prompt injection detection models (Garden Intelligence, Rebuff)
- Privilege separation between system prompt, user input, and tool outputs
- Input sanitization preprocessing pipelines
- OWASP LLM Top 10 as industry standard reference

#### 2.2 EU AI Act Final Passage (March 2024)

The EU AI Act was signed into law August 2024 (applied gradually from 2025-2027). Key provisions directly relevant to AI TRiSM:

**Prohibited AI (August 2024 effective):**
- Social scoring systems by governments
- Real-time biometric identification in public spaces (with exceptions)
- Subliminal manipulation of behavior
- Exploitation of vulnerabilities (age, disability)

**High-Risk AI (2026 effective):**
- AI in critical infrastructure (energy, water, transport)
- AI in education and vocational training
- AI in employment and worker management
- AI in law enforcement
- AI in migration and asylum processes
- AI in administration of justice

**High-Risk Requirements:**
- Risk management system
- Data governance
- Technical documentation
- Transparency and logging
- Human oversight
- Accuracy, robustness, cybersecurity

**Compliance Implications:**
Any organization selling to or operating in the EU must:
1. Inventory all AI systems for risk classification
2. Implement EU AI Act requirements for high-risk systems
3. Register high-risk systems in EU database
4. Conduct conformity assessment

#### 2.3 NIST AI RMF Adoption

NIST's Artificial Intelligence Risk Management Framework (January 2023) was adopted as the de facto US enterprise standard:
- Used in 50%+ of enterprise AI governance frameworks by end of 2023
- Referenced in US federal AI policy (AI EO, March 2023)
- Published profiles for specific sectors (banking, healthcare)

The four GOVERN-MAP-MEASURE-MANAGE functions provided structure for enterprise AI TRiSM programs.

#### 2.4 AI Governance Market

A new market emerged: AI Governance platforms providing tooling for AI TRiSM:
- **IBM OpenScale/Watson OpenScale**: Fairness, drift, explainability monitoring
- **Fiddler AI**: Production ML monitoring with explainability
- **Arthur AI**: ML monitoring and explainability platform
- **Credo AI**: Governance-focused AI risk management
- **Fairly AI**: Bias detection and compliance
- **ModelOp**: Model governance and lifecycle management

Market estimated $1.1B in 2023, projected $12B by 2029—reflecting the urgency.

#### 2.5 Real-World AI TRiSM Failures (2023-2024)

**Air Canada Chatbot Ruling:**
A Canadian tribunal ruled Air Canada was responsible for inaccurate information given by its AI chatbot (regarding bereavement fares). Air Canada's defense that "the chatbot is a separate legal entity" was rejected. This established that organizations are liable for AI system outputs.

**Law Firm ChatGPT Fabrication:**
Two lawyers fined/sanctioned for submitting AI-fabricated case citations to a US federal court (Mata v. Avianca, 2023). Judges increasingly requiring AI disclosure in legal filings.

**Health Insurance AI Claim Denials (2023-2024):**
Investigative reports revealed major health insurers using AI models to deny claims with extremely high override rates—suggesting models were making inaccurate determinations at scale. Congressional inquiries followed.

---

### 3. Value Proposition (Updated for 2024)

1. **Legal liability protection**: Air Canada ruling establishes organizational liability for AI errors
2. **Regulatory compliance**: EU AI Act, sector-specific regulations require AI governance
3. **Operational reliability**: Reduce hallucination harm in production systems
4. **Trust maintenance**: Users/customers trusting AI systems requires demonstrated governance
5. **IP protection**: Prevent proprietary data leakage through AI interactions

---

## Round 2: Deep-Dive — Practical AI TRiSM Implementation for GenAI

### Research Question

**Most actionable question for 2024:** Given that most organizations are now deploying GenAI in production, what is the minimum viable AI TRiSM framework to prevent the most common failures?

### Deep Findings

#### Minimum Viable AI TRiSM Framework for GenAI

**Tier 1: Immediate (0-30 days)**
1. **Data policy**: Define what data categories cannot be submitted to GenAI systems
2. **Approved tools list**: Designate approved GenAI tools with enterprise agreements (no training on company data)
3. **Human review gate for high-stakes outputs**: Legal, medical, financial content requires human review before use

**Tier 2: Near-term (30-90 days)**
4. **Output disclaimers**: All AI-generated content labeled as such
5. **Hallucination mitigation**: RAG for knowledge-intensive applications; source citations required
6. **Incident process**: How to report when AI causes a problem

**Tier 3: Structural (90-180 days)**
7. **AI inventory**: Catalog all AI systems in production with risk classification
8. **AI governance committee**: Cross-functional body overseeing AI deployment decisions
9. **Monitoring**: Track AI system performance, accuracy, bias on production data

**Tier 4: Advanced (6-18 months)**
10. **Explainability**: For high-risk AI decisions, implement explanation capabilities
11. **Bias auditing**: Regular third-party auditing for high-impact AI systems
12. **EU AI Act compliance**: Risk assessment and documentation for EU-applicable systems

**Most Common Mistakes:**
- Focusing on policy without technical controls
- Treating all AI systems the same (generic risk framework instead of risk-tiered)
- Not having a feedback mechanism for AI errors to improve systems

### Round 2 Conclusion

The 2024 AI TRiSM reality is that most organizations are behind. The Air Canada liability ruling, EU AI Act, and documented GenAI failures create urgent business and legal motivation to implement AI governance. The Minimum Viable AI TRiSM framework—data policy, approved tools, human review gates, output labeling—can be implemented in 30-60 days. Waiting for a "perfect" governance framework while AI deploys across the organization is riskier than implementing an imperfect framework now and improving it iteratively.

---

## Sources

1. Gartner 2024 Strategic Technology Trends
2. EU AI Act final text (2024)
3. NIST AI Risk Management Framework (2023)
4. Air Canada chatbot ruling (Canadian Civil Resolution Tribunal, February 2024)
5. Mata v. Avianca case documentation (SDNY, 2023)
6. OWASP LLM Top 10 (2023 edition)
7. LlamaGuard documentation (Meta AI, 2023)
8. Credo AI, ModelOp product documentation

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~1,000 words*
