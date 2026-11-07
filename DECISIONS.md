# Jurnal append-only de decizii

Adaugă decizii noi; nu șterge intrări anterioare.

## D00-1 — Crearea remote
Autor: Codex. GraphQL și REST au refuzat crearea repo-ului (HTTP 403); proprietarul a creat repository-ul privat. S-a verificat separat dreptul de push. Probe istorice: `docs/step-00-initial-blocker.md`.

## D00-2 — Proveniența surselor
Autor: Codex. Se păstrează PDF-urile originale, extragerile integrale și SHA-256; nu se copiază cod din alt proiect.

## D00-3 — README inițial
Autor: Codex la cererea utilizatorului. Commitul README inițial a fost păstrat în istorie și pagina completată prin PR.

## D01-1 — Un singur index
Autor: Codex; model selectat declarat de utilizator: GPT-6 Luna / Low. `PROGRESS.md` este punctul unic de intrare și status. `SESSION_LOG.md` și `DECISIONS.md` păstrează istoria append-only. Aceasta reduce riscul ca mai multe copii ale statusului să se contrazică.

## D01-2 — Identitate model
Autor: Codex; utilizatorul a confirmat Luna / Low. Se înregistrează selecția raportată de utilizator; dacă modelul runtime nu este verificabil, se spune explicit. Nu se inventează versiune sau efort.

## D01-3 — Usage
Autor: Codex la instrucțiunea utilizatorului. Usage-ul nu se urmărește și nu se deduce. Handoff-ul se actualizează la finalul sesiunii, fără prag procentual.