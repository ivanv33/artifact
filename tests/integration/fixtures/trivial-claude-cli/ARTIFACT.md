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

Use the Write tool to create the file `out/haiku.md` containing a three-line
haiku about {{ params.topic }}. The Write tool call is mandatory — do not
respond with the haiku as chat text; the file must exist on disk when you
finish.
