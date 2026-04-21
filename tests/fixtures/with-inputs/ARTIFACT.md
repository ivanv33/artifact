---
kind: transform
executor: deepagent
model: anthropic:claude-sonnet-4-6
inputs:
  - name: events.json
    desc: GitHub events.
params:
  - name: user
    type: string
    required: true
    desc: GitHub username.
outputs:
  - name: report.md
    desc: Narrative report.
---

Read {{ inputs.events.json }} and produce out/report.md for {{ params.user }}.
