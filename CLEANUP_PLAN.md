# Cleanup Plan for Public Release

> Generated: 2026-02-08 | Branch: `version-7`
>
> **Repository stats**: 3,692 tracked files totaling 67 MB, of which ~64 MB is generated/ephemeral data. Actual source code is ~3 MB.

---

## P0 - Critical (Do Before Any Public Push)

### 1. Revoke Exposed API Keys

The `.env` file contains **real API keys** that are tracked in git history:

| Key | File | Pattern |
|-----|------|---------|
| Anthropic API Key (x2) | `.env` | `sk-ant-api03-...` |
| Google Gemini API Key | `.env` | `AIzaSy...` |
| OpenAI API Key | `.env` | `sk-proj-...` |

**Actions:**
- [ ] Immediately revoke all four keys via their respective provider dashboards
- [ ] Verify `.env` is in `.gitignore` (it is, but was committed before the ignore rule)
- [ ] Remove `.env` from git tracking: `git rm --cached .env`
- [ ] Purge `.env` from git history using `git filter-repo` (keys persist in history even after removal)

### 2. Purge Secrets from Git History

Even after removing files, secrets remain in all historical commits. Before making the repo public:

- [ ] Run `git filter-repo --path .env --invert-paths` to strip `.env` from all history
- [ ] Force-push rewritten history (coordinate with all collaborators)
- [ ] Alternatively: create a fresh repo with a squashed initial commit

---

## P1 - High Priority (Repository Bloat)

### 3. Remove `logs/` from Tracking (37.65 MB, 1,234 files)

Benchmark run logs with incremental `summary_step_*.json` snapshots.

- [ ] Add `logs/` to `.gitignore`
- [ ] `git rm -r --cached logs/`

### 4. Remove `results/` from Tracking (18.67 MB, 64 files)

Benchmark result JSON files up to 1 MB each.

- [ ] Add `results/` to `.gitignore`
- [ ] `git rm -r --cached results/`
- [ ] Keep a representative example in `examples/` or document how to reproduce

### 5. Remove Generated `workflows/` from Tracking (5.19 MB, 2,162 files)

All generated workflow artifacts from benchmark runs. These are reproducible compiled outputs.

- [ ] Add `workflows/` to `.gitignore` (or `workflows/*/` to keep the directory)
- [ ] `git rm -r --cached workflows/`
- [ ] Keep 1-2 curated example workflows in an `examples/` directory

### 6. Remove `paper/*.pdf` from Tracking (~2.7 MB, 6 versions)

Multiple versions of the arXiv paper as binary PDFs. Binary files don't benefit from git delta compression.

- [ ] Add `*.pdf` to `.gitignore`
- [ ] `git rm --cached paper/*.pdf`
- [ ] Link to the paper on arXiv in README instead, or attach to a GitHub Release

### 7. Remove `.pr-review-temp/` (Tracked Temp Files)

Internal PR review artifacts accidentally committed.

- [ ] Add `.pr-review-temp/` to `.gitignore`
- [ ] `git rm -r --cached .pr-review-temp/`

---

## P2 - Medium Priority (Git Hygiene)

### 8. Delete Merged Remote Branches (15 branches)

These are all merged into `origin/main` and serve no purpose:

```
origin/LLM-Baseline
origin/add-logs-data
origin/add-external-datasets
origin/baseline-bench
origin/add-code-factory-framework
origin/add-security-validators
origin/analytics-target-most-recent-benchmark
origin/code-quality
origin/nanosecond
origin/remove-custom-semgrep
origin/add-security-section-paper
origin/external_benchmarks_baselines
origin/feature/crush-integration
origin/merging-all-branches
origin/add-code-gate-flag
```

- [ ] Delete all with: `git push origin --delete <branch-name>` (or batch)
- [ ] Delete local merged branch: `git branch -d feature/crush-integration`

### 9. Review Unmerged Branches

These are NOT merged and need owner decisions:

| Branch | Age | Action Needed |
|--------|-----|---------------|
| `benchmarks-research` | 12 days | Merge or delete? |
| `human-coding-benchmarks` | 11 days | Merge or delete? |
| `walter-feedback` | 14 days | Merge or delete? |
| `update-security-part` | 6 days | Possibly in progress |
| `version-7` | Current | Same commit as `feature/crush-integration` - use a git tag instead? |

