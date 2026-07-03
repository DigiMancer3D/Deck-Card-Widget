# Hard-coded Output Text Map

This file records the output text that was previously drawn directly inside `draw_source_analyzer()` / `run_scan_frame()` and is now stored under `header.display_text` in the `.buttstore`.

The public defaults are rebranded for **Deck Card Widget**, while `old_text` records the previous private 3DCP wording for review or rollback.

| ID | Editor label | Previous hard-coded text | Public default text | X | Y | Anchor | Previous/default color | Font | Size | Weight | Slant | Notes |
|---|---|---|---|---:|---:|---|---|---|---:|---|---|---|
| title_main | Top Title | 3DCP SOURCE ANALYZER | DECK CARD WIDGET | 34 | 38 | w | #e8fff5 | TkDefaultFont | 19 | bold | roman | Old private default: 3DCP SOURCE ANALYZER |
| status_live | Status Live | STATUS: LIVE | STATUS: LIVE | 922 | 38 | e | #00ff99 | TkDefaultFont | 12 | bold | roman | Previously used the scanner/accent color. |
| row_source_type | Row Label - Source Type | SOURCE TYPE: | CARD TYPE: | 52 | 96 | w | #8aa39b | TkDefaultFont | 12 | bold | roman |  |
| row_confidence | Row Label - Confidence | CONFIDENCE: | CONFIDENCE: | 52 | 128 | w | #8aa39b | TkDefaultFont | 12 | bold | roman |  |
| row_verdict | Row Label - Verdict | VERDICT: | STATUS: | 52 | 160 | w | #8aa39b | TkDefaultFont | 12 | bold | roman |  |
| qr_label | QR Label | SOURCE QR | LINK QR | 0 | 84 | center | #8aa39b | TkDefaultFont | 10 | bold | roman | X is computed from the QR column when a link exists; saved X is a fallback. |
| right_brand | Right Brand | THE PERSPECTIVE LAB | DECK CARD WIDGET | 898 | 106 | e | #668078 | TkDefaultFont | 10 | bold | roman |  |
| right_subtitle | Right Subtitle | PROOF ANALYSIS CONSOLE | STREAM CARD CONSOLE | 898 | 126 | e | #445953 | TkDefaultFont | 10 | normal | roman |  |
| activity_label | Activity Label | ACTIVITY: LINK READY | ACTIVITY: LINK READY | 898 | 154 | e | #00ff99 | TkDefaultFont | 10 | bold | roman | Only shown when the active card has a source/link URL. |
| host_label | Host Label | HOST: {host} | HOST: {host} | 898 | 172 | e | #8aa39b | TkDefaultFont | 9 | normal | roman | Use {host} to insert the domain parsed from the card link. |
| box_claim_label | Box Label - Claim | CURRENT CLAIM: | CARD CLAIM: | 52 | 216 | w | #8aa39b | TkDefaultFont | 11 | bold | roman |  |
| box_evidence_label | Box Label - Evidence | EVIDENCE SHOWN: | CARD EVIDENCE: | 52 | 306 | w | #8aa39b | TkDefaultFont | 11 | bold | roman |  |
| box_question_label | Box Label - Question | OPEN QUESTION: | OPEN QUESTION: | 52 | 396 | w | #8aa39b | TkDefaultFont | 11 | bold | roman |  |
| scan_label | Scanner Label | ANALYZING... | ANALYZING... | 835 | 210 | center | #00ff99 | TkDefaultFont | 10 | bold | roman | Only drawn while the scan animation is visible. |

## Also still hard-coded as layout/styling

The Display Edit tab controls output text objects only. Structural canvas shapes remain in code: output background, inner panel, separator lines, QR white box, boxed-text containers, accent side bars, and scan-line rectangles.

Field values such as card type, confidence, verdict, claim, evidence, question, and source link were already editable through the main card editor. Display Edit controls their output labels, not the user-entered values themselves.
