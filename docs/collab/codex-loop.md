# Bucla Claude + Codex (politică de lucru)

Autor: Claude Sonnet 5.5, la instrucțiunile proprietarului (2026-11-07). Decizia formală: D11-2 în [DECISIONS.md](../../DECISIONS.md).

## Rolurile
- **Claude** orchestrează și implementează. Pentru pașii de clasă H cere sfatul `advisor` (Opus 5.5) înainte de a scrie codul și înainte de a declara pasul gata.
- **Codex** (ChatGPT Plus al proprietarului, CLI în containerul sesiunii Claude) face **doar** review-urile independente cerute de plan: pașii de clasă H și re-review-urile lor. Pentru clasele M, T, L planul nu cere review independent, deci nu se consumă Codex.
- Cota Codex se termină mult mai repede decât cea Claude: un apel de review per pas, pachet precompilat, fără explorare liberă.

## Limita de independență (obligatorie)
`advisor` este același model-familie cu Claude. **Nu înlocuiește niciodată** review-ul independent din familia opusă cerut la clasa H. Fără review Codex real, pasul H rămâne REVIEW_PENDING, indiferent de sfatul advisor-ului. Când Codex este pornit de Claude (nu într-o sesiune Codex separată), asta se declară în raport: independența constă în modelul diferit, nu în orchestrator diferit.

## Modele Codex per clasă (slug-uri din `~/.codex/models_cache.json`)
| Clasă | Model | Efort |
|---|---|---|
| H | `gpt-6-astra` | medium (nu high, pentru cotă) |
| M+ / M | `gpt-6.1-sol` | medium |
| T | `gpt-6.1-terra` | medium |
| L | `gpt-6-luna` | low |

## Procedura unui review Codex
1. `git status` curat; HEAD local = HEAD de pe origin pentru SHA-ul revizuit; SHA-ul din verdict este cel revizuit efectiv.
2. Pachet precompilat într-un fișier: diff-ul relevant, constatările anterioare, documentul de remediere, ce se cere (doar remedierile + regresii; rulează doar suita de teste; nu re-citește tot repo-ul).
3. `codex exec --cd <repo> --ephemeral --sandbox read-only -m <model> -c model_reasoning_effort="<efort>"`, stdout redirecționat într-un fișier (verdictul nu se pierde și nu se reapelează).
4. **Promptul exact trimis lui Codex se salvează în repo lângă verdict** (dovada gradului de independență).
5. La mesaj „usage limit … try again at HH:MM”: se reprogramează la acea oră plus câteva minute, nu la intervale fixe.
6. Dacă `codex` lipsește (container nou): `npm install -g @openai/codex@0.167.0`; dacă login-ul s-a pierdut, se cere proprietarului un cod nou (`codex login --device-auth`).

## Autorizări active ale proprietarului
Pași înlănțuiți fără confirmări (un pas la rând, cu dovezi; clasa H doar cu review real), merge după verificări locale (D10-2), Codex din containerul Claude cu abonamentul propriu. Nu acoperă costuri, secrete sau modificarea documentelor canonice.
