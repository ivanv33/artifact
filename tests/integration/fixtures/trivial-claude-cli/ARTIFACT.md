---
kind: transform
executor: claude_cli
params:
  - name: topic
    type: string
    required: true
    desc: A single word topic.
outputs:
  - name: haiku.md
    desc: A three-line haiku on the topic.
---

Write a three-line haiku about {{ params.topic }} to `out/haiku.md`.
Do not output anything else. The file must exist and be non-empty.
