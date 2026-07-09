# Marginalia

Marginalia turns a Markdown file into a self-contained review document. A reviewer
opens one HTML file, selects exact text, records priority feedback or deletions,
and sends the file back. The receiving agent gets source addresses, intent, and
threaded discussion without re-ingesting the whole document as review context.

The viewer is offline and zero-server. It embeds the Markdown snapshot and review
ledger directly in the HTML, fetches nothing at runtime, and uses system fonts.

## Review Loop

```text
plan.md -> plan-view.html -> reviewer -> digest or revision packet -> revised plan.md
```

1. Bake a source file:

   ```sh
   python3 build-view.py plan.md
   ```

2. Open `plan-view.html` in a browser. Chromium browsers, including Helium, can
   save it in place after the reviewer drags the file onto its own window once.
   Firefox and Safari fall back to a downloaded replacement file.

3. Select a span and choose a review signal:

   | Signal | Meaning | Shortcut |
   | --- | --- | --- |
   | Critical | Mission-critical correction | `1` |
   | Important | Fix before another unnecessary iteration | `2` |
   | Refinement | Low-risk polish or clarification | `3` |
   | Strike | Delete the selected text | `X` |

   Priority notes automatically colour their source span. Strike creates a direct
   deletion operation. Every coloured span has an explicit review intent.

4. Post the comment, reply in the focused discussion when needed, then save the
   view. The review queue filters Critical, Important, Refinements, and Deletions.

5. Collect the feedback:

   ```sh
   python3 distill.py plan-view.html
   python3 distill.py --packet plan-view.html
   ```

   The digest is human-readable. The revision packet is structured JSON for an
   agent that can read the current Markdown source. Neither duplicates the full
   source text merely to carry the review.

6. Revise the Markdown, then bake it again. Existing notes carry forward. A span
   whose reviewed text no longer locates stays visible as `text changed`; select
   the replacement span in the viewer and use Reattach instead of guessing.

## Review Data

The HTML file is the review artifact passed between people. Running `distill.py`
also writes `<doc>.notes.json`, a git-friendly ledger with the document hash,
notes, and extraction time. Commit sidecars when review history belongs in the
repository.

Parallel reviews merge without overwriting one another:

```sh
python3 merge-ledgers.py reviewer-a.notes.json reviewer-b.notes.json \
  --out plan.notes.json --view plan-view.html
```

The merge accepts only sidecars for the same Markdown snapshot. Independent notes
are preserved, shared threads union by entry ID, and a note remains open until all
copies resolve it.

## Agent Skills

Marginalia is a set of agent skills packaged as a Claude Code plugin. The same
canonical skill folders also install directly into Codex:

```sh
./scripts/install-agent-skills.sh
```

The installer creates symlinks and refuses to replace an existing local skill.
Restart the relevant agent after installation.

| Agent | Installed form | Commands |
| --- | --- | --- |
| Claude Code | Local `marginalia` plugin | `/margin-send`, `/margin-collect`, `/margin-merge` |
| Codex | Direct local skills | `margin-send`, `margin-collect`, `margin-merge` |

For a one-off Claude Code session without installation:

```sh
claude --plugin-dir "$PWD"
```

## Browser Behaviour

The viewer follows the operating-system theme by default and remembers a manual
theme choice. It autosaves locally, warns before closing with unsaved work, and
supports `Cmd+S`.

Chromium’s File System Access API controls in-place saving. The browser chooses
the first-save folder, but after the view is armed with its own file handle, later
saves write directly back to that file. The viewer cannot override Chromium’s
folder-picker policy.

## Repository Layout

```text
build-view.py       bake Markdown into a standalone viewer
template.html       viewer UI and embedded client logic
distill.py          digest, packet, staleness, and sidecar output
merge-ledgers.py    merge parallel sidecars safely
margin_anchor.py    quote anchoring and Markdown source mapping
skills/             send, collect, and merge workflows for agents
samples/            maintained Markdown example
tests/              Python and Node verification
```

## Verification

```sh
python3 -m pytest tests/
node --test tests/*.mjs
```
