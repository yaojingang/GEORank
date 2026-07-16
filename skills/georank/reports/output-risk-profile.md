# Output Risk Profile

Skill: `georank`

## Why This Exists

Generated skills often fail in small output details: generic headings, cluttered citations, fragile screenshots, weak Markdown rendering, or missing execution assumptions. This profile predicts the most likely output mistakes before the skill is used heavily.

## Matched Risk Families

### Code and command safety
- Matched keywords: code, script, cli, command, terminal, api
- Score: `6`

### Tone and specificity
- Matched keywords: copy, article, content, summary
- Score: `4`

### Markdown readability
- Matched keywords: markdown, md, report
- Score: `3`

### Citation and footnote clutter
- Matched keywords: source, reference
- Score: `2`

## Likely Output Mistakes

- Commands can omit environment assumptions, working directory, or rollback notes.
- Code snippets can look runnable while missing required inputs.
- Headings and summaries can drift into generic, interchangeable language.
- The output can sound polished but lose the user's actual taste, audience, or scenario.
- Tables can render as dense grids with weak hierarchy or poor mobile readability.
- Long bullets can make the output look complete while hiding the actual decision logic.

## Output Constraints To Apply

- Name the working directory, required inputs, and expected output for each command.
- Mark destructive or external side-effect operations explicitly.
- Anchor titles and summaries in the user's audience, object, and concrete outcome.
- Avoid placeholder phrases such as comprehensive guide, ultimate solution, or key insights unless the source demands them.
- Use tables only when comparison is the main job; otherwise prefer compact cards or grouped bullets.
- Keep table cells short and move explanations below the table.

## Self-Repair Checks

- Scan each command for cwd, input, output, and side-effect assumptions.
- Remove speculative error handling that is not tied to a real failure mode.
- Replace generic title candidates with scenario-specific alternatives.
- Delete any polished sentence that could fit almost any project unchanged.
- Preview whether each table still reads well when columns are narrow.
- Convert any table with paragraph-length cells into bullets or cards.

## Reviewer Note

Use this report before deepening the package and again before approving example outputs.
