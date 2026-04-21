---
kind: transform
executor: deepagent
model: anthropic:claude-sonnet-4-6
params:
  - name: user
    type: string
    required: true
    desc: GitHub username.
  - name: focus
    type: string
    required: false
    default: general
    desc: Optional focus area.
outputs:
  - name: report.md
    desc: Narrative report.
---

Report on {{ params.user }} with focus {{ params.focus }}.
