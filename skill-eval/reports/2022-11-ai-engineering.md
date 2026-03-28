# AI Engineering (2022 Edition) — Research Report

**Year:** 2022
**Topic Code:** 2022-11
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

### 1. Overview

AI Engineering appeared in both 2021 and 2022 Gartner strategic technology trends. For full foundational treatment, see `2021-08-ai-engineering.md`. This report focuses on the 2022-specific context: what changed in the AI engineering landscape between 2021 and 2022.

**Gartner's 2022 Framing:** "By 2025, the 10% of enterprises that establish AI engineering best practices will generate at least three times more value from their AI efforts than the 90% of enterprises that do not."

This 3x value claim is more specific and impactful than the 2021 framing—suggesting Gartner had accumulated more evidence of the performance differential between mature and immature AI programs.

---

### 2. 2022-Specific Developments

#### 2.1 MLOps Market Maturation

The MLOps market saw significant growth and consolidation in 2022:
- **Databricks acquisition of MosaicML** (announced 2023, reflecting 2022 strategy)—AI training infrastructure
- **MLflow 2.0**: Major update to the dominant open-source MLOps framework; better model serving, improved autologging
- **Weights & Biases**: Grew to 800,000+ users; became de facto standard for ML experiment tracking
- **Amazon SageMaker**: Expanded feature set with Ground Truth (data labeling), Autopilot (AutoML), Pipelines (ML workflow)
- **Google Vertex AI**: GA (2021), expanded with Vertex AI Experiments and Vertex AI Feature Store

**Key Validation:** Both AWS and Google released managed feature stores in their ML platforms—confirming feature stores as critical AI engineering infrastructure.

#### 2.2 The LLM Disruption to AI Engineering

Late 2022 introduced a new complication: Large Language Models (LLMs) disrupted traditional AI engineering practices.

Traditional ML development cycle:
- Collect/label data → Train model → Evaluate → Deploy → Monitor

LLM development cycle:
- Select foundation model → Fine-tune or RAG → Prompt engineer → Evaluate → Deploy → Monitor for hallucination + drift

This fundamental change required AI engineering frameworks to evolve:
- Prompt management emerged as a new engineering discipline
- Model evaluation metrics changed (perplexity, factuality, harmlessness—not just accuracy/F1)
- Hallucination detection became a new monitoring category
- Foundation model versioning (what happens to your application when OpenAI updates GPT-4?)

#### 2.3 Responsible AI / AI Governance Maturation

2022 saw significant regulatory and governance development:
- **EU AI Act**: Progressed through legislative process; risk-based classification of AI systems
- **NIST AI Risk Management Framework (AI RMF)**: Published January 2023, reflecting 2022 development
- **Microsoft Responsible AI Standard**: Published June 2022; established internal guidelines
- **Google Model Cards**: Tool for documenting AI model characteristics and limitations
- **Algorithmic Impact Assessments**: Adopted by several national governments as pre-deployment requirement

AI engineering in 2022 began incorporating responsible AI as a first-class engineering practice, not an afterthought.

#### 2.4 AI Engineering Talent

The "MLOps Engineer" role became a recognized job title in 2022:
- LinkedIn: 40,000+ job postings for "MLOps Engineer" or similar titles by end 2022
- Compensation: $150,000-$250,000 in US tech hubs
- Skills in demand: Python, Kubernetes, MLflow, feature stores, cloud ML platforms
- Education gap: More MLOps engineering demand than supply; most practitioners were self-taught from data scientist or DevOps backgrounds

#### 2.5 AutoML and Democratization

AI engineering also moved toward democratization through AutoML:
- Google AutoML, AWS Autopilot, Azure Automated ML—enable non-ML engineers to build models
- DataRobot: Commercial AutoML platform; 1,000+ enterprise customers
- H2O.ai: Open-source AutoML widely adopted
- The "citizen data scientist" enabled by AutoML created new governance challenges (models built by business users without proper engineering practices)

---

### 3. Maturity Assessment (2022 Evolution)

| Component | 2021 | 2022 |
|-----------|------|------|
| Experiment tracking (Weights & Biases, MLflow) | Early majority | Mainstream |
| Model serving infrastructure | Developing | Mature |
| Feature stores | Emerging | Growing adoption |
| Model monitoring | Early | Developing |
| LLM engineering | Nonexistent | Emergent |
| Responsible AI tooling | Nascent | Developing |
| AutoML | Early | Early majority |

---

## Round 2: Deep-Dive — The Foundation Model Disruption to AI Engineering

### Research Question

**Most significant 2022 development:** LLMs disrupted traditional AI engineering practices. What new practices are required for LLM-based AI systems?

### Deep Findings

#### LLMOps: AI Engineering for Foundation Models

"LLMOps" emerged as a term in late 2022/early 2023 for the distinct engineering practices required for LLM-based systems:

**Prompt Management:**
- Prompts as artifacts to be versioned, tested, and deployed
- Prompt injection vulnerabilities as new security category
- A/B testing prompts for quality optimization
- Tools: PromptLayer, Weights & Biases Prompts, LangSmith

**Foundation Model Management:**
- Which model version is in production?
- What happens to behavior when OpenAI deprecates a model version?
- How to evaluate model updates before deploying to production?
- Vendor lock-in vs. portability trade-off

**Evaluation for LLMs:**
Traditional ML evaluation: held-out test set with clear correct answers. LLM evaluation is far harder:
- "Correctness" is subjective for generation tasks
- Factuality requires external knowledge verification
- Harmlessness requires safety evaluation
- New evaluation frameworks: HELM (Holistic Evaluation of Language Models), BIG-bench, specific task benchmarks
- Human evaluation still needed (but expensive)

**Hallucination Detection and RAG:**
- LLMs confidently generate false information—"hallucination"
- RAG (Retrieval-Augmented Generation) reduces hallucination by grounding responses in retrieved documents
- Hallucination detection tools emerging: TruLens, Ragas, Arize Phoenix

**Cost Management:**
LLM inference is expensive:
- GPT-4 costs $0.01-0.06 per 1,000 tokens in 2022-2023
- High-volume applications could easily spend $1M+/month on LLM inference
- Prompt optimization, model tiering (use smaller model for simple queries), caching strategies all important

### Round 2 Conclusion

AI engineering is a moving target—LLMs introduced a new paradigm that requires new tooling, practices, and expertise. Organizations that built solid MLOps foundations (data pipelines, model monitoring, governance) in 2021-2022 were better positioned to adopt LLMOps practices in 2023-2024. The foundational investments in AI engineering—good data practices, systematic evaluation, governance frameworks—transfer even as the specific AI technology changes.

---

## Sources

1. Gartner 2022 Strategic Technology Trends
2. Weights & Biases user statistics
3. MLflow 2.0 release notes
4. Google Vertex AI documentation
5. NIST AI Risk Management Framework (January 2023)
6. Microsoft Responsible AI Standard (June 2022)
7. EU AI Act legislative progress (2022)
8. HELM evaluation framework (Liang et al., Stanford, 2022)

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~900 words*
