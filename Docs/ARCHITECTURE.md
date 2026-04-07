__AGENTIC NETOPS__

__INTELLIGENCE LAYER__

 

*Master Architecture & Design Document*

Version 1\.0  |  April 2026

__Classification__

Confidential — Internal Use

__Status__

Architecture Design — Pre\-Build

__Framework Conformance__

NIST AI RMF, ISO 42001, AU VAISS, EU AI Act

__Target Environments__

Home Lab, MSP, Telco, Banking, Government

# __1\. Executive Summary__

*A compliance\-first, vendor\-agnostic, multi\-agent NetOps intelligence layer built on MCP abstractions, designed to stitch into existing enterprise environments and provide reliable, auditable, human\-supervised incident diagnosis and remediation guidance\.*

This system is not a replacement for ServiceNow, Cisco DNAC, Nexus Dashboard, Meraki, NetBox, NSO, or Ansible\. It is an AI\-driven orchestration and decision layer that reads incidents, investigates using existing tools, reasons across telemetry, proposes remediations, validates against policy and known state, and records everything for audit and security review — with a mandatory human approval gate before any actual change\.

# __2\. The Four Absolutes__

Every architecture decision is gated against these four non\-negotiable constraints\. Any design choice that clashes with an absolute must be redesigned before proceeding\.

__Absolute__

__Principle__

__How Enforced__

Cost

Near\-zero for development; cents per demo run

Ollama\-free dev, Haiku API for most reasoning, Sonnet only for complex escalations

Latency

30s end\-to\-end target; under 3 minutes acceptable

Parallel MCP tool calls, async audit writes, LangGraph parallel agent execution

Performance

No blocking operations in the critical reasoning path

Audit, observability, and GitHub writes are all async background tasks

Compliance

Every decision auditable, explainable, and policy\-enforced

Full audit trail per incident, SHA\-256 hashing, zero trust at every boundary

# __3\. Governing Design Principles__

## __3\.1 Plugin Architecture Everywhere__

The single most important architectural decision\. Anything domain\-specific, environment\-specific, or likely to change is decoupled into its own pluggable module\. The core engine remains thin and stable\. Everything variable lives outside it as a plugin\.

*Rule: If you can imagine a second customer needing a different version of it, it gets decoupled\. Every plugin boundary requires a defined contract\. The engine only knows the contracts, never the implementations\.*

__Component__

__What Gets Decoupled__

__How Added__

Scenarios

YAML config files per incident type

Drop in new YAML file

MCP Providers

Provider adapter per vendor

New adapter class

LLM Models

Model interface layer

Swap config value

Escalation Behaviour

Per\-scenario escalation config

YAML addition

Change Correlation Rules

Rule definition files

New rule file

Policy Rules

Policy config files

New policy file

Audit Destinations

Audit sink adapters

New sink adapter

Approval Interface

Channel adapter \(SNOW, Teams, email\)

New channel adapter

Zero Trust Auth

Auth adapter layer

New auth adapter

Prompt Storage

Artifact repository interface

New storage adapter

Test Runner

CI/CD pipeline interface

New runner adapter

Deployment Control

Deployment platform interface

New control adapter

Model Registry

Model governance interface

New registry adapter

Observability Sink

OTel collector target

New exporter adapter

Remediation Mode

Intent\-based or CLI or both

Config per scenario

Compliance Registry

Standards conformance store

New standard entry

AI Register

Deployment documentation

New register entry

## __3\.2 Zero Trust — Data and Human Actors__

Nothing is trusted by default\. Every agent, tool call, data source, and human actor must authenticate, authorise, and be verified on every interaction — regardless of role or prior trust\.

- Every agent has its own identity — Agent A cannot call Agent B without authorisation
- Read tools and write tools carry separate permission scopes
- Even ServiceNow administrators and network engineers cannot interfere outside their defined scope
- Cryptographic pipeline integrity — every stage signs its output, next stage verifies before processing
- Audit records are write\-once and append\-only — no role can modify them retroactively
- Separation of duties enforced by design — no single role can both initiate and approve an action
- Human approvals are cryptographically signed against approver identity — SNOW admin access cannot forge an approval

