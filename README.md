# RevenuePilot AI

Punct unic de reluare: [PROGRESS.md](PROGRESS.md). Execută un singur pas autorizat per sesiune și oprește-te la final.

## Surse canonice
- [Meta-prompt V3 — PDF](docs/canonical/RevenuePilot_AI_META_PROMPT_CONSTRUCTIE_V3.pdf) · [text extras](docs/canonical/RevenuePilot_AI_META_PROMPT_CONSTRUCTIE_V3.txt)
- [Plan V3 — PDF](docs/canonical/RevenuePilot_AI_PLAN_CONSTRUCTIE_GITHUB_V3.pdf) · [text extras](docs/canonical/RevenuePilot_AI_PLAN_CONSTRUCTIE_GITHUB_V3.txt)
- Hashuri: [SHA256SUMS](docs/canonical/SHA256SUMS)

## Progres și handoff
- [Index și status](PROGRESS.md)
- [Politică Git și review](GIT_POLICY.md)
- [Jurnal append-only de sesiuni](SESSION_LOG.md)
- [Jurnal append-only de decizii](DECISIONS.md)
- [Șablon handoff](SESSION_TEMPLATE.md)
- [Checkpoint PASUL 00](docs/step-00-initial-blocker.md)

Git păstrează codul și documentele, nu găzduiește aplicația sau baza de date runtime. Hostingul și cheile API comerciale nu sunt configurate. Nu modifica `fabrica-autonoma`.

## Propunere de arhitectură — PASUL 04

[Arhitectură și ADR-uri](docs/architecture/README.md) · [Predare pentru review](docs/architecture/handoff.md). Status DONE după review Claude; vezi PROGRESS pentru starea curentă.

## Verificări fără host — PASUL 05

[Contract și rezultate](docs/ci/step-05.md); workflowul este în `.github/workflows/step-05-documentation.yml`.

## Securitate — PASUL 07

[Model de amenințări și politici de acces](docs/security/README.md) · [Predare Claude](docs/security/handoff.md). REVIEW_PENDING; controalele runtime sunt propuse, nu implementate.
