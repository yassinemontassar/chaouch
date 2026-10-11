# 0007: Open items from the first smoke run

- **Status:** open (not decided yet)
- **Date:** 2026-10-11

## Context
The owner read the first `eval-smoke` answers and judge scores (B2, Gemini 2.5 Flash, 20 in-scope
questions). Two things to decide later, not fixed yet.

## 1. Answer script for Arabizi questions
Gemini answers Arabizi questions in Arabic script, never in Arabizi.

To decide: should Chaouch mirror the user's script (Arabizi in, Arabizi out)? If yes, add a "script match"
metric next to the dialect score.

## 2. Judge looks too strict on some items
Correctness was 0 on answers that seem to contain the required facts:

| id | What the answer says |
|---|---|
| b3-005 | mentions applying online and Rapid-Poste |
| birth-003 | names the Municipality of Tunis |

Plan: run the judge calibration of spec 8.2 (owner hand-labels 50 answers; Spearman and Cohen's kappa
against the judge) right after the full baseline, and before trusting its numbers. If agreement is weak,
revise `correctness_v1.md` and re-judge from the cache.

## 3. Gemini free tier is 20 requests per day
The 429s on 2026-10-11 show `GenerateRequestsPerDayPerProjectPerModel` = 20 for gemini-2.5-flash (and 5
per minute), not the 250/day assumed earlier. One smoke run (20 questions) uses a whole day; B2 on all 43
in-scope questions takes 3 days, resuming from the eval cache each day.

To decide: accept the multi-day B2 run, or move B2 to another free model with a larger daily quota.
**Resolved:** B2 moved to Gemini 3.5 Flash-Lite (ADR 0008).

## Consequences
- Baseline correctness may be underestimated until calibration is done; say so wherever the numbers appear.