## __3\.3 Compliance\-First by Design__

Compliance is not bolted on\. Every material decision captures a full audit payload before the response is returned to the user\. Audit writes are async and never block the agent pipeline\.

- Full audit trail per incident: ID, timestamp, agent invoked, tool calls, raw evidence, conclusions, remediation, validation result, policy decision, approval state, output hash
- SHA\-256 hashing of the full input context, prompt version, model version, temperature, and output — combined into a single tamper\-evident record
- Cryptographic evidence chain proves outputs were not altered after the fact
- Prompt injection detection — raw vs sanitised input both recorded in audit trail

# __4\. System Architecture__

## __4\.1 Architecture Overview__

The system operates across three primary layers\. Enterprise systems are never replaced — only integrated through the MCP abstraction layer\.

__Layer__

__Description__

__Layer 1__

Agentic Intelligence Layer — the reasoning brain\. Multi\-agent orchestration via LangGraph\. Specialised agents handle triage, diagnosis, remediation, validation, and audit\.

__Layer 2__

MCP Tool / Provider Layer — the abstraction stitch\. Normalises vendor\-specific responses into a standard schema before agents ever see the data\. Providers are pluggable\.

__Layer 3__

Existing Enterprise Systems — ServiceNow, DNAC, Nexus Dashboard, Meraki, NetBox, NSO, Ansible, Splunk, GitHub\. These are never replaced, only connected\.

## __4\.2 The Five Agents__

Each agent is a Python class with a defined role, scoped MCP tool access, input/output contracts enforced by Pydantic, and behaviour driven by the Scenario Registry\. Agents are built using LangGraph — not AutoGen, CrewAI, or other generic frameworks — because LangGraph provides full orchestration control, auditability, and compliance\-grade visibility\.

__Agent__

__Responsibility__

__LLM Temperature__

Triage Agent

Reads incoming ticket/alert\. Classifies incident type, severity, domain, and likely data sources\. Determines investigation path via Scenario Registry lookup\.

0\.1

Diagnostic Agent

Calls MCP tools to gather telemetry\. Investigates root cause\. Reasons over BGP, interfaces, routes, errors, and topology context\.

0\.2

Validator Agent

Checks diagnosis against raw telemetry, policy, golden config, and known\-state baselines\. Can reject and return for re\-evaluation\. Reduces hallucinations\.

0\.0

Remediation Agent

Proposes remediation steps\. Produces both intent\-based payload \(for DNAC/NSO\) and CLI fallback\. Never executes directly\.

0\.3

Audit Agent

Captures full decision payload\. SHA\-256 hashes the record\. Writes asynchronously to configured audit sink\. Provides immutable accountability\.

0\.0

## __4\.3 Orchestration Patterns__

LangGraph supports all required patterns\. The Scenario Registry determines which pattern applies per incident type\.

- Linear — simple incidents: Triage → Diagnostic → Remediation → Audit
- Loop with rerun — low confidence: Diagnostic → Validator REJECT → Diagnostic \(retry with new context\) → Validator PASS
- Parallel \+ merge — complex multi\-domain: Triage → parallel Diagnostic agents → merged results → Validator → Remediation
- Escalation — edge cases: Diagnostic \(Haiku, low confidence\) → escalate → Diagnostic \(Sonnet, deep reasoning\)
- Max 2 reruns before automatic human escalation — no infinite loops

# __5\. Scenario Registry__

The Scenario Registry is the mechanism by which the system remains extensible without engine changes\. Each scenario is a YAML config file\. Adding new scenarios requires no code changes — drop a new YAML file in the registry folder and the engine picks it up automatically\.

*Starting with 20 common network scenarios\. Designed to scale to 50\+ without any engine modification\.*

__Each scenario definition contains:__

- Scenario ID and display name
- Trigger keywords and alert type mappings
- Which agents are required for this scenario
- Which MCP tools to call \(and whether in parallel\)
- Maximum diagnostic retries before human escalation
- Confidence threshold for Sonnet escalation
- Whether remediation requires human approval
- Compliance tier \(high / medium / low\)
- Change correlation settings including lookback window and max tickets
- Escalation config including vendor handoff and pre\-written case note generation
- Remediation execution mode: intent\_only, cli\_only, or both
- Tiered progressive loading settings \(Tier 1/2/3 triggers and limits\)
- Context window priority data fields per scenario

