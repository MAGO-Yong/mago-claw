# Agentic AI — Research Report

**Year:** 2025 (announced October 21, 2024)
**Topic Code:** 2025-01
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

### 1. Topic Alignment

**Definition (Gartner):** Agentic AI refers to AI systems that can autonomously plan and execute complex multistep tasks and adaptively respond to feedback from their environment to achieve specific goals—with little or no human interaction. Unlike generative AI that responds to prompts, agentic AI takes initiative, uses tools, and orchestrates sequences of actions to complete goals.

**The Fundamental Shift:**
- **Generative AI**: Input → Output (one step; human evaluates and decides next action)
- **Agentic AI**: Goal → Plan → Execute (multiple steps; AI decides and executes autonomously)

This shift means AI moves from "assistant you talk to" to "autonomous agent that does work for you."

**Key Characteristics of Agentic AI:**
1. **Goal-directed**: Given an objective, figures out how to achieve it
2. **Multi-step reasoning**: Decomposes complex goals into sequences of actions
3. **Tool use**: Can use APIs, search engines, code execution, web browsers, other AI models
4. **Memory**: Maintains context across a session and potentially across sessions
5. **Self-correction**: Evaluates its own outputs and corrects when errors are detected
6. **Autonomy**: Operates for extended periods without human intervention

**Agent Architectures:**

*ReAct (Reasoning + Acting)*: Agent reasons about next step, takes action, observes result, reasons again. Published by Google/Princeton 2022; underpins many agent implementations.

*Plan-and-Execute*: Agent creates full plan first, then executes. Better for long-horizon tasks.

*Multi-Agent Systems*: Multiple AI agents collaborating, each with specialized roles (orchestrator + subagents).

**Adjacent Concepts:**
- **Generative AI** (2022): The capability that enables agentic AI (LLMs as the reasoning engine)
- **Hyperautomation** (2021, 2022): Rule-based automation; agentic AI is autonomous automation
- **Machine Customers** (2024): Agents as purchasing entities
- **Multiagent Systems** (2026): Evolution—multiple specialized agents collaborating
- **Autonomous Systems** (2022): Physical autonomy; agentic AI is cognitive autonomy

---

### 2. Context and Drivers

**The ChatGPT to Agent Evolution:**
ChatGPT (2022): Answer questions.
GPT-4 with function calling (2023): Could call external APIs.
GPT-4 with Assistants API (2023): Maintained state, used tools (code interpreter, retrieval).
OpenAI GPT-4o + operator system (2024): Complex autonomous task execution.
Claude 3.5 Computer Use (2024): Could control desktop/browser autonomously.
GPT-4 model with Operator (2025): Consumer-facing agent.

The progression was rapid: from chatbot to autonomous agent in under 3 years.

**Enterprise Drivers:**
1. **Cost of human labor**: Agents can do white-collar work at software cost
2. **Scale impossibility**: Some tasks (personalized outreach at scale, 24/7 monitoring) require automation
3. **Complexity increase**: Modern knowledge work is too complex for rule-based automation
4. **GenAI infrastructure**: LLM capability now sufficient for reliable agent use in constrained domains

**Gartner Prediction (2024):**
"By 2028, agentic AI will be embedded in 33% of enterprise software applications."

---

### 3. Foundational Research Findings

#### 3.1 Early Enterprise Agent Deployments (2024-2025)

**Salesforce Agentforce:**
Launched September 2024. Autonomous AI agents for sales, service, marketing, and commerce:
- Service agent: Handles customer inquiries autonomously, accessing customer data, knowledge base, policies
- Sales agent: Autonomous prospect research, outreach, meeting scheduling
- Launched with 200+ enterprise customers at announcement
- Raised Salesforce stock price 20%+ on announcement day

**Microsoft Copilot Studio Agents:**
Microsoft's platform for building enterprise AI agents:
- IT Service Management: Agent handles common IT requests autonomously (password reset, software access)
- HR agent: Answers employee questions about policies, benefits, handles routine HR tasks
- Finance agent: Assists with expense processing, invoice approval workflows
- 1,800+ Copilot Studio customers by 2024

**ServiceNow AI Agents:**
Autonomous IT service management:
- Incident resolution agent: Diagnoses and resolves common IT incidents without human
- Change management agent: Handles routine change requests
- Reducing MTTR (Mean Time to Resolution) by 20-40% in beta customers

**Google Agentspace:**
Enterprise agent platform combining Gemini models with enterprise knowledge (Google Search, Drive, Workspace, third-party apps).

#### 3.2 Consumer-Facing Agents

**OpenAI Operator (2025):**
- First general-purpose autonomous web agent for consumers
- Could complete tasks like booking restaurants, purchasing products, filling forms
- Gated release; demonstrated significant capability and risk (security concerns)

**Anthropic Claude Computer Use (2024):**
- Claude could control a computer: click, type, see screen
- The "computer use" capability is transformative—any computer task becomes automatable
- Enterprise: QA automation, data extraction from legacy systems, browser-based workflows

**Perplexity AI agents:**
- Research agents that autonomously search, synthesize, and produce structured research outputs
- Enterprise partnerships for market research and competitive intelligence

#### 3.3 Multi-Agent Systems

The frontier of agentic AI is multi-agent systems where specialized agents collaborate:

