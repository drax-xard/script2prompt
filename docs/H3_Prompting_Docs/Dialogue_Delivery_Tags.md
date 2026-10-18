# Dialogue delivery tags (`<d>` inner tags)

> **Not an official MiniMax feature.** These tags are a **community finding**:
> they are not documented in the published H3 prompt-writing guides, but they
> have been used in practice and observed to work. Treat this file as a
> *community addendum* to `H3 Prompt Writing Guide (Text and Keyframe).md` and
> `H3 Prompt Writing Guide (Reference).md`, not as guide-derived canon.

H3 dialogue is written inside `<d>...</d>` as
`Name (S1) says <d>[English]words</d>.` Delivery tags are extra tags placed
**inside** the `<d>` element to express nuance that plain words cannot: pauses,
breathing, emphasis, and non-verbal sounds.

## Placement

- A **leading tag** goes immediately after the language tag:
  `<d>[English]<inhale> Alright, let's do this.</d>`
- A **wrapping tag** encloses only the words it affects:
  `<d>[English]I will <i>not</i> tolerate this.</d>`
- The language tag always comes first, directly after `<d>`. The speaker ID and
  any descriptive delivery note (`(low but insistent)`) stay *outside* `<d>`.

Use a tag **only when the script cues that delivery** (a parenthetical, an
action beat, or clearly implied by the words). Do not decorate untagged lines.

## Tag reference

| Group | Tag | Meaning | Example |
| ----- | --- | ------- | ------- |
| Pauses and breath | `<pause>` | Short pause | `Okay, so. <pause> This is just me talking.` |
| Pauses and breath | `<long pause>` | Longer pause | `I mean <long pause> I don't even know.` |
| Pauses and breath | `<breath>` | Breathing sound | `And then <breath> it just happened.` |
| Pauses and breath | `<inhale>` | In breath | `<inhale> Alright, let's do this.` |
| Pauses and breath | `<exhale>` | Out breath | `<exhale> Fine. Have it your way.` |
| Pauses and breath | `<catches breath>` | Out of breath | `Wait <catches breath> hold on a sec.` |
| Pauses and breath | `<deep breath>` | Calming down | `<deep breath> Okay. I can do this.` |
| Delivery and emphasis | `<i>...</i>` | Emphasize 1–4 words | `I was <i>not</i> expecting that.` |
| Delivery and emphasis | `<whisper>...</whisper>` | Whisper delivery | `<whisper> Don't tell anyone this.</whisper>` |
| Delivery and emphasis | `<softer>` | Quieter delivery | `<softer> I don't think I can say it.` |
| Delivery and emphasis | `<humming>...</humming>` | Humming a tune | `<humming> da-da-da-beautiful-day.</humming>` |
| Delivery and emphasis | `<stutter>` | Stutters the words | `<stutter> I ca can't believe that.` |
| Delivery and emphasis | `<uh>` | Filler / hesitation | `So, like <uh> what was I saying?` |
| Non-verbal sounds | `<laughs>` | Laughing | `That's <laughs> that's actually funny.` |
| Non-verbal sounds | `<chuckle>` | Small laugh | `<chuckle> You're not serious.` |
| Non-verbal sounds | `<sighs>` | Sigh | `<sighs> I really tried.` |
| Non-verbal sounds | `<gasp>` | Sharp intake | `<gasp> Oh my God.` |
| Non-verbal sounds | `<coughs>` | Cough | `<coughs> Sorry, one sec.` |
| Non-verbal sounds | `<clears throat>` | Throat clear | `<clears throat> So anyway` |
| Non-verbal sounds | `<sniff>` | Sniffing | `<sniff> It's just really sad.` |
| Non-verbal sounds | `<mhm>` | Agreement sound | `Yeah, <mhm> exactly.` |
| Non-verbal sounds | `<phew>` | Relief | `<phew> That was close.` |

## How Script2Prompt uses them

- **Deterministic builders** (`core/fallback.py`, reused by `core/r2v.py`):
  `core/delivery.py` maps an unambiguous screenplay parenthetical to a tag and
  inserts it into the rendered `<d>` line. Examples: `(beat)` → `<pause>`,
  `(whispering)` → `<whisper>...</whisper>`, `(sighs)` → `<sighs>`,
  `(laughs)` → `<laughs>`, `(softly)` → `<softer>`. Ambiguous or non-delivery
  parentheticals (`(V.O.)`, `(CONT'D)`, `(to Will)`, `(closer)`) are left
  untagged rather than guessed at.
- **LLM rewrite** (`core/prompts.py`): the system prompts list the tags and
  instruct the model to add one only when the script cues the delivery.
