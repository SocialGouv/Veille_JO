# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A French government (CEPS/DGOS) daily automation tool: each morning it reads the
Journal Officiel (JO) via the Légifrance PISTE API, finds texts about pharmaceutical
specialties (inscriptions, radiations, price changes, label changes, indication
extensions), consolidates them into one row per drug name + laboratory, and produces
an Excel file plus a pre-filled Outlook draft (or HTML fallback) — never sent
automatically. All user-facing docs, code comments, identifiers, and log messages are
in French; keep that convention when editing.

## Commands

Setup (macOS/Linux dev, from repo root):
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill PISTE_CLIENT_ID / PISTE_CLIENT_SECRET
```

Run the full pipeline for a given date (needs valid PISTE credentials in `.env`):
```bash
.venv/bin/python main.py --date 2026-05-28
```
With no `--date`, it uses `date.txt` (JJ-MM-AAAA) if present/valid, else today.

Check external connectivity (PISTE token + one live API call):
```bash
.venv/bin/python diagnostic.py
```

Run the full offline test suite (no network, no API key required) — from repo root:
```bash
python -m unittest discover -s tests -t tests
```
`-t tests` is required — `tests/` is not a package. ~154 tests, runs in well under a
second. Run a single test module/case/method the normal unittest way, e.g.:
```bash
python -m unittest tests.test_rapprochement.TestConsolider.test_generique_multi_labos -t tests
```
(prefix `python -m unittest` invocations with `-t tests` or run from repo root with
`tests.<module>` dotted paths as above).

Offline non-regression recipe (regenerates the 2026-05-28 case from a fixture and
diffs it against the historical target file):
```bash
.venv/bin/python tests/generer_depuis_fixture.py
.venv/bin/python tests/compare_cible.py sorties/veille_jo_2026-05-28.xlsx tests/fixtures/veille_jo_2026-05-28_CIBLE.xlsx
```

There is no linter/formatter/type-checker configured in this repo — don't invent one.

## Pipeline architecture

`main.py` orchestrates a strictly linear, deterministic pipeline (no LLM/heuristic
guessing anywhere — every ambiguous case is surfaced as "à vérifier" / "à compléter
manuellement" rather than inferred):

1. **`extraction.py`** (`ClientPiste`) — OAuth2 token → `lastNJo` (find the JO
   container for the target date) → `jorfCont` (summary tree) → `jorf` (full text per
   `JORFTEXT` id). Retries with backoff (`config.TENTATIVES_PISTE`), raises
   `ErreurPiste` on definitive failure.
2. **`filtrage.py`** — keeps only texts whose *title* matches `config.MOTS_CLES`
   keywords (case-insensitive substring match). Logs both kept and discarded texts.
3. **`analyse.py`** — the only place raw text is parsed: strips visas/considérants,
   extracts HTML tables separately, classifies each text by title regex
   (`config.MOTIFS_CLASSIFICATION`) then refines by body content (e.g. an
   "inscription"-titled arrêté whose body says "sont radiées" is reclassified as a
   radiation), extracts denominations/labs/CIP/PPTTC/participation rate per table row,
   and copies the indication text verbatim from the section preceding each table.
   Price amounts are parsed but **never displayed** — only used internally for
   `referentiel_prix` comparison.
4. **`referentiel_prix.py`** (`ReferentielPrix`, optional — gated by
   `config.ORIENTATION_PRIX_AUTO`) — orients "neutral" price notices (that don't say
   hausse/baisse) by comparing the published PPTTC against a prior known price, first
   from the local run history (`donnees/historique_prix.csv`), then from a cached BDPM
   public reference file (`donnees/CIS_CIP_bdpm.txt`, refreshed at most every
   `config.BDPM_MAX_AGE_JOURS` days). Any failure here is non-fatal — the affected
   rows just stay "à vérifier".
5. **`rapprochement.py`** (`consolider`) — the core business-rules module. Merges all
   analyzed texts into **one row per (normalized drug root name, mapped laboratory)**
   across the 6 output sections (Nouvelles inscriptions, Hausse de prix, Baisse de
   prix, Modification de libellé, Extensions d'indications, Radiations). Cross-text
   matching is done via CIP/UCD product codes, never by trusting name spelling alone,
   because the same drug is often spelled differently across texts published the same
   day. Name normalization (root name, dosage/packaging stripping, salt/ester
   stripping) lives in `config.FORMES_GALENIQUES` / `config.SELS_ET_ESTERS`;
   laboratory name mapping lives in `config.MAPPING_LABOS` (longest-key-wins, order in
   the dict doesn't matter — sorted by key length at lookup time).
6. **`export.py`** — writes the Excel workbook (openpyxl) matching the historical
   `tests/fixtures/veille_jo_2026-05-28_CIBLE.xlsx` layout (data starts at cell B2,
   rate column is a numeric `0%`-formatted cell carrying a hyperlink, not a string).
7. **`notification.py`** — builds the HTML mail body from the consolidated data
   (never by re-reading the Excel) and delivers it per `config.MAIL_MODE`:
   `"brouillon_outlook"` (COM automation via `pywin32`, inserts before the existing
   Outlook signature, attaches the day's Excel, `.Display()` only — `.Send()` is
   gated by `config.ENVOI_AUTOMATIQUE`, which defaults to `False`) or `"html"`
   (writes `sorties/corps_mail_<date>.html` and opens it in a browser). The HTML file
   is always written regardless of mode, as a permanent fallback trace.

`main.executer(date_cible)` runs steps 1–7 end to end and always returns 0 (success,
including a no-relevant-texts "RAS" day) or 1 (failure — PISTE unreachable or an
unexpected exception), which the Windows scheduled task uses to decide whether to
retry. **No mail ever means a failure** — a day with nothing to report still sends a
"RAS" mail; this invariant is deliberate and shows up throughout the tests.

## Key invariants (do not casually change)

- **Never emit numeric prices anywhere** in the output (mail or Excel) — Prix/Lien
  cells are always a link-only "Site LégiFrance" text (contract decided 23/07/2026,
  see `rapprochement.py` module docstring). The participation rate (Taux), by
  contrast, *is* shown as a percentage.
- **Nothing is ever auto-sent**: `ENVOI_AUTOMATIQUE` must stay `False` unless a human
  explicitly changes it after a trust period; don't add code paths that call
  `.Send()` unconditionally.
- Ambiguity is always surfaced, never silently resolved: look for the
  `"(à vérifier)"` / `"à compléter manuellement"` conventions in `rapprochement.py`
  and `analyse.py` before "fixing" a case that looks like a gap — it may be
  intentional per `TESTS.md`.
- `config.py` is the single place for all tunables, keyword lists, and mapping
  tables (`MOTS_CLES`, `MOTIFS_CLASSIFICATION`, `MOTIFS_LISTES`,
  `FORMES_GALENIQUES`, `SELS_ET_ESTERS`, `MAPPING_LABOS`); secrets never go here —
  they live only in `.env` (`PISTE_CLIENT_ID` / `PISTE_CLIENT_SECRET`), loaded via
  `python-dotenv`. Each config entry is expected to carry a dated comment explaining
  which real JO issue justified it — keep that convention when adding entries.
- `date.txt` at the repo root is the non-technical "replay a different day" UI: it's
  read once per run, then its content is cleared (never deleted) at the end of
  every run regardless of success/failure, per `main.vider_fichier_date`.
- [TESTS.md](TESTS.md) is the authoritative business-behavior checklist (with real
  JO dates as regression references, 🤖 = covered by an automated test, 📅 = verified
  via a real-date replay, ⚠ = known, deliberately-unfixed defect). Consult it before
  changing behavior in `analyse.py` or `rapprochement.py` — many edge cases encode a
  specific past incident.

## Publication GitHub Pages (CI)

`.github/workflows/publier-pages.yml` runs `main.py` daily (cron, plus manual
`workflow_dispatch`) on a Linux GitHub Actions runner and republishes the day's output
to the `gh-pages` branch as a static site (`archive/<date>.html`/`.xlsx` + a regenerated
`index.html`). `scripts/publier_page.py` is the glue: it does **not** duplicate
`main.py`'s date-resolution logic, it just globs whatever dated file `main.py` already
wrote to `sorties/` for the run that just happened (`corps_mail_<date>.html`, or
`alerte_<date>.html` on failure) plus `veille_jo_<date>.xlsx` if present. If you rename
any of these three output filename patterns in `notification.py`/`export.py`, update
`scripts/publier_page.py`'s glob patterns in the same change — nothing else checks that
this contract still holds.

## Tests

- `tests/` is not a package (no `__init__.py`); always invoke with `-t tests`.
- `tests/fixtures/fixture_annexe_e.py` and `veille_jo_2026-05-28_CIBLE.xlsx` are the
  canonical real-world regression fixture (JO du 28/05/2026); `tests/compare_cible.py`
  is the diffing tool used to validate output against it (strict volet vs.
  human-review volet — see its module docstring for what is and isn't compared).
- `tests/test_orchestration.py` mocks PISTE and the export/notify steps to test
  `main.executer` pipeline wiring without any I/O.
- Everything else in `tests/` is unit-level per module (`test_analyse.py`,
  `test_filtrage.py`, `test_rapprochement.py`, `test_referentiel_prix.py`,
  `test_export_compare.py`, `test_notification.py`, `test_date_fichier.py`).
