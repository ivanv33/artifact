---
kind: transform
executor: deepagent
model: anthropic:claude-sonnet-4-6
outputs:
  - name: hello.md
    desc: A trivial output.
---

Write a file called `out/hello.md` containing "hi".
