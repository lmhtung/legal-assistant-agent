# Explainable Educational Question Answering Challenge

## Introduction

Large Language Models (LLMs) have demonstrated impressive abilities in question-answering systems, including those applied in educational contexts. However, these models often generate only brief, single-answer responses without providing any reasoning or explanatory detail.

In educational environments, this lack of transparency poses significant challenges.

### Quality of Answers

When an answer is incorrect, we cannot trace or understand the source of the error. When it is correct, we have no visibility into how it was derived or whether it was properly verified.

### Complex Reasoning

Educational domains often involve intricate rules, policies, and multi-step logical reasoning, which can be challenging for purely data-driven LLMs to handle reliably.

One promising direction within Explainable AI (XAI) is **Symbolic Reasoning**, where a Symbolic Engine, either standalone or integrated with an LLM, makes the reasoning process explicit. However, many other approaches can also achieve transparency.

This challenge invites any method that enhances both the accuracy and interpretability of educational Question Answering (QA) systems, making them more suitable for verifiable use in learning environments.

---

## Example Queries

The following examples illustrate the types of educational queries this challenge addresses, along with expected transparent responses.

| Query | Expected Response |
|---|---|
| This semester, I scored 8 points on the final exam for the DSA course. However, I was absent for the lab exam. Can I still get a B in this course? | No. Because you missed the lab exam, you received a score of 0 for lab work. According to Regulation #13 of X University, a student with 0 lab points cannot pass the course. |
| Calculate the equivalent resistance of the following circuit, given that each resistor has a resistance of `r`. | Since the resistors are connected together at both ends, the circuit can be redrawn to show that the three resistors are connected in parallel. Therefore, the equivalent resistance is: `R = r / 3`. |

---

## Challenge Objectives

The primary goal of this challenge is to build educational QA systems that not only produce accurate answers but also provide clear, verifiable reasoning for how those answers were derived.

Specifically, we seek to:

- Encourage, but not require, the use of symbolic reasoning tools such as Z3, custom solvers, or other logic-based engines alongside LLMs.
- Extend XAI research into STEM domains such as physics, especially electric circuits.
- Provide benchmark datasets and evaluation frameworks to support future developments in explainable AI for education.

---

## What We'll Build

Participating teams will develop systems that:

- Provide correct final answers to educational queries.
- Generate natural language explanations that justify each answer.
- Optionally provide additional supporting evidence, such as:
  - First-Order Logic (FOL) derivations
  - Chain-of-Thought (CoT) reasoning
  - Premise lists
  - Structured proofs
  - Other interpretable reasoning traces
- Use any approach, including symbolic reasoning, neurosymbolic methods, fine-tuned LLMs, or any combination, as long as the system can explain how it arrived at each answer.

---

## Competition Rules

### Who Can Participate

This competition is open to everyone, including:

- High school students
- University students
- Working professionals
- Researchers worldwide

There is no restriction on age, nationality, or affiliation, except that members of the **URA Research Group**, the organizing team, are not eligible to participate.

---

## Rules

All participating teams must adhere to the following rules throughout the competition.

### DO

#### Provide Explainable Answers

Every generated answer must be accompanied by a natural language explanation that justifies how the answer was derived.

The explanation should be:

- Concise
- Interpretable
- Verifiable

#### Encouraged: Use a Symbolic Engine

Teams are encouraged to incorporate symbolic reasoning, such as:

- Z3 Solver
- Custom-built reasoning engines
- Logic-based solvers
- Rule-based verification modules

However, this is not mandatory. Any approach that produces explainable results is accepted.

#### Use Open-Source LLMs

All LLMs used in the system must be:

- Open-source
- 8 billion parameters or fewer

This applies to any LLM component, whether used for:

- Answer generation
- Reasoning
- Natural Language to Logic conversion
- Explanation generation

---

### DO NOT

#### Use Closed-Source Models

The use of commercial or closed-source LLMs is strictly prohibited, including but not limited to:

- GPT
- Claude
- Gemini

Submissions that rely on closed-source models will be disqualified.

#### Hide External Data Sources

All external datasets used for fine-tuning LLMs or Symbolic Engines must be fully disclosed.

Failure to disclose external data usage will result in disqualification.

---

## Datasets

The official datasets will be released at the kick-off workshop.

Two dataset types will be provided, covering:

1. Logical reasoning in educational regulations
2. Physics problem-solving