# __6\. MCP Abstraction Layer__

MCP is the abstraction contract between agents and vendor systems\. Agents never see raw vendor data\. Every provider response is normalised into a standard schema envelope before agents consume it\.

## __6\.1 Normalised Response Envelope__

Every MCP tool response must conform to this structure regardless of backend vendor:

- source — which provider returned this data
- timestamp — when the data was retrieved
- confidence — provider's self\-reported confidence in the data
- freshness — how current the data is
- completeness — full / partial / stale flags
- payload — the normalised data in standard schema
- raw\_hash — SHA\-256 of the raw vendor response before normalisation

## __6\.2 Core MCP Tools__

__get\_bgp\_neighbors\(\)__

Returns normalised BGP peer state regardless of vendor

__get\_interface\_health\(\)__

Interface counters, errors, and status

__get\_routing\_table\(\)__

Routing table with prefix and next\-hop normalisation

__get\_routing\_impact\(\)__

Blast radius assessment for a given failure

__get\_incident\_context\(\)__

ServiceNow ticket and related CI data

__get\_change\_records\(\)__

Recent changes against a CI within a lookback window

__validate\_against\_policy\(\)__

Checks proposed action against policy store

__get\_similar\_incidents\(\)__

RAG retrieval from outcome database

__get\_topology\_context\(\)__

Upstream/downstream CI relationships

__get\_redundancy\_state\(\)__

Failover path availability for a device

## __6\.3 Provider Examples__

The same agent logic runs against any of these backends via the normalised MCP contract:

- Cisco Nexus, DNAC / Catalyst Center, Nexus Dashboard, Meraki
- NSO, NetBox, Ansible AWX
- ServiceNow, GitHub
- Mock simulators, Cisco DevNet sandboxes
- Hybrid connectors for on\-premise, private cloud, SD\-WAN, and co\-location zones

# __7\. Confirmed Technology Stack__

__Layer__

__Technology__

__Role__

Agent Orchestration

LangGraph \(free, local Python\)

Agent flow, loops, parallel execution, state management

API Framework

FastAPI

Webhook receiver, agent API, approval portal backend

LLM — Standard

Claude Haiku

Triage, change correlation scoring, simple reasoning \(~$0\.001/call\)

LLM — Complex

Claude Sonnet

Edge cases, low\-confidence escalation \(triggered conditionally\)

Data Contracts

Pydantic \+ OpenAPI

Runtime contract enforcement at every agent boundary

Observability

OpenTelemetry

Traces, metrics, latency — exports to Grafana \(demo\) or Splunk/Datadog \(enterprise\)

Scenario Registry

YAML files

Decoupled scenario definitions — no engine changes to add scenarios

Audit Trail

GitHub \(demo\) / pluggable sink

Immutable evidence commits — enterprise replaces with approved store

Outcome Database

PostgreSQL \+ pgvector

Incident outcomes and RAG vector search for contextual intelligence

Trigger / Callback

n8n \(optional plugin\)

Outer trigger layer only — not in critical reasoning path

Demo Approval UI

Grafana \+ FastAPI

Combined observability and human approval interface for demo

ITSM

ServiceNow

Ticket source, CI change records — never replaced, only integrated

# __8\. Data & Intelligence Architecture__

## __8\.1 Tiered Progressive Data Loading__

Complex incidents generate massive telemetry\. The system loads data in priority tiers and stops when confidence is sufficient — preventing context window overflow and controlling cost\.

__Tier__

__Data Sources__

__Trigger Condition__

Tier 1 — Immediate

Recent logs, current device state, active alarms

Always — runs first in parallel with Tier 2

Tier 2 — Change Correlation

SNOW tickets for affected CI \+ directly connected CIs, changes within 72hr window

Always — runs parallel to Tier 1

Tier 3 — Broader Investigation

Upstream/downstream CI tickets, backup config comparison, historical RAG patterns

Only if Tiers 1\+2 confidence below scenario threshold

