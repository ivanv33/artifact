---
kind: transform
executor: deepagent
model: google_genai:gemini-2.5-flash-lite
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
