# Evaluation: 2021-03 Privacy-Enhancing Computation (PEC)

**Evaluator Perspective:** First-time reader, non-expert in cryptography
**Evaluation Date:** 2026-03-22

---

## Scoring

| Dimension | Score | Notes |
|-----------|-------|-------|
| Readability | 8 | Technical topic handled well; the six technique list is clear; maturity table is excellent |
| Content Richness | 9 | Strong real-world examples (NHS, Apple, COVID contact tracing); good technique breakdown |
| Logic & Coherence | 9 | Well-organized; maturity-by-technique table is genuinely useful; R2 adoption tiers are logical |
| Report Quality | 8 | Professional; good structure; R2 is well-focused and actionable |

**Overall Average: 8.5 / 10**

---

## What Was Done Well

1. **Six technique taxonomy with clear explanations**: Each PEC technique has a concise definition with real-world application—non-experts can follow this
2. **Maturity table**: The Technique/Maturity/Cost/Use Case table is excellent—visual, scannable, actionable
3. **Real-world examples are strong**: NHS federated learning, Apple differential privacy, COVID contact tracing—these are concrete, verifiable cases
4. **Honest about limitations**: The GDPR/anonymization uncertainty is correctly flagged as unresolved
5. **Adoption tiers in R2**: Tier 1/2/3 framework helps enterprises sequence investments practically

## What Was Done Poorly

1. **Performance improvement numbers are imprecise**: "100-1000x improvement" is a wide range; should cite specific benchmarks if available
2. **HE performance claims lack sourcing**: "1,000x-10,000x slower" is cited without a source
3. **No failure cases**: No example of a PEC implementation that failed or underperformed—would add balance
4. **ING Bank SMPC reference**: Described as a "pilot"—unclear if it was published research or inferred; should be flagged as unverified

## Improvement Suggestions

1. Do a web search for 2024/2025 PEC market adoption statistics to quantify enterprise uptake
2. Add a "tool landscape" section—which open-source and commercial tools should teams evaluate first?
3. Add a "cost of wrong implementation" example—what goes wrong when PEC is implemented incorrectly?
4. Round 2 could benefit from one interview-quality case study with measurable outcomes

---

## Reader Experience Notes

This is the strongest technical report so far. The maturity table alone justifies reading. A CTO or privacy engineer would find genuine value here. The adoption tier framework in Round 2 provides clear decision-making guidance. The key limitation is some imprecision in technical claims that experts would question.

**Would share with colleagues:** Yes, especially with data engineering or privacy teams
**Key takeaway clarity:** Clear (Start with differential privacy and federated learning; HE is still years away)
**Confidence in conclusions:** High