## __8\.2 Context Window Management__

- Payload summarisation — raw telemetry is preprocessed by a deterministic Python summariser before entering agent context \(e\.g\. 10,000\-line BGP table becomes a structured 3\-line summary\)
- Scenario\-driven data prioritisation — Scenario Registry defines which fields are priority vs deprioritised per incident type
- Sequential reasoning passes via LangGraph — used when data genuinely exceeds context limits

## __8\.3 Change Correlation Engine__

When SNOW change records exist for an affected CI, the system applies a two\-layer correlation approach:

- Layer 1 — Deterministic scoring: each change scored against the incident using rule\-based factors \(CI directly connected \+40pts, change type routing/network \+30pts, timing within 1hr \+20pts, same vendor platform \+10pts\)\. Fast, auditable, no LLM cost\.
- Layer 2 — LLM reasoning: only invoked when deterministic scoring cannot separate two similarly\-scored changes\. Network domain knowledge applied to ambiguous cases only\.
- Layer 3 — Human arbitration: when still ambiguous, the approval UI presents both changes side\-by\-side with scores\. Human decision is recorded and feeds the outcome database\.
- Messy or overly complex change notes are flagged as unassessable — raw notes included in evidence package, autonomous remediation blocked, human alerted\.

## __8\.4 Evidence Quality Metadata__

Confidence score alone is insufficient\. Every diagnosis carries evidence quality metadata alongside the confidence score:

- accessible\_cis — count of CIs successfully queried
- inaccessible\_cis — count of CIs unreachable or timed out
- lagged\_sources — count of sources returning stale data
- missing\_data\_impact — high / medium / low assessment of what the gaps mean for diagnosis quality

The human approval UI surfaces all of this — the engineer sees not just the confidence number but precisely why it is what it is\.

# __9\. Organisational Contextual Intelligence__

The system's primary competitive moat\. It does not just learn network patterns — it learns team structures, workflow preferences, organisational topology, and audit requirements specific to each deployment environment\.

## __9\.1 Four Learning Dimensions__

__Dimension__

__What Is Learned__

__Business Value__

Network Pattern Intelligence

Failure patterns, device behaviour, vendor\-specific anomalies specific to this environment

Faster diagnosis, higher confidence on repeated incident types

Team & Workflow Intelligence

Which team owns which incident domain, escalation paths, working hours, preferred diagnosis format

Correct routing first time, team\-appropriate output format

Organisational Audit Intelligence

Security team's required fields, evidence chain format, sign\-off structure

Security team pulls exactly what they need without reformatting

Domain Boundary Intelligence

Which team owns which slice of a cross\-domain incident

Split diagnosis packages per team — each sees only their relevant portion

## __9\.2 RAG Implementation__

- Outcome database: PostgreSQL with pgvector extension — single database, minimal cost
- Every resolved incident stored as a structured knowledge record with symptoms, changes present, human verdict, AI confidence at diagnosis time, actual outcome, and resolution time
- RAG retrieval runs parallel to Tier 1 investigation — zero added latency
- Feedback quality gate — low\-confidence diagnoses overridden by humans go to review queue before entering RAG, preventing bad reasoning from compounding

## __9\.3 Passive Feedback Signals__

Engineer burden is near\-zero\. The system learns primarily from behaviour signals, not mandated written notes:

- Remediation modified before approval — what was changed is recorded
- Resolution code in SNOW does not match AI suggested fix — mismatch signal
- Resolving team different from AI recommended team — routing signal
- Same device generates another incident within 4hrs of resolution — MCP network signal, not SNOW
- When human does override: single forced\-choice selection only \(Wrong root cause / Correct cause wrong remediation / Missing context / Policy reason / Other\)\. Optional free text\. 10 seconds maximum effort\.

# __10\. Reliability & Hallucination Controls__

## __10\.1 LLM Non\-Determinism Strategy__

Non\-determinism is managed through three combined layers — no single layer is sufficient alone:

