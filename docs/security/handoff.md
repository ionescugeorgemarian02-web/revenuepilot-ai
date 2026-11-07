# Predare PASUL 07 către Claude

- Autor: Codex; modelul/efortul runtime neverificate. Nu se urmărește usage, conform instrucțiunii utilizatorului.
- Bază: `63ac761c0fb972d10592bdd38a3335c23a4312e8` (`main`, pașii 00–06 integrați); branch `step-07/threat-model`.
- Stare țintă a livrării: REVIEW_PENDING. Scopul autorului este documentarea completă a 07; 08 nu a fost început. Nu există module, host ori chei API noi.
- Fișiere de examinat: [modelul](README.md), [18 amenințări](threat-register.md), [politicile](access-policies.md), [probe/limite](verification.md), indexul și intrările S07/D07-1.

## Instrucțiuni de reluare

Fetch și checkout branch; verifică SHA-ul curent și worktree, apoi [PROGRESS](../../PROGRESS.md) și planul canonic. Nu prelua vechea afirmație că main are numai 00–01. Review recomandat: **Claude Opus 5.5 / High**, familie diferită de autor. Review-ul trebuie să fie scris de reviewer, cu SHA-ul exact, probele efectiv rulate și APPROVED sau CHANGES_REQUESTED; fișier recomandat `docs/security/review-claude.md` (încă inexistent). Nu există aici un review Claude substituit de Codex.

Verifică în special: cursele revocare/STOP/dispatch și rezervarea atomică; DNS rebinding și redirect; izolare browser/parser; tenant în DB/cache/queue/memorie; credențiale OAuth; granturile anticipate finite; independența ledgerului de ștergere; gate-urile Git și supply chain. Verifică dacă fiecare oracle negativ poate fi implementat și dacă un control pozitiv împiedică acceptarea unui produs care respinge tot.

Rulează comenzile din [verification](verification.md); examinează diff-ul față de baza `63ac761` și ultimul rezultat CI pentru HEAD. Dacă apar defecte, adaugă R07-n și CHANGES_REQUESTED, cu remediere verificabilă; păstrează istoricul autorului. Dacă aprobă și check-urile pentru HEAD sunt verzi, integrează prin PR conform permisiunilor GitHub, fără cerere repetată către proprietar. Nu elimina protecții pentru a simula îndeplinirea review-ului. Consemnează SHA merge și marchează DONE numai după criteriile îndeplinite.

Lipsa reviewerului este limita curentă pentru DONE, nu lipsa acordului utilizatorului. În această sesiune nu există un instrument disponibil de apelare Claude; predarea persistă în Git. După închiderea 07, 08 este eligibil (depinde de **05 și 07**, conform planului PDF); recomandare GPT-6.1 Sol / Medium sau Claude Sonnet 5.5 / Medium. STOP în sesiunea 07, fără implementare 08.