**Example: Software Development Agent Team**
- **Architect agent**: Designs system architecture given requirements
- **Developer agent**: Writes code per architecture
- **Testing agent**: Tests code, finds bugs
- **Review agent**: Reviews code quality and security
- **Deploy agent**: Manages CI/CD pipeline

Each agent specializes; orchestrator agent coordinates. Human oversight at key checkpoints.

**Industry Example:**
Cognition AI's "Devin" (2024): First "AI software engineer" claim—capable of completing coding tasks end-to-end (debugging, writing features, deploying). Demonstrated controversial but impressive capability in early 2024.

**Framework Landscape:**
- **LangGraph**: Stateful agent orchestration framework (LangChain)
- **AutoGen** (Microsoft): Multi-agent conversation framework
- **CrewAI**: Role-based agent team framework
- **OpenAI Assistants API**: Managed agent infrastructure

#### 3.4 Agentic AI Risks

**Hallucination at action scale:**
Generative AI hallucinations are text. Agentic AI hallucinations cause actions. An agent that misidentifies a situation can send a wrong email, delete files, or make a wrong purchase.

**Prompt injection (critical risk for agents):**
Agents that browse the web or read emails can receive malicious instructions embedded in content (see AI TRiSM report). Consequences are worse for agents than chatbots because agents take real-world actions.

**Scope creep:**
Agents optimizing for a goal may take actions humans didn't anticipate or authorize.

**Trust and oversight:**
How do you know what an agent did? How do you reverse a wrong action? Audit trails and reversibility are critical.

**Gartner's Guidance:**
"By 2028, at least 15% of day-to-day work decisions will be made autonomously through agentic AI. Governance must be in place before deployment."

---

### 4. Value Proposition

1. **Labor economics**: Autonomous agents working 24/7 at software costs
2. **Personalization at scale**: Each customer/employee can have an agent working for them
3. **Complex task automation**: Tasks too complex for rule-based automation become automatable
4. **Speed**: Agent completes in minutes what takes humans hours
5. **Consistency**: Agents follow processes without fatigue or shortcut-taking

---

## Round 2: Deep-Dive — Enterprise Agent Governance

### Research Question

**Most critical gap:** Enterprises deploying agentic AI need governance frameworks that didn't exist before agents. What does agent governance look like?

### Deep Findings

#### Why Agent Governance is Different

Traditional software governance: Approve the application before deployment; it does what it's programmed to do.
Agentic AI governance: The agent's behavior is emergent from the LLM + context. You cannot fully predict what it will do in all situations.

This requires:
- **Sandboxing**: Limit what systems/data an agent can access
- **Permission scoping**: Least-privilege principle applied to agent capabilities
- **Human-in-the-loop**: Checkpoints where humans must approve before agent proceeds
- **Audit logging**: Complete record of every action taken
- **Reversibility**: Can agent actions be undone if wrong?

#### Emerging Agent Governance Frameworks

**NIST AI RMF (extended for agents):**
NIST guidance suggests agents be evaluated on:
- Accuracy of goal interpretation
- Appropriateness of actions to goals
- Scope respect (staying within authorized domain)
- Transparency of actions

**Enterprise Agent Governance Checklist:**
1. Define agent's scope explicitly (what it can and cannot do)
2. Implement least-privilege access (only APIs/data needed for its role)
3. Set confidence thresholds (below threshold = escalate to human)
4. Require human approval for high-impact actions (email sends, purchases, deletions)
5. Log all agent actions with timestamps and reasons
6. Implement rollback where possible (draft before send, staging before commit)
7. Monitor outcomes (compare agent decisions to expected outcomes)

**Salesforce's Agentforce Trust Layer:**
Salesforce built a trust layer into Agentforce:
- Data masking: Agent can see customer context but not raw PII
- Output filtering: Agent responses filtered through content safety
- Audit trail: Complete record of agent actions

#### Human-Agent Collaboration Patterns

The most successful 2024-2025 enterprise agent deployments used human-agent collaboration:
- **Supervised autonomy**: Agent does work; human reviews and approves before action
- **Exception-based oversight**: Agent works autonomously; human only sees exceptions
- **Full autonomy with audit**: Agent operates fully autonomously; human reviews audit trail periodically

Most enterprise deployments in 2024 used supervised autonomy—too early for exception-based or full autonomy for most use cases.

### Round 2 Conclusion

Agentic AI is the most transformative technology of 2025-2026, but governance infrastructure must match capability. The difference between "agent that helps" and "agent that causes harm" is often governance design, not technology quality. Organizations should deploy agentic AI with: explicit scope definition, least-privilege access, human checkpoints for high-impact actions, complete audit trails, and clear reversal procedures. Start with supervised autonomy; earn the right to increase autonomy through track record.

---

## Sources

1. Gartner 2025 Strategic Technology Trends
2. Salesforce Agentforce launch announcement (September 2024)
3. Microsoft Copilot Studio documentation
4. OpenAI Operator announcement (2025)
5. Anthropic Claude Computer Use announcement (October 2024)
6. Cognition AI "Devin" demonstration (March 2024)
7. LangGraph, AutoGen, CrewAI documentation
8. Agentic AI market: $14.9 billion by 2025 (SuperAGI market report)

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~1,300 words*
