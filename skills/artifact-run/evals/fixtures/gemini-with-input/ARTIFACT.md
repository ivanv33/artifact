---
kind: transform
executor: deepagent
model: google_genai:gemini-2.5-flash
inputs:
  - name: topic.md
    desc: Markdown describing the topic.
outputs:
  - name: haiku.md
    desc: A three-line haiku about the topic.
---

Read the topic from {{ inputs.topic.md }} and write a three-line haiku about it to `out/haiku.md`.
Do not output anything else. The file must exist and be non-empty.