The input provided to each team's system depends on the dataset type. All other fields, such as FOL, CoT, explanations, and other annotations shown in the samples, are reference annotations provided in the training data only. Teams can use them as templates for building their own reasoning pipelines.

---

## Dataset Type 1: Logic-Based Educational Queries

This dataset contains **464 records** with a total of **913 questions** designed to evaluate logical reasoning in educational contexts.

Topics include university regulations such as:

- Grading policies
- Course enrollment rules
- Scholarship criteria
- Academic requirements

Question types include:

- Multiple Choice
- Yes / No / Uncertain
- Open-ended queries

Each record includes:

- A set of premises in natural language
- A set of premises in First-Order Logic
- Derived questions
- Ground-truth answers
- Human-written explanations

During evaluation, the system receives the question together with the natural language premises, `premises-NL`, as input. Teams are free to use the premises in any way, such as prompt context, FOL conversion, rule extraction, or symbolic verification.

### Sample Data

```json
{
  "premises-NL": [
    "If a curriculum is well-structured and has exercises, it enhances student engagement.",
    "If a curriculum enhances student engagement and provides access to advanced resources, it enhances critical thinking.",
    "If a faculty prioritizes pedagogical training and curriculum development, the curriculum is well-structured.",
    "The faculty prioritizes pedagogical training and curriculum development.",
    "The curriculum has practical exercises.",
    "The curriculum provides access to advanced resources."
  ],
  "premises-FOL": [
    "ForAll(c, (well_structured(c) ∧ has_exercises(c)) → enhances_engagement(c))",
    "ForAll(c, (enhances_engagement(c) ∧ advanced_resources(c)) → enhances_critical_thinking(c))",
    "..."
  ],
  "questions": [
    "Based on the premises, what can we conclude about the curriculum?\nA. It enhances student engagement but not critical thinking\nB. It enhances critical thinking\nC. It needs more resources to enhance critical thinking\nD. It is well-structured but lacks exercises",
    "Does the combination of faculty priorities and curriculum features lead to enhanced critical thinking?"
  ],
  "answers": ["B", "Yes"],
  "explanation": [
    "Premise 4 and premise 3 confirm the curriculum is well-structured. Premise 5 provides exercises, so premise 1 implies enhanced engagement. Premise 6 adds advanced resources, and premise 2 confirms enhanced critical thinking, supporting option B.",
    "Faculty priorities satisfy premise 3, making the curriculum well-structured. Exercises (premise 5) and premise 1 lead to enhanced engagement, and with advanced resources (premise 6), premise 2 confirms enhanced critical thinking."
  ]
}
```

---

## Dataset Type 2: Physics Problems

This dataset contains **5,520 text-based physics problems** focusing on electric circuits and electrostatics.

Topics include:

- Resistance
- Voltage
- Current
- Power
- Capacitance
- Electric fields
- Energy calculations

Questions are numerical and require multi-step computation.

Each problem comes with:

- Step-by-step CoT reasoning
- Final numerical answer
- Unit

During evaluation, the system receives only the question as input. The source materials, such as textbooks and knowledge references, used to construct this dataset will be announced at the kick-off workshop.

### Sample Data

```json
{
  "id": "TD401",
  "question": "Calculate the energy stored in capacitor C when C = 100 μF and U = 30 V.",
  "cot": "Step 1: Identify the given values for capacitance (C) and voltage (U).\nStep 2: Recall the formula for energy: E = 0.5 * C * U^2.\nStep 3: Convert capacitance to Farads: C = 100 μF = 1 × 10^-4 F.\nStep 4: Substitute: E = 0.5 × (1 × 10^-4) × (30)^2.",
  "answer": "45",
  "unit": "J"
}
```

---

## Evaluation Criteria

Submissions are assessed across three dimensions: correctness, explanation quality, and reasoning depth.

| Criterion | Description |
|---|---|
| P1: Correctness of Answers | Generating accurate and precise answers for the given queries. |
| P2: Quality of Explanation | Providing a clear, coherent natural language explanation that justifies the answer. |
| P3: Depth of Reasoning | Demonstrating strong reasoning capabilities through additional supporting evidence, such as FOL derivations, CoT steps, premise identification, or other structured proofs. |

---

## Test Format

The official test set will combine both dataset types into a single unified set.

For **Type 1 queries**, the system receives:

- The question
- Natural language premises

