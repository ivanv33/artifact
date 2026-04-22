"""Emit a reference ``ARTIFACT.md`` and scaffold a new artifact directory.

This module has two public functions. They are deliberately I/O-minimal
and have no CLI coupling — ``cli.py`` is responsible for stdin/argv.

- ``render_template`` returns the reference artifact as a string. YAML
  comments listing allowed values are interpolated from the authoritative
  ``spec.ALLOWED_*`` constants so the template cannot drift from the parser.
- ``create`` (added in a later stage) takes a destination path and content
  string, validates the content via the parser, and writes
  ``<dest>/ARTIFACT.md`` plus ``<dest>/.gitignore``.
"""

from __future__ import annotations

from pathlib import Path

from artifact.spec import ALLOWED_EXECUTORS, ALLOWED_KINDS, ALLOWED_PARAM_TYPES, parse_spec_from_str


def _render_allowed(values: set[str]) -> str:
    """Render an ``ALLOWED_*`` set as ``a | b | c`` (sorted, stable)."""
    return " | ".join(sorted(values))


def render_template() -> str:
    """Return the reference ``ARTIFACT.md`` (frontmatter + body) as a string.

    The comment strings next to ``kind``, ``executor``, and each param's
    ``type`` are interpolated from ``spec.ALLOWED_*`` so they cannot
    silently drift when the parser grows a new accepted value.

    Returns:
        The full artifact text, terminated by a newline.
    """
    kinds = _render_allowed(ALLOWED_KINDS)
    executors = _render_allowed(ALLOWED_EXECUTORS)
    param_types = _render_allowed(ALLOWED_PARAM_TYPES)

    return f"""\
---
# ARTIFACT.md — recipe + provenance container.
# Convention: prefix the parent directory with a DIKW digit
# (0- raw, 1- info, 2- knowledge, 3- wisdom). Not enforced.
# Full reference: docs/artifact-dd.md

kind: transform                        # one of: {kinds}
executor: deepagent                    # one of: {executors}
model: anthropic:claude-sonnet-4-6     # provider:name under executor: deepagent; bare Claude model under executor: claude_cli (optional there)

inputs:
  - name: requirements.md
    desc: |
      Free-form brief describing what you want in a car and why.
      Who drives it, climate, commute, what you'll carry, deal-breakers,
      nice-to-haves, any brand lean or scar tissue ("my last Jetta ate
      two transmissions"). A paragraph is plenty.
      `name:` must be a bare filename.

params:
  - name: max_budget_usd
    type: float                        # one of: {param_types}
    required: true
    desc: Upper bound on what you'll spend out the door (not monthly payment).
  - name: stretch_budget_usd
    type: float
    required: false
    default: null
    desc: |
      Used only for wildcards. If set, the agent may propose picks priced
      up to this amount and explain what the extra money unlocks. Unset =
      no stretch wildcards.
  - name: shortlist_size
    type: int
    required: false
    default: 5
    desc: How many model recommendations to include in the core shortlist.
  - name: wildcard_count
    type: int
    required: false
    default: 3
    desc: |
      How many "outside your requirements" picks to include. Zero disables
      the wildcards section.
  - name: reliability_weight
    type: float
    required: false
    default: 0.7
    desc: |
      0.0 = weight features/fun/looks equally with reliability.
      1.0 = rank reliability above all else.
      Used to shape picks, not to hard-filter.
  - name: include_used
    type: bool
    required: false
    default: true
    desc: |
      true = consider model years going back ~8 years when they fit budget.
      false = limit to new or near-new (within 2 model years).

outputs:
  - name: picks.md
    desc: |
      Prose memo. One H2 per recommended {{year-range, make, model, trim}}
      with: why it fits the requirements, 3-5 things owners consistently
      say (good and bad) with source URLs, expected price band, and
      common issues to watch for at this age/mileage.
  - name: candidates.json
    desc: |
      Structured list of picks:
      [{{
        "rank": <int>,
        "make": <string>,
        "model": <string>,
        "year_range": <string e.g. "2020-2022">,
        "trim_hints": [<string>...],
        "price_usd_range": [<int>, <int>],
        "fit_score": <float 0..1>,
        "why_fits": <string — one sentence>,
        "what_owners_say": [{{"claim": <string>, "source": <url>}}, ...],
        "common_issues": [<string>...],
        "sources": [<url>...]
      }}, ...]
  - name: wildcards.md
    desc: |
      Picks deliberately outside the stated requirements, with a paragraph
      each explaining why the caller should reconsider. Three flavors, one
      of each when applicable: stretch-budget, segment-adjacent,
      older-premium-for-same-dollars.
---

# Body style: refer to agent capabilities as verbs ("search the web",
# "fetch the page"), not specific tool identifiers. Keeps the recipe
# portable across executors; the agent picks the right tool at run time.

You are recommending which cars the author of {{{{ inputs.requirements.md }}}}
should SHORTLIST — the research that happens before they touch a listing
site. You are not finding them a specific vehicle to buy. You are naming
the models, year ranges, and trims worth considering, and explaining why.

Your evidence must come from people who actually own these cars, not from
manufacturer marketing or SEO-bait "top 10" listicles. Prefer:

- Owner communities and model-specific forums for lived experience.
- Independent reliability and recall data (government recall databases,
  consumer-reported complaint aggregators).
- Real-world transaction price ranges, not MSRP or live listings.

Search the web for owner discussions, reliability reports, and recall
histories for each candidate. Fetch specific pages when you need the
exact claim or number to quote. For every factual claim in your outputs,
include an inline URL you actually visited. For every pick, cite at
least two independent owner-community sources. If you can't meet that
bar, say so in the memo rather than padding with weaker sources.

Produce three files:

**`out/picks.md`** — the core memo. {{{{ params.shortlist_size }}}} H2
sections, one per recommended model. Each section opens with a specific
pick (year range + make + model + trim guidance), explains in one
paragraph why it fits the caller's requirements, lists 3-5 bullets of
what owners consistently report (good and bad) with inline source URLs,
names the expected price band, and calls out 1-2 things to watch for
when inspecting a specific listing at that age/mileage.

**`out/candidates.json`** — the same picks in the structured schema
described in the output declaration above. Every `source` must be a real
URL you used.

**`out/wildcards.md`** — {{{{ params.wildcard_count }}}} picks OUTSIDE the
stated requirements. Aim for one of each flavor when applicable:
stretch-budget (only if {{{{ params.stretch_budget_usd }}}} is set — what
does the extra money unlock), segment-adjacent (wagon instead of SUV,
say), and older-premium-for-same-dollars (older model year of a
higher-class vehicle; call out ownership-cost trade-offs honestly).

Weighting: {{{{ params.reliability_weight }}}} near 1.0 ranks reliability
above features; near 0.5 is balanced; below 0.3 means the caller is
buying for joy. {{{{ params.include_used }}}} = false limits picks to new
or within two model years; true widens the net back ~8 years when the
price fits.

Be specific. "Toyota RAV4" is not a pick; "2020-2022 RAV4 XLE or above
(skip LE — cloth seats, no blind-spot monitor)" is a pick.
"""