### 10. Update Local `main`

Local `main` is 7 commits behind remote.

- [ ] `git checkout main && git pull`

### 11. Review Security Test Workflows

`workflows/code_gate_test_*` directories contain intentionally vulnerable code (hardcoded credentials, SQL injection, XXE, etc.) for testing CodeGate detection.

- [ ] Decide: keep for demonstrating security validation, or move to a separate test-data repo?
- [ ] If keeping, add a clear `README.md` in the directory explaining these are intentional test fixtures
- [ ] Review `workflows/code_gate_test_hardcoded_creds/activities.py` for overly realistic credential patterns

---

## P3 - Documentation (Public Release Readiness)

### 12. Fix README.md Placeholder URL

```
git clone https://github.com/your-org/CompiledAI.git
```

- [ ] Replace `your-org` with actual GitHub organization name

### 13. Add Missing Standard Files

| File | Priority | Notes |
|------|----------|-------|
| `CONTRIBUTING.md` | Required | Contribution guidelines, dev setup, PR process |
| `CHANGELOG.md` | Strongly recommended | Version history (v1-v7 exist in commits) |
| `CODE_OF_CONDUCT.md` | Recommended | Community guidelines |

### 14. Add GitHub Community Files

- [ ] Create `.github/ISSUE_TEMPLATE/bug_report.md`
- [ ] Create `.github/ISSUE_TEMPLATE/feature_request.md`
- [ ] Create `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] Create `.github/workflows/ci.yml` (tests, linting, type checking)

### 15. Complete `pyproject.toml` Metadata

Currently missing project URLs:

- [ ] Add `homepage`
- [ ] Add `repository`
- [ ] Add `documentation`
- [ ] Add `issues` / bug tracker URL

### 16. Resolve Source Code TODOs

Open TODOs that reference incomplete work:

| File | Line | TODO |
|------|------|------|
| `src/compiled_ai/factory/code_factory/factory.py` | 1630 | `Track which templates were used` |
| `src/compiled_ai/metrics/consistency.py` | 117 | `Implement proper semantic clustering` |

- [ ] Implement or remove before release

---

## P4 - Nice to Have

### 17. Add CI Badges to README

- [ ] Build status badge
- [ ] Test coverage badge
- [ ] PyPI version badge (if publishing)

### 18. Create a `docs/` Directory

- [ ] Architecture deep-dive
- [ ] Tutorial: "Your First Compiled Workflow"
- [ ] API reference (consider Sphinx / pdoc)

### 19. Add More Code Examples

- [ ] Python usage examples (beyond YAML workflows)
- [ ] Create an `examples/` directory with curated, documented examples

### 20. Consider Git LFS for Datasets

Large JSON datasets in history (`BFCL_v3_live_multiple.json` at 3.89 MB, `swebench_lite.json` at 3.71 MB):

- [ ] Evaluate migrating `datasets/` to Git LFS if the repo will include them
- [ ] Or provide download scripts only (current approach for some datasets)

---

## .gitignore Additions Summary

Add these entries to `.gitignore`:

```gitignore
# Generated artifacts
logs/
results/
workflows/

# Binary documents
*.pdf

# Temporary/review files
.pr-review-temp/

# Crush benchmark logs
.crush/
```

---

## Quick Reference: Cleanup Commands

```bash
# 1. Remove tracked files that should be ignored
git rm -r --cached logs/ results/ workflows/ .pr-review-temp/ paper/*.pdf .env

# 2. Update .gitignore (edit manually with entries above)

# 3. Commit the cleanup
git add .gitignore
git commit -m "chore: remove generated artifacts and update .gitignore for public release"

# 4. Purge secrets from history (DESTRUCTIVE - coordinate with team)
pip install git-filter-repo
git filter-repo --path .env --invert-paths

# 5. Delete merged remote branches
git push origin --delete LLM-Baseline add-logs-data add-external-datasets \
  baseline-bench add-code-factory-framework add-security-validators \
  analytics-target-most-recent-benchmark code-quality nanosecond \
  remove-custom-semgrep add-security-section-paper external_benchmarks_baselines \
  feature/crush-integration merging-all-branches add-code-gate-flag

# 6. Clean up local
git branch -d feature/crush-integration
git checkout main && git pull
```