For **Type 2 queries**, the system receives:

- The question only

Questions will include:

- Multiple-choice questions
- Yes / No / Uncertain questions
- Open-ended reasoning questions
- Numerical computation problems

The topic distribution, including the percentage of each dataset type, will be announced at the kick-off workshop.

---

## Evaluation Process

### Phase 1 & 2: Selection

Submissions are first scored automatically against ground-truth answers. They are then reviewed by the organizing committee for explanation quality.

### Final Round

Top teams run their systems live on unseen queries.

The Challenge Chairs evaluate each team's:

- Answers
- Explanations
- Reasoning depth

Teams demonstrating stronger reasoning capabilities will be ranked higher.

### Final Score

The final score will be computed as a weighted combination of:

- P1: Correctness of Answers
- P2: Quality of Explanation
- P3: Depth of Reasoning

Specific weights will be published with the official dataset release.

---

## Submission Requirements

Each team must submit:

1. An API endpoint
2. A brief solution description, limited to 1 page, detailing:
   - The proposed approach
   - Models used
   - Dataset used for training

For each query, the API must return the required fields below.

Teams are encouraged to include optional fields that demonstrate the depth of their system's reasoning. Richer evidence will have an advantage in the evaluation, particularly in the final round where the Challenge Chairs assess reasoning depth live.

### API Response Format

```json
{
  "answer": "B",
  "explanation": "The voltage across R2 is calculated using ...",

  "fol": "∀x (Resistor(x) → HasVoltage(x, V))",
  "cot": [
    "Step 1: Identify the circuit topology ...",
    "Step 2: Apply Kirchhoff's voltage law ...",
    "Step 3: Solve for the unknown voltage ..."
  ],
  "premises": [
    "Ohm's law: V = IR",
    "KVL: sum of voltages in a loop = 0"
  ],
  "confidence": 0.92
}
```

### Required Fields

| Field | Required | Description |
|---|---:|---|
| `answer` | Yes | The final answer produced by the system. |
| `explanation` | Yes | A natural language explanation justifying how the answer was derived. |

### Optional Fields

| Field | Required | Description |
|---|---:|---|
| `fol` | No | First-Order Logic representation or derivation. |
| `cot` | No | Step-by-step reasoning or computation trace. |
| `premises` | No | Supporting rules, formulas, assumptions, or retrieved evidence. |
| `confidence` | No | Confidence score produced by the system. |

> **Note:** `answer` and `explanation` are mandatory for every submission. All other fields, including `fol`, `cot`, `premises`, and `confidence`, are optional but encouraged, as they contribute to higher scores in the reasoning depth evaluation. The final submission format will be finalized at the kick-off workshop.

---

## Recommended System Design

Although the challenge does not require a specific architecture, participants may consider building a modular explainable QA system with the following components:

```text
                           ┌────────────────────────────┐
                           │ User Query                 │
                           └─────────────┬──────────────┘
                                         │
                                         v
                           ┌────────────────────────────┐
                           │ Supervisor Agent            │
                           │ - classify query            │
                           │ - select registered agent   │
                           └─────────────┬──────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │                                         │
                    v                                         v
        ┌───────────────────────┐               ┌───────────────────────┐
        │ Physics Agent          │               │ Logic Agent            │
        │                        │               │                        │
        │ Reasoning              │               │ Reasoning              │
        │ Tool Selection         │               │ Tool Selection         │
        │ Execute Tools          │               │ Execute Tools          │
        │ Gather Results         │               │ Gather Results         │
        │ Self Evaluation        │               │ Self Evaluation        │
        │ Self Correction        │               │ Self Correction        │
        │ Build Output           │               │ Build Output           │
        └───────────┬───────────┘               └───────────┬───────────┘
                    │                                       │
                    └────────────────────┬──────────────────┘
                                         v
                           ┌────────────────────────────┐
                           │         Supervisor         │
                           └─────────────┬──────────────┘
                                         v
                           ┌────────────────────────────┐
                           │ Final JSON Response         │
                           └────────────────────────────┘
```

Possible implementation choices include:

- Open-source LLMs with 8B parameters or fewer
- Retrieval-Augmented Generation
- Formula databases
- Rule databases
- Z3 Solver
- SymPy
- Custom symbolic engines
- Fine-tuned small language models
- Hybrid neurosymbolic pipelines

---

## License

The license will be announced by the organizing committee.
