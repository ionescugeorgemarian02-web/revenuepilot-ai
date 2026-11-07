# Remediere R11 — răspuns Claude la review-ul Codex

Autor: Claude Opus 5.5. Data: 2026-11-07. Review: [review-codex.md](review-codex.md) pe `eaa99e0`, verdict CHANGES_REQUESTED. Raportul Codex nu a fost modificat. Status după remediere: **REVIEW_PENDING** — re-review Codex pe noul SHA necesar înainte de DONE/merge.

| ID | Remediere | Dovadă |
|---|---|---|
| R11-1 P1 | `update` validează toate câmpurile în variabile temporare, apoi aplică titlul, corpul, versiunea și anularea aprobării împreună, sub lock. Update fără niciun câmp → 400. | `test_r11_1_rejected_update_changes_nothing`: 4 update-uri invalide lasă obiectul aprobat identic; update valid → draft, v2. Eșuează pe `eaa99e0`. |
| R11-2 P1 | Regulă unică: niciun serviciu nu apelează celălalt serviciu ținând propriul lock. `login`/`switch_organization` construiesc principalul după eliberarea lock-ului auth; `add_member` verifică `user_exists` înainte de lock-ul tenancy. | `test_r11_2_single_lock_order_between_services` (aserțiuni că lock-ul celuilalt serviciu nu e ținut) și `test_r11_2_interleaving_login_and_add_member_completes` (intercalarea exactă din proba Codex). Pe `eaa99e0`: blocat după 10 s → FAIL; acum PASS. |
| R11-3 P2 | Un singur eveniment de audit per operație, înregistrat la final (`_decision`): `allow` doar la reușită; altfel codul primit de client (`not_found` identic pentru absent/invizibil, `not_owner`, `last_admin`, `invalid_request` etc.). Fără conținut. | `test_r11_3_final_decision_is_audited`: 6 cazuri, exact o decizie fiecare, niciun allow fals. Eșuează pe `eaa99e0`. |
| R11-4 P2 | Validare explicită de tip pentru `kind`, `title`, `body`, `visibility`, `parent_id`, `role`, `user_id`, `query`, înainte de lookup. Plasă finală în handler: 500 `internal_error` (nu 400), în loc de conexiune închisă. | `test_r11_4_wrong_json_types_rejected_by_service` (6 valori × 10 câmpuri) și `test_r11_4_wrong_json_types_return_400_not_disconnect` (HTTP, cu control pozitiv). Eșuează pe `eaa99e0`. |

Răspunsuri la observațiile fără blocaj:
- Q2 (switch în paralel cu eliminarea): acum switch-ul răspunde explicit 403 dacă membership-ul dispare în timpul rotirii. Tokenul vechi e deja invalidat, deci clientul trebuie să se autentifice din nou (fail closed).
- Q5 (granturi după retrogradarea proprietarului): documentat — retrogradarea **nu** revocă granturile deja emise; eliminarea beneficiarului le retrage. Revocarea individuală nu există încă.
- C11-1 (audit nelimitat în memorie): rămâne risc rezidual mediu, nerezolvat aici; înainte de expunere: plafon, comportament la saturare, audit durabil (pasul 13).

Verificări locale (D10-2): 40 teste PASS pe Python 3.12 și 3.13; cele 6 teste noi verificate că eșuează pe `eaa99e0` (5 direct; testul de intercalare după forțarea ordinii, la fel ca proba Codex). `docs/tenancy/review-probes.py` afirmă comportamentul defect al `eaa99e0`, deci acum se oprește la prima aserțiune (R11-1) — este așteptat, nu o regresie. CI remote NOT_RUN.

Corecție proprie: prima versiune a testului de intercalare trecea și pe codul vechi (ordinea thread-urilor nu era forțată și așteptarea expira); detectat prin rularea pe `eaa99e0`, corectat înainte de publicare.
