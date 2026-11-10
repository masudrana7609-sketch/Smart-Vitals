# Ethics, security, privacy and sustainability checklist (Output 3, LO3)

Go through this now, and again before you hand in. Each item needs a sentence in your report: what the risk is, and what your design does about it.

## Data protection (R5, R7)
- [x] No real patient data anywhere: simulated, synthetic or open and anonymised only. *(`data/DATA_CARD.md`)*
- [ ] Health data is *special category* data under UK GDPR. Which principles would a real MedLink system have to meet (lawful basis, data minimisation, storage limitation, security)?
- [ ] Do I collect only the data the system needs?
- [x] How long are readings and alerts kept, and who can delete them? *(30 days and 1 year, deleted automatically and audited: `app/retention.py`)*

## Security (R5)
- [x] Clinicians log in, and can see only their own patients. A patient view shows only that patient. Tested? *(T4, T18; no patient view built)*
- [x] Passwords are stored hashed, never in plain text; keys live in `.env`, not in the repository. *(argon2; the API refuses a placeholder SECRET_KEY)*
- [ ] Traffic between parts is encrypted (HTTPS, MQTT over TLS), or I explain why not in a prototype. *(not yet: explained in ADR 8; broker and database are on an internal network and need logins)*
- [x] Is there a log of who viewed or changed what? *(audit log, ADR 6)*
- [ ] Where could someone attack the system: the feed, the API, the model, the dashboard? (Week 10)

## Safety and fairness
- [ ] Missed Critical (no alert) versus false alarm (alarm fatigue): which does my design favour, and why?
- [x] Does the model work as well for every risk group, and for patients with and without diabetes? *(notebook 03, `docs/results/fairness.md`)*
- [ ] Does the clinician see how sure the model is, and why it raised an alert? The clinician, not the model, decides.
- [ ] Does my report say clearly that this is a prototype, not a medical device?

## Sustainability and society
- [x] Roughly how much computing do training and running my system use? Could the edge, a smaller model or less frequent retraining do the job (Weeks 6 and 7)? *(`docs/results/edge_cloud.md`; training model v2 takes about 2 s)*
- [ ] Who could be left out: patients without a smartphone, good signal or digital skills?
- [ ] Have I declared where and how I used AI tools?
