# Symptom Checker UI Integration TODO

Last updated: 2026-05-29

## Fixed Standards

These standards apply to every body region and every body part, not only chest.

1. The UI input order is: profile, major body region, body part, symptoms, context/follow-up questions, free text, result.
2. A symptom, context option, or follow-up option that already appeared in an earlier input section must not appear again in a later section.
3. `context_chips` and `follow_up_questions[].options[].maps_to_context` must be disjoint in the `context-guide` API response.
4. `quick_contexts` are global helpers. If a context is already covered by follow-up questions or body-part questions, the frontend should not render it again as a separate option.
5. Body-part-specific questions take priority over broad region-level questions when they exist.
6. If a body part has no hand-authored question set, the backend must generate compact follow-up questions from its scoped context codes so Flutter still receives a usable question structure.
7. Follow-up question count is capped. Current backend cap is 6 questions per context guide.
8. Safety and conditional questions are prioritized before ordinary candidate-support questions.
9. Options that map to the same context code are merged into one option label instead of being rendered as repeated options.
10. User-facing UI must not expose internal words such as `rule`, `RAG`, `Medical RAG`, `score`, `backend`, or `display_candidates`.
11. Rule candidates and Medical RAG candidates are merged into one user-facing `display_candidates` list, capped at Top 5.
12. Rule candidates are not always forced above RAG candidates. Final display rank uses the merged display score.
13. Gemini runs after candidate merging. It receives the final Top 5 candidate payload and writes the final result explanation.
14. Gemini may use symptoms and free text as evidence, but the screen input summary should show only major body region and body part to avoid repetition.
15. Medical visit/emergency/consultation advice must not repeat across summary, warnings, candidates, and next steps. Show it at most once.
16. The bottom notice must remain: `이 설명지는 정확한 진단이 아닌 참고용 정보입니다. 정확한 진단은 의료진 상담이 필요합니다.`
17. Health output must remain reference information, never diagnosis or prescription.
18. Age and registered gender are supporting evidence only. They must not create a disease candidate or red flag by themselves.
19. Review-only contexts can support explanation or active combinations, but must not trigger standalone red flags.
20. Every UI spec integration must be validated by tests, including no duplicate mapped contexts between chips and follow-up questions.

## Current Implementation Status

- Done: chest spec first pass for `upper_chest`, `sternum`, `rib_area`, and `breast`.
- Done: merged rule + Medical RAG `display_candidates` Top 5 response.
- Done: Gemini final explanation prompt and user-facing result layout rules.
- Done: backend-level dedupe between `context_chips` and `follow_up_questions`.
- Done: follow-up question option merging when several options map to one context.
- Done: all `SYMPTOM_CHECKER_*_UI_SPEC.md` files are now read as the source for body-part follow-up question wording when a matching spec section exists.
- Done: all selectable body parts return at least one follow-up question or context input.
- Done: all selectable body parts are connected to a UI spec section or compatible adjacent section.
- Done: all valid UI spec context codes are registered into `CONTEXT_OPTIONS`; symptom/body-region/body-part codes remain excluded so they do not appear twice.
- Done: weak or generic rule candidates are demoted in `display_candidates`, and Medical RAG candidates can outrank them when retrieval confidence is better.

## Resume TODO

If the session is interrupted, continue from this checklist.

1. Verify the current branch and do not switch/reset user changes.
2. Read this file first, then inspect `docs/SYMPTOM_CHECKER_*_UI_SPEC.md`.
3. Inspect `health-navigator-backend/app/services/symptom_checker_service.py` sections:
   - `CONTEXT_OPTIONS`
   - `BODY_PART_CONTEXT_CHIP_CODES`
   - `REGION_FOLLOW_UP_QUESTIONS`
   - `BODY_PART_FOLLOW_UP_QUESTIONS`
   - `get_context_guide`
   - `_dedupe_follow_up_questions_for_context`
4. Ensure every selectable body part remains connected in `UI_SPEC_BODY_PART_SECTIONS`.
5. Prefer exact UI spec wording from `docs/SYMPTOM_CHECKER_*_UI_SPEC.md`.
6. Keep `context_chips`, symptom codes, body-part codes, and follow-up mapped contexts disjoint.
7. If new spec context codes are added, verify they are auto-registered and not accidentally symptom/body-part codes.
8. Update tests in `health-navigator-backend/tests/test_symptom_checker_service.py`.
9. Run:
   - `cd health-navigator-backend`
   - `.venv\Scripts\python.exe -m py_compile app/services/symptom_checker_service.py app/schemas/symptom_checker.py`
   - `.venv\Scripts\python.exe -m pytest tests/test_symptom_checker_service.py -k "context_guide or follow_up_question or context_chips or display_candidates or gemini"`
   - `.venv\Scripts\python.exe -m pytest`
8. Manually check the HTML demo or Swagger `context-guide` response for representative parts:
   - chest `upper_chest`, `sternum`, `breast`, `rib_area`
   - head `forehead`, `temple`
   - abdomen `epigastrium`, `lower_abdomen`
   - arm/hand `wrist`, `finger`
   - leg/foot `calf`, `ankle`, `foot`
   - pelvis/urinary `suprapubic`, `genitals`
   - back/flank `flank`, `lower_back`

## Remaining Manual Spec Work

The first complete backend integration is done. Remaining work is quality refinement, not basic wiring.

- Add more explicit disease/rule mappings for newly registered spec context codes where high-value rules are needed.
- Review broad body parts that reuse an adjacent spec section (`arm`, `leg`, `whole_abdomen`, `right_abdomen`, `left_abdomen`, `pelvis`, `throat`, `tonsil_area`) and split them into dedicated spec sections later if the UI needs more precision.
- Verify Flutter renders `context_guide.follow_up_questions`, `display_candidates`, Gemini explanation, and the bottom disclaimer using the same structure as the HTML demo.
- Keep the user-facing candidate list at merged Top 5 and do not show internal source labels such as rule, RAG, score, backend, or display_candidates.
