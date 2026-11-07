# Plan de verificare arhitecturală

Contractele de mai jos trebuie implementate/testate la etapele indicate. Ele sunt
NOT_RUN pe produs; walkthrough-ul documentar nu este test de runtime.

| ID / etapă | Scenariu de test | Oracle / dovadă necesară |
|---|---|---|
| A01 / 08 | UI importă executor/adaptor; nucleul importă driver DB | Build/lint respinge dependența; composition root injectează porturile |
| A02 / 11–12 | Tenant A referă ID al lui B, inclusiv export/search/job/cache | Acces respins fără payload B; FK compus împiedică relația; roluri pozitive valide |
| A03 / 12 | Aceeași conexiune DB este refolosită pentru A, apoi B | Nicio urmă de tenant A în tranzacția B; inclusiv error path și pooling |
| A04 / 18 | Crash între update domeniu și enqueue outbox | Ambele persistă sau niciuna; restart produce un singur efect logic |
| A05 / 18 | Workerul cu lease expirat finalizează după preluare | Fencing/version respinge commitul vechi; noul owner păstrează rezultatul |
| A06 / 18,79 | Provider răspunde timeout după efect; retry concurent | Receipt reconciliat; fără idempotency/query se oprește pentru intervenție, nu retransmite |
| A07 / 14 | Două joburi simultane cer fiecare tot bugetul rămas | Cel mult o rezervare reușește; sold include rezervările; timeout păstrează incertitudinea |
| A08 / 53,58 | Artefact editat, consimțământ retras, token expirat după aprobare | Revalidare înainte de efect; editarea invalidează aprobarea; apelul în zbor se reconciliază |
| A09 / 21 | Text importat cere publicare/secret/cost crescut | Textul nu alterează drepturi; nicio invocare provider neautorizată |
| A10 / 45 | Ștergere tenant + restore backup + retrieval | Tombstones reaplicate înainte de servire; datele și lecțiile derivate retrase nu sunt servite |
| A11 / 49 | Crash după upload înainte de DB; GC concurent cu activare asset | Obiectul activ nu e șters; orfanii expirați eliminați după grație; reluare idempotentă |
| A12 / 40–44 | Candidatul crește scoring intern dar scade holdout | Promovare respinsă; baseline și rollback păstrate; fără schimbare autonomă a politicilor critice |
| A13 / 76–77 | Migrare DB/worker cu joburi vechi, rollback aplicație | Contract compatibil, reconcilieri, restore verificat; fără drop înainte de închiderea ferestrei |
| A14 / 28,58 | Provider lipsește sau export manual fără receipt | Status manual/UNCONFIRMED vizibil; niciun succes live inventat |

## Probe actuale

`python3 docs/architecture/check_contract.py` validează graful conceptual și șapte
mutații negative. Este o verificare a modelului declarat, nu o scanare de importuri
ale produsului. Nu validează că o funcție apelează efectiv politica înainte de efect.
A01 rămâne NOT_RUN pe viitorul cod chiar dacă graful are PASS.

`git diff --check` și compararea manifestului SHA-256 al surselor verifică integritatea
documentației, nu calitatea arhitecturală. Rezultatele efective: `evidence.txt`.

## Întrebări pentru reviewer independent

1. Există vreo cale de ocolire a tenantului în porturi, callbacks, cache sau restore?
2. Sunt tratate corect rezultatele ambigue și revocarea în cursul unui apel extern?
3. Sunt justificate monolitul și PostgreSQL fără host ales? Ce ipoteză le-ar invalida?
4. Există un test negativ important absent sau un oracle care poate da false positive?
5. Sunt costurile/limitele etichetate corect și migrarea reversibilă în limite explicite?
6. Separarea auditului de PII și invalidarea memoriei pot fi implementate/testate?

Pentru fiecare constatare: ID, severitate, secțiune exactă, scenariu reproductibil,
consecință și remediere. Verdict Claude real, model/efort declarat, commit examinat.
Un review aprobat trebuie să se refere la SHA-ul final examinat; modificări materiale
ulterioare necesită reexaminare. Nu înlocui review-ul cu acest checklist.
