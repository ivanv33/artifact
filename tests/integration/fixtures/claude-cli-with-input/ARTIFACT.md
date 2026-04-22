---
kind: transform
executor: claude_cli
inputs:
  - name: topic.txt
    desc: A file whose first line is a single-word topic.
outputs:
  - name: haiku.md
    desc: A three-line haiku on the topic read from topic.txt.
---

Use the Read tool to read the file at {{ inputs.topic.txt }}. The first line
of that file is a single English word — call it TOPIC. Then use the Write
tool to create `out/haiku.md` containing a three-line haiku about TOPIC. The
haiku must contain the literal TOPIC word (exact spelling, case-insensitive
match is fine) at least once. The Write tool call is mandatory — do not
respond with the haiku as chat text; the file must exist on disk when you
finish.
