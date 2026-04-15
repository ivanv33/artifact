# Examples

Worked examples of artifact pipelines. Each demonstrates a different shape.

| File | Tier(s) | Demonstrates |
|------|---------|--------------|
| `passover-rain.md` | data → knowledge | Minimal 2-artifact pipeline. PEP 723 self-contained Python script for the knowledge step. No info layer (tagging + stats live inside the script). |
| `bushwick-buy-vs-rent.md` | data → info → knowledge → wisdom | Six-artifact pipeline showing all four DIKW layers. Info layer justified because the cost-comparison CSV is independently reusable. |
| `car-search.md` | data → info → knowledge → wisdom | Multi-make discovery pipeline. Demonstrates: the run file lifecycle, per-item outputs scaling to dozens of files, a `# Criteria` block for fixed inputs (instead of pretending they're params), and `receipts/<output>.<ext>.md` receipts on every output. |

When in doubt, start from the example whose shape most closely matches your goal.