- Temperature control per agent role — Validator at 0\.0, Triage at 0\.1, Diagnostic at 0\.2, Remediation at 0\.3\. Overridable per scenario in registry\.
- Structured output enforcement — agents respond in strict JSON schema via Pydantic\. Free\-form text responses are where variance hides\.
- Audit trail locks the record — input context hash \+ temperature setting \+ model version \+ prompt version \+ output hash\. Auditor does not need to replay — every condition is recorded\.

## __10\.2 Prompt Engineering Discipline__

Prompts are versioned artifacts with full engineering discipline — not hardcoded strings:

- Prompts stored as versioned files in source control — each change is a commit
- Scenario\-based regression test suite — all 20\+ scenarios must pass before deployment
- Canary deployment — new prompt version handles 10% of incidents; auto\-rollback if confidence scores or validator pass rates drop
- Prompt version included in audit hash — every incident record shows exactly which prompt version produced that diagnosis

In enterprise deployments, the three plugin boundaries for prompt management are independently configurable:

- Prompt Storage Interface — internal artifact repository \(Artifactory, internal GitLab\)
- Test Runner Interface — internal CI/CD \(Jenkins, internal pipelines\)
- Deployment Control Interface — internal deployment platform

## __10\.3 Prompt Injection Security__

The system ingests user\-written data \(SNOW tickets, change notes\)\. Injection attacks are a real vector in production:

- Layer 1 — Input sanitisation: deterministic Python preprocessor strips injection patterns at the MCP ingestion layer before any LLM sees the data
- Layer 2 — Injection detection: lightweight parallel LLM check specifically scanning for imperative commands, role override attempts, approval bypass language, and system prompt references in data fields
- Layer 3 — Structural separation: agent prompts and external data never exist in the same context string\. Data is always passed as structured JSON fields, never concatenated into instruction text\. Enforced by Pydantic contracts\.
- All injection attempts — detected or suspected — are logged to audit trail with raw vs sanitised input comparison

## __10\.4 Graceful Degradation__

- If a CI is inaccessible or response is lagged — continue with partial evidence, report evidence quality metadata explicitly, never assume missing data means no problem
- Hard timeouts enforced per provider — system never waits indefinitely
- If provider unavailable — partial evidence continues, uncertainty surfaced to human, autonomous remediation blocked

# __11\. Remediation Architecture__

## __11\.1 Intent\-Based \+ CLI Dual Mode__

Remediation output is a two\-layer structure supporting both modern intent\-based controllers and legacy CLI environments\. Enterprise selects mode via Scenario Registry config\.

__Mode__

__Output__

__Target Environment__

intent\_only

Structured intent payload for DNAC/NSO to resolve into vendor CLI

Modern intent\-based environments

cli\_only

Vendor\-specific CLI commands

Legacy environments without intent controller

both \(default\)

Intent payload primary, CLI fallback if no controller detected

Mixed/transitional environments — enterprise selects per scenario

*The remediation agent never executes changes directly\. It proposes\. The Validator checks\. A human approves\. Only then does execution occur via the enterprise's own tooling\.*

## __11\.2 Vendor Escalation Handoff__

For incidents where internal triage is exhausted and vendor engagement is required \(e\.g\. Cisco TAC\):

- System confirms all internal checks are clear
- Auto\-updates SNOW ticket with full evidence package
- Pre\-writes vendor case notes with exact symptoms, evidence, timestamps, and recommended priority
- Flags to human for approval before any vendor contact — entitlement, business priority, and relationship decisions remain with the human
- Human arrives at the handoff point with zero legwork remaining

# __12\. Compliance & Governance__

## __12\.1 Framework Conformance__

__Framework__

__Conformance__

__How Addressed__

Australian AI Ethics Principles \(8 principles\)

Full

Fairness, accountability, transparency, reliability, privacy/security, contestability, human oversight, wellbeing — all addressed by design

Australian Voluntary AI Safety Standard / Guidance for AI Adoption \(Oct 2025\)

Full

All 10 guardrails covered\. Compliance Registry plugin tracks conformance per standard\.

NIST AI Risk Management Framework

Full

Govern\-Map\-Measure\-Manage loop implemented across agent design and audit architecture

ISO/IEC 42001

Full

AI management system alignment via Compliance Registry and audit infrastructure

Microsoft Responsible AI \(6 principles\)

Full

