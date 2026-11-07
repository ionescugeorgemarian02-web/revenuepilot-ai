# Politica Git și review — PASUL 02

Repository autorizat: `ionescugeorgemarian02-web/revenuepilot-ai`. `main` este sursa de integrare; se lucrează pe un branch per pas, `step-NN/scop-scurt`, cu un singur autor principal. Niciodată nu scrie în fabrica-autonoma și nu include secrete.

## Revendicare și predare

1. `git fetch origin`; confirmă URL, `origin/main`, HEAD, status curat, jurnalul și PR-urile deschise. Dacă există muncă în progres pentru același pas, nu crea o revendicare concurentă.
2. Înregistrează în `PROGRESS.md` sau într-un document al pasului ID, autor real, rol/model declarat, branch, commit de bază, scop, oră UTC și expirare lease. Creează branchul din `origin/main`; push și PR draft fac revendicarea vizibilă. Revendicarea în document nu este un lock atomic: dacă apar două revendicări, ambele sesiuni se opresc și coordonează cu proprietarul; nicio sesiune nu suprascrie cealaltă.
3. La predare, înregistrează schimbările, testele efective PASS/FAIL/NOT_RUN, defectele, commitul, review-ul și pasul următor. Nu inventa review sau rezultate. Când lease-ul expiră, verifică PR/branch și cere clarificare dacă există activitate; expirarea nu autorizează ștergerea ori preluarea automată.

## Commit și PR

Commituri mici, imperative, cu ID pas (ex. `docs(step-02): define review policy`). Fiecare pas folosește PR spre `main` cu scop, criterii, bază, verificări, limitări și dovezi. Review-ul examinează diff-ul și testele; la pași critici autorul și reviewerul sunt din familii diferite. Fără review necesar, rămâne `REVIEW_PENDING`; autorul nu aprobă în numele altui model. PR-ul nu se integrează până când review-ul cerut și verificările disponibile nu sunt satisfăcute. Proprietarul verifică și aprobă integrarea atunci când platforma nu poate impune protecția.

## Actualizare, conflict și revenire

Înainte de integrare actualizează `origin/main`, verifică dacă au apărut schimbări și reanalizează diff-ul; dacă un branch partajat necesită rebase, coordonează-l cu deținătorii. Nu folosi force-push; dacă rebase ar rescrie un branch public, folosește un branch nou sau merge al bazei și păstrează istoricul. Rezolvă conflictele cu context și consultă autorul când intenția este neclară; nu șterge istoricul jurnalelor. După rezolvare, rerulează verificările relevante. Rollback: `git revert` al commitului/merge-ului verificat, printr-un nou PR cu teste și motivație; nu rescrie main. Păstrează linkuri la PR, SHA, comenzi, rezultate, review, limitări și decizii în jurnal.

## Protecție și stare reală

La verificarea din PASUL 02, GitHub a raportat `main.protected=false`; GET pentru branch protection a returnat HTTP 403 `Resource not accessible by integration`. Un apel anterior pentru rulesets a returnat 403 cu solicitare GitHub Pro sau repository public. Drepturile și disponibilitatea de configurare efectivă nu sunt demonstrate. Regula de PR și review este procedurală; nu există dovadă că GitHub blochează push direct sau merge neanalizat. Nu marca drept verificată protecția automată. Nu cumpăra plan și nu schimba vizibilitatea. PASUL 02 rămâne BLOCKED până la protecție verificată sau la o soluție echivalentă efectiv demonstrată care împiedică modificări neanalizate.