def create(dest: Path, *, content: str) -> Path:
    """Validate ``content`` and scaffold an artifact directory at ``dest``.

    Writes exactly two files: ``<dest>/ARTIFACT.md`` (the piped content,
    with a trailing newline appended if missing) and ``<dest>/.gitignore``
    containing ``runs/*\\n``.

    Args:
        dest: Destination directory. Created with parents if it does not
            exist. Must be empty if it does exist.
        content: Full ``ARTIFACT.md`` text. Must parse cleanly via
            ``parse_spec_from_str`` — if not, raises before any file is
            written.

    Returns:
        ``dest`` as passed by the caller.

    Raises:
        SpecError: If ``content`` fails parser validation. No files written.
        FileExistsError: If ``dest`` exists and is not empty. No files written.
        OSError: If the directory cannot be created (permissions, etc.).
            No files written.
    """
    parse_spec_from_str(content, dest / "ARTIFACT.md")

    if dest.exists():
        if any(dest.iterdir()):
            raise FileExistsError(f"{dest} is not empty")
    else:
        dest.mkdir(parents=True)

    artifact_text = content if content.endswith("\n") else content + "\n"
    (dest / "ARTIFACT.md").write_text(artifact_text, encoding="utf-8")
    (dest / ".gitignore").write_text("runs/*\n", encoding="utf-8")
    return dest
