# PASUL 05 — verificări fără host

Autor: Codex; model/efort runtime neverificate. Bază: `b9607d23f8d16d52a1e7f8bfd27be377dd530499` (PASUL 04 DONE pe branch după re-review Claude). Branch: `step-05/ci-no-host`. Scope: verificări documentare reproductibile prin instrumentele disponibile; niciun modul de platformă, deployment sau API live.

Workflowul `.github/workflows/step-05-documentation.yml` rulează la push pe branchul pasului și la PR-urile ulterioare cu fișiere relevante. Permissions: `contents: read`; checkout pinned, job limitat la 5 minute. Nu primește secrete, nu instalează pachete, nu face deploy și nu apelează API comercial. Menține restricțiile de cost ale proiectului; consumul real GitHub Actions și limita contului se citesc din GitHub, nu se deduc din documentația generală.

Contractul verifică: SHA-256 ale PDF-urilor/textelor canonice, graful de importuri conceptual cu mutații negative, linkurile relative din index/arhitectură și whitespace pe commit. Acesta este un baseline de documentație. Nu există produs, deci build/lint/typecheck/unit/integration/UI/E2E de produs sunt NOT_RUN. CI nu validează tenant isolation, DB, worker sau security runtime. Mock/fixture nu sunt folosite; rezultatul este test local/CI documentar, separat de integrare/live.

Rulare locală reproductibilă din root:

```bash
(cd docs/canonical && sha256sum -c SHA256SUMS)
python3 -B -I docs/architecture/check_contract.py
python3 -B -I scripts/verify_docs.py
git diff --check HEAD^ HEAD
```

Pentru verdictul PASULUI 05, atașează ID/URL-ul jobului GitHub Actions și concluzia sa reală dacă rulează. Dacă GitHub nu pornește jobul ori conexiunea nu permite observarea, păstrează status BLOCKED și raportează doar rulările locale PASS. `main` este protejat; PR-urile anterioare #3–#6 încă sunt suprapuse în branchuri. Acest workflow se poate integra în main numai după review/merge în ordine. Nu susține CI pe main până atunci.
