# AGENTS.md — Prospectus Automation (PA)

## Project rules
- One branch: main
- Never commit secrets. Use .env locally; commit only .env.example
- Never invent issuer/offering facts. If unknown, write TBD or [[MISSING: field]]

## App goals
Streamlit app with 3 tabs:
1) YOUR PROSPECTUS (upload/version/preview/lock)
2) TEMPLATES (template library CRUD + preview)
3) AUTO GENERATION (validated inputs + assembly + generation runs)

## Source docs
- docs/Master Prompt - Prospectus Automation.docx
- docs/Understanding Securities Prospectus Structure.docx
- docs/UI_SKETCH.pdf
- reference/*.pdf