Fairness, Reliability & Safety, Privacy & Security, Inclusiveness \(N/A\), Transparency, Accountability

EU AI Act

Aligned

Risk\-proportionate design, human oversight, transparency, audit trail

## __12\.2 Compliance Registry Plugin__

A versioned store of which standards the system is currently conforming to and which policy/audit plugins implement them\. When a new government or industry standard is released:

- Update the relevant plugin or adapter \(not the engine\)
- Add the new standard entry to the Compliance Registry
- Regression suite validates conformance before deployment

*Retrofitting a new standard is a configuration and adapter exercise, not an engine rebuild\.*

## __12\.3 AI Register__

Australian government guidance \(National AI Centre, October 2025\) requires organisations to maintain an AI Register\. The system generates a deployment AI Register entry as part of its deployment package — this is a documentation plugin and requires no engineering changes\.

# __13\. Observability & Visibility__

## __13\.1 Three Visibility Planes__

Three distinct dashboards serve three distinct audiences\. In demo environments all three run in Grafana\. In enterprise, the OpenTelemetry layer exports to the enterprise's existing tooling\.

__Dashboard__

__Audience__

__Key Metrics__

Management Dashboard

CIO, IT Management, Service Owners

Incidents handled vs escalated, average resolution time, accuracy trend, cost per incident, engineer hours saved \(ROI\)

Security Dashboard

CISO, SecOps, Security Analysts

Prompt injection attempts, zero trust violations, unauthorised access attempts, audit trail integrity status, agent behaviour anomalies

Compliance & Governance Dashboard

Compliance Officers, Auditors, Risk Teams

Policy violations flagged, human override rate and reasons, approval workflow completion, standards conformance status, outstanding approvals aging

## __13\.2 Export Formats__

__Format__

__Use Case__

__Enterprise Target__

CSV

Raw data export for internal analysis

All environments

PDF

Formal compliance reports for regulators

Regulated industries

JSON

Integration with SIEM or enterprise reporting

Splunk, Elastic, Datadog

API Endpoint

Live feed into BI and SIEM tools

Power BI, Tableau, Splunk

__Common enterprise observability tools by segment:__

- Banks, telcos, Australian government — Splunk \(dominant in Australia\)
- Microsoft\-heavy enterprises — Power BI \+ Azure Monitor
- Cloud\-native enterprises — Datadog
- Tech\-forward / telcos — Elastic/Kibana
- IBM shops — IBM Instana

# __14\. Deployment Architecture__

## __14\.1 Deployment Topology Variants__

Same engine and codebase across all deployment targets\. Only provider configs, access controls, and audit sink adapters change\.

__Environment__

__Footprint__

__Key Differences__

Home Lab / Demo

Docker Compose, local or cloud LLM, mock/sandbox providers

All components local, GitHub audit sink, Grafana for all dashboards and approvals

MSP Deployment

Single VM or small Docker host

Connects to customer systems via API, mostly read\-only mode, lightweight footprint per customer

Telco / Large Enterprise

Private cloud or approved AI environment, MCP connectors in secure on\-prem zones

Strict RBAC, stronger audit/SIEM integration, remediation policy\-gated, Splunk sink

Banking / Government

Air\-gapped or sovereign cloud options

Private inference option, internal artifact repositories, internal CI/CD, dedicated compliance tooling

## __14\.2 Hybrid Network Environment Support__

Enterprises operate across on\-premise, private cloud, public cloud, SD\-WAN edges, and co\-location facilities simultaneously\. Each zone gets its own MCP connector adapter:

- Same plugin architecture principle applied to connectivity
- Each zone connector is independently authenticated under zero trust
- Cross\-zone calls are async with hard timeouts and partial\-data handling
- Air\-gapped zones can operate with local connector agents that sync when connectivity permits

# __15\. Build Roadmap__

## __15\.1 Pre\-Build Requirements__

These must be resolved before Weekend 1 code is written:

- Canonical data schema — the normalised MCP response envelope every provider must conform to
- Failure mode map — every failure type \(provider timeout, partial data, stale data, low confidence, validator reject, policy block\) with defined behaviour
- Agent communication contract — how agents pass context via LangGraph state
- Idempotency strategy — if an incident triggers twice, defined behaviour
- Schema versioning strategy — MCP tool responses and agent prompts

