# Eval summary: MAF-Magentic vs MAST-GAIA failures

- MAS: `openai/gpt-5.4-mini` | Judge: `openai/gpt-5.4` | 15 tasks x 3 runs
- New task-success rate (originals all failed): **23%**
- Cost: MAS $20.26 + judge $4.57 = **$24.82**

## Per-mode survival (among originally-flagged tasks)

| mode | name | orig-flagged | survive (any run) | survive (majority) |
|---|---|---|---|---|
| 1.1 | Disobey Task Specification | 7 | 43% | 14% |
| 1.2 | Disobey Role Specification | 0 | - | - |
| 1.3 | Step Repetition | 12 | 83% | 67% |
| 1.4 | Loss of Conversation History | 1 | 0% | 0% |
| 1.5 | Unaware of Termination Conditions | 11 | 73% | 64% |
| 2.1 | Conversation Reset | 8 | 38% | 0% |
| 2.2 | Fail to Ask for Clarification | 1 | 0% | 0% |
| 2.3 | Task Derailment | 3 | 0% | 0% |
| 2.4 ⭐ | Information Withholding | 0 | - | - |
| 2.5 ⭐ | Ignored Other Agent's Input | 0 | - | - |
| 2.6 (control) | Action-Reasoning Mismatch | 13 | 54% | 31% |
| 3.1 | Premature Termination | 11 | 64% | 55% |
| 3.2 | Weak Verification | 14 | 100% | 93% |
| 3.3 | No or Incorrect Verification | 0 | - | - |

_⭐ = structural-core target (expect to persist); 2.6 = capability control (expect to drop)._