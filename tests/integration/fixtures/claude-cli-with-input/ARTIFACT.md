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
of that file is the topic. Then use the Write tool to create `out/haiku.md`
containing a three-line haiku about that topic. The Write tool call is
mandatory — do not respond with the haiku as chat text; the file must exist
on disk when you finish.