## __15\.2 Build Milestones__

__Weekend__

__Focus__

__Goal__

Weekend 1

MCP Server \+ Provider Abstraction

Mock Cisco Nexus telemetry, realistic JSON responses, anomaly scenarios \(BGP peer down, interface errors, routing loop, partial telemetry\)\. Prove abstraction and evidence model\.

Weekend 2

Multi\-Agent Reasoning Layer

Triage, Diagnostic, Validator, Remediation, Audit agents via LangGraph\. Tool\-grounded diagnosis with hallucination checking\. Scenario Registry operational\.

Weekend 3

Orchestration \+ Integration

ServiceNow webhook trigger, context enrichment, agent orchestration, status updates, approval portal \(Grafana\)\. Incident in, diagnosis out, human sees structured output\.

Weekend 4

Compliance, Intelligence, Polish

SHA\-256 audit hashing, GitHub audit commits, RAG outcome database foundation, prompt versioning, observability dashboards, demo readiness, README and architecture docs\.

## __15\.3 Build Governance__

Every milestone follows this structure:

- Design review — five\-lens check \(Scalability, Reliability, Vendor Agnosticism, Compliance, Four Absolutes\) before writing code
- Build — component implementation
- Adversarial test — explicit question: what breaks this?
- Document decisions — Architecture Decision Records for every major choice
- Absolutes sign\-off — explicit verification that cost, latency, performance, and compliance are still satisfied

# __16\. MVP Demo Scenario__

*BGP Peer Down at 2am — The Reference Demo*

This scenario demonstrates every capability of the system in a single coherent flow:

__Step 1__

BGP peer drops at 2am\. ServiceNow creates an incident automatically\.

__Step 2__

Orchestration layer triggers\. Triage Agent classifies the incident via Scenario Registry lookup\.

__Step 3__

Parallel execution: Diagnostic Agent queries simulated Cisco telemetry via MCP\. Change Correlation Engine queries SNOW for recent changes against the affected CI and connected CIs\.

__Step 4__

RAG retrieval runs in parallel — retrieves similar past incidents from the outcome database\.

__Step 5__

Diagnostic Agent identifies the failed peer, routing impact, and correlates against change records\. Confidence score and evidence quality metadata produced\.

__Step 6__

Validator Agent confirms the diagnosis is grounded in real evidence, does not violate policy assumptions, and checks for prompt injection in source data\.

__Step 7__

Remediation Agent produces both intent\-based payload and CLI fallback\. Vendor case notes pre\-written if TAC engagement required\.

__Step 8__

Audit Agent hashes the full decision package and commits asynchronously to GitHub\.

__Step 9__

Human approval request sent\. Engineer sees diagnosis, confidence, evidence quality, proposed remediation, and risk rating in Grafana approval UI\.

__Step 10__

Human approves\. Outcome recorded\. Feedback signal enters the outcome database\. Organisational contextual intelligence grows\.

# __17\. Future Evolution Considerations__

## __17\.1 AI Capability Evolution__

- Multi\-agent architecture is designed to accommodate collapsing multiple agents into a single model call if/when model capability makes this viable — without redesigning orchestration
- Model interface layer is swappable — Claude API replacement requires only a new model plugin
- Prompt versioning and regression suites protect against behavioral drift from model updates

## __17\.2 Network Infrastructure Evolution__

- Intent\-based remediation output is already designed for Cisco's intent\-based networking direction
- CLI fallback ensures backward compatibility with legacy environments during transition periods
- MCP provider adapters can be extended for new vendor APIs without agent changes

## __17\.3 Regulatory Evolution__

- Australian mandatory guardrails for high\-risk AI settings are expected — Compliance Registry plugin handles conformance updates
- EU AI Act enforcement ramps through 2025\-2026 — architecture already aligned
- IEEE, NIST, and ISO agentic AI standards are emerging — plugin architecture ensures conformance is a config exercise

*Document Status: Living Document — Updated Continuously Through Design Phase*

*All decisions subject to Four Absolutes gate before finalisation*

