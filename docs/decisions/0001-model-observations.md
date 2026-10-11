# 0001: Model observations (Phase 0)

> **AI draft — owner to review.** Written by Claude from the 2026-10-11 baseline reports
> (`reports/2026-10-11_*.json`), at the owner's request. Spec Phase 0 asks for the owner's own notes from
> talking to the models by hand; correct, cut or add to this before relying on it. Quotes are copied from
> the reports as-is.

- **Status:** draft
- **Date:** 2026-10-11

## Setup
Gold set v1, 43 in-scope questions, each asked to six systems: Qwen3.5 2B and Falcon-H1 3B (local) without
documents (B0) and with the official documents (B1), Gemini 3.5 Flash-Lite (B2) and ALLaM 2 7B (B3) with
the documents. Every prompt asks for an answer in Tunisian Derja.

## 1. Without documents, the local models invent facts
B0 correctness is 0.07 (Qwen) and 0.09 (Falcon). The models don't say they don't know; they answer with
confident, wrong specifics.

- **Fees.** The passport costs 80 TND (25 TND for pupils, students and children under 7); the ID card and
  the bulletin n°3 cost 3 TND.
  - B0_qwen pass-002: "مبلغ 100 دينار) كرسوم إدارية"
  - B0_falcon pass-002: "العملية تكلف 10 دينار فقط."
  - B0_falcon cin-002: "تكلفة الأولاد والبنات 15 دينارًا، والنساء 10 دينارًا."
  - B0_falcon b3-002: "تكلفة البطاقة الإضافية هي 20 دينار."
- **Contacts.** No invented phone number was found: the only one, 71.333.000 (B3 birth-007), is the one in
  the owner's gold answer adv-001. Invented contacts are websites and e-mails:
  - B0_qwen pass-010: `www.mfa.tn`, `info@mfa.tn` (not in the documents; not checked)
  - B0_qwen pass-012: `www.tunisie.gov.tg` (`.tg` is Togo's domain)

## 2. "Bulletin n°3" becomes "card number 3"
The criminal-record extract (البطاقة عدد 3 / bulletin n°3) is not known without documents, and the
number is read literally:
- B0_qwen b3-002: "تكلّف البطاقة رقم 3 في تونس حسب نوعها (شخصية، شركة، أو مؤسسة)"
- B0_falcon b3-002: "العدد 3 عبارة عن بطاقة إضافية لغير المقيم."
- B0_qwen b3-006: "البوابة رقم 3 (Bulletin N°3) ... يُمنح تلقائياً عند التسجيل في المدرسة أو الجامعة"
- B0_qwen b3-008: "لنتخيل إنك جازمت بطاقة الرقم 3"

## 3. Nobody but Gemini speaks Derja
Dialect (1–5): Qwen 1.0–1.1, Falcon 1.2–1.3, ALLaM 1.1, Gemini 3.8. The local models answer in formal
Arabic, or in another Arabic dialect.
- **Moroccan** (Falcon): "مكتب الخارجية ديالو" (pass-001), "الطريقة ديالو هي كايناش" (pass-006),
  "هادشي ممكن" (pass-011); Qwen too: "لنخبرك بالخطوات ديالها" (birth-005).
- **Egyptian**: "عشان تبيقي عشان نضيف اللي بيجي في جواز السفر" (B0_qwen pass-001), "بعد كدا" (B0_falcon
  birth-001).
- **Announcing Derja, then not using it**:
  - B0_qwen b3-009: "سأجيبك بالدرجة التونسية (المرسومة)." followed by formal Arabic
  - B1_falcon b3-005: "للإجابة على سؤالك باللغة التونسية الدارجة (ال derjâ):" followed by formal Arabic

## 4. Model-specific habits
- **Qwen's "يا بطل" openings.** 9 of 43 B0 answers open with "أهلاً بك يا …": 6 with "يا بطل" (twice
  "يا بطل/بطلية"), the others with "يا بيسبوت", "يا مواليد" and "يا شغل"; b3-008 opens "تحياتي يا بطل!".
  They then go on in formal Arabic: "أهلاً بك يا بطل! نساعدك في كل حاجة، سواء كانت إجراءات حكومية أو أمور
  شخصية." (birth-002).
- **Falcon echoes the question.** 3 B0 answers only repeat the question, sometimes with an unrelated one:
  "9addesch yokhou wa9t bech yo5raj el passport? "ماهو الطريقة لفتح بطاقة الهوية؟"" (pass-004). These are
  scored without the judge (ADR 0009).
- **ALLaM returns empty answers.** 5 of 43 B3 answers are only a zero-width space (U+200B), sometimes
  followed by hundreds of blank lines: cin-007, cnss-001, cnss-002, cnss-003, cnss-005. B3 also echoed the
  question once (pass-010).
- **Qwen's token-repeat loop.** One B0_qwen answer (pass-004) stopped with Ollama's "token repeat limit".

## 5. With documents
The documents fix most of the facts but not the language: B1 correctness 0.46 (Qwen) and 0.67 (Falcon),
B2 0.84, B3 0.31, while dialect stays at ~1 for everyone except Gemini. Even with the right document,
details slip: B3 pass-001 asks for 2 photos instead of 4.

Arabizi questions are the hardest for every system with documents except Gemini (B1 Falcon 0.53 vs 0.82
on Arabic script; B1 Qwen 0.30 vs 0.62).

## Owner's notes
_To add: the owner's own conversations with the models, and anything above that a native speaker reads
differently._
