# DDXPlus Evidence Manual Review

Reviewed at: 2026-05-14

This note records the first manual review of DDXPlus respiratory, allergy, airway, swelling, hemoptysis, and chest-pain-pattern evidence.

## Policy

- DDXPlus is a review queue, not a design source of truth.
- No active API behavior changed in this review.
- No active red flag was added from DDXPlus.
- Do not add symptoms, contexts, candidates, or red flags only to improve train/validate/test metrics.
- Promotion requires user-facing UX value, safety need, existing rule-policy fit, official/public/specialist guidance, and tests.

Structured output:

- `health-navigator-backend/app/data/review/ddxplus_evidence_manual_review.json`

## Manual Decisions

| Evidence | Decision | Internal code | Status |
| --- | --- | --- | --- |
| `E_66` shortness of breath / difficulty breathing | Keep existing mapping | `shortness_of_breath` | already active symptom |
| `E_64` out of breath with minimal effort | Candidate context only | `severe_shortness_of_breath` | inactive |
| `E_194` high-pitched sound breathing in | Candidate context only | `wheezing_or_stridor` | inactive |
| `E_214` wheezing sound when exhaling | Candidate context only | `wheezing_or_stridor` | inactive |
| `E_112` wheeze/noisy breathing after coughing | Reject generic cough mapping | `wheezing_or_stridor` | inactive |
| `E_65` difficulty swallowing/blockage | Candidate context only | `difficulty_swallowing_or_drooling` | inactive |
| `E_42` contact/eating known allergen | Candidate context only | `known_allergen_exposure` | inactive |
| `E_12` known severe food allergy | History context only | `severe_food_allergy_history` | inactive |
| `E_151` generic swelling | Keep generic symptom review | `swelling` | generic only |
| `E_152` swelling location | Needs value-level review | `facial_lip_tongue_throat_swelling` | inactive |
| `E_45` coughing up blood | Reject generic cough mapping | `hemoptysis` | inactive |
| `E_14` chest pain at rest | Candidate context only | `rest_chest_pain` | inactive |
| `E_218` exertion worse, rest better | Candidate context only | `exertional_chest_pain_relieved_by_rest` | inactive |
| `E_220` pain worse with deep breath | Candidate context only | `pleuritic_chest_pain` | inactive |
| `E_13` progressive worsening with less effort | Candidate context only | `progressive_exertional_worsening` | inactive |

## Source Candidates

- CDC anaphylaxis guidance: https://www.cdc.gov/vaccines/covid-19/clinical-considerations/managing-anaphylaxis.html
- FDA food allergy guidance: https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/food-allergies
- NHS epiglottitis: https://www.nhs.uk/conditions/epiglottitis/
- CDC heart attack symptoms: https://www.cdc.gov/heart-disease/about/heart-attack.html
- NHS heart attack symptoms: https://www.nhs.uk/conditions/heart-attack/symptoms/
- NHS pulmonary embolism: https://www.nhs.uk/conditions/pulmonary-embolism/
- MedlinePlus pulmonary embolism: https://medlineplus.gov/pulmonaryembolism.html

## Next

- 2026-05-14 implementation note: the first minimal API exposure added `wheezing_or_stridor`, `known_allergen_exposure`, `facial_lip_tongue_throat_swelling`, and `hemoptysis` to `CONTEXT_OPTIONS` as `explanation_context` with `rule_strength: review`.
- 2026-05-14 implementation note: chest `context_chips` exposes `wheezing_or_stridor` and `hemoptysis` as `red_flag_context_not_standalone`.
- These codes do not activate red flags and do not change candidate scoring.
- Split `difficulty_swallowing_or_drooling` if UX needs swallowing difficulty and drooling as separate chips.
- For swelling location, map only airway/allergy-relevant values instead of generic swelling.
- Add tests that DDXPlus-reviewed candidates do not trigger red flags until explicit active rules are implemented.
