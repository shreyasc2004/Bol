# Bol — Hinglish Smart Writing Assistant

**CS3235 · Project option 4 · 5 November 2026**

## Problem and scope

Bol helps Hindi speakers turn Roman-script Hinglish into Devanagari, improve phrasing and optionally translate to English. It uses AI4Bharat and BharatGen models with an official Aksharantar sample. Both models run locally; no external model API or key is used.

Example: `mujhe kal college jana hai` → `मुझे कल college जाना है` with common-English-word preservation enabled.

## Models, data and suitability

| Component | Selected resource | Purpose |
| --- | --- | --- |
| Transliteration | AI4Bharat Hindi RNN v0.5 | Roman Hindi to Devanagari; alternate spellings |
| Generative writing | BharatGen Param-1-2.9B-Instruct, Q4_K_M | Hindi phrasing and optional English translation |
| Official dataset | AI4Bharat Aksharantar Hindi test split, fixed 50-pair sample | Supplemental word-level evaluation |
| Task-specific data | 40 authored application cases; 12 writing cases | Evaluate this app's behavior |

The assignment's IndianNLP-Transliteration link redirects to AI4Bharat's earlier RNN repository, which supplies the converter used here. It is not the newer IndicXlit transformer. Param1 is BharatGen's Hindi/English model. A community GGUF conversion reduces its size to approximately 1.82 GB, allowing CPU inference on the 16 GB development laptop. It is a format/precision conversion of Param1, not an additional model or an official BharatGen GGUF release. llama.cpp b12034 is only its execution runtime.

The community runtime's default tokenizer did not match the original BharatGen BPE on Hindi and chat-role strings. The adapter therefore uses the **original pinned BharatGen tokenizer** for both input token IDs and output decoding, with the official ChatML format. This fixed the observed incorrect responses. No pretrained weights were changed.

Pinned revisions and verified SHA-256 hashes are recorded in data/sovereign_provenance.json. AI4Bharat code is MIT-licensed. Param1 and the conversion metadata identify Apache-2.0, although the original Param1 README body also mentions MIT; this academic prototype links both sources and does not redistribute weights. Aksharantar's source-dependent CC BY/CC0 terms and credit are recorded in data/ATTRIBUTION.md. Only Hindi is enabled; voice recognition, TTS and unrelated models are outside this writing project's scope.

## Application and prompting

```text
Browser → Flask validation → AI4Bharat converter → editable Hindi + alternatives
                         → local BharatGen Param1 → revised Hindi / English
```

The frontend provides conversion, alternate spellings, manual editing, tone selection, spacing cleanup, copy and text download. Existing Hindi, whitespace, punctuation, numbers, emoji, URLs and emails are preserved during conversion. English preservation is a small vocabulary/acronym rule, not automatic language detection.

Param1 receives an editing/translation instruction that asks it to preserve meaning, names, numbers and negation, and return only the result. Generation uses temperature 0.2, seed 42, a 180-token output cap and a 2,048-token local context. Long passages return an explicit error rather than a silently truncated result. The first AI request loads Param1; subsequent requests reuse it. Identical successful requests are cached in memory. No RAG or model training is needed.

## Measured evaluation

| Evaluation | Cases completed | Exact match | CER | Other measure |
| --- | ---: | ---: | ---: | --- |
| Authored application cases | 40/40 | 55.0% | 5.91% | Edit-based word accuracy 80.65% |
| Supplemental Aksharantar word sample | 50/50 | 42.0% | 15.94% | Word accuracy 42.0% |
| Param1 writing/translation pilot | 12/12 | Not a quality target | Not used | Literal number preservation 11/12 (91.67%) |

There were no service errors in these completed runs. Mean latency was approximately 655 ms for authored conversion cases, 203 ms for the word sample, and 951 ms for writing cases using an already-running local runtime. These are local pilot measurements, not published benchmark scores. Conversion latency excludes model loading and can include cache reuse.

CER is micro-averaged edit distance over NFC-normalized Unicode code points. WER uses whitespace tokens; word accuracy is max(0, 1 − WER). The writing evaluator's mean character n-gram F2 was 0.618; this is diagnostic reference overlap, **not a semantic accuracy or fluency score**. No human ratings are claimed.

The 40 task-specific cases cover greetings, daily language, polite requests, questions, variants, names, ambiguity, numbers, whitespace, punctuation, emoji, native script, code mixing, URLs and emails. Aksharantar selection used seed 3235 before inference, with original identifiers and references retained. It supplements rather than replaces the task-specific set. Sixteen automated tests passed, including validation, formatting, caching, failure handling and enforcement of the local model endpoint. Unit tests mock model responses; the evaluation reports contain actual model outputs.

## Observed successes and failures

| Case | Actual observation | Interpretation |
| --- | --- | --- |
| `aap kaise hain?` | आप कइसे हैं? instead of आप कैसे हैं? | Word-level phonetic ambiguity. |
| `main theek hoon` | मैं ठीक हों instead of मैं ठीक हूँ | Nasalized-vowel error. |
| `dilli se mumbai` | दिल्ली से मुम्बई vs reference दिल्ली से मुंबई | Acceptable variants can lower exact-match scores. |
| Concise rewriting | मैं यह कहना चाहता हूँ कि मैं कल नहीं आ पाऊँगा। → मैं कल नहीं आ पाऊंगा। | Removes verbosity while preserving negation. |
| Polite rewriting | कृपया इसे test@example.com पर भेज देना। → कृपया इसे test@example.com पर भेज दें। | Improved phrasing; email retained. |
| Number formatting | 10 became दस | Literal digit check warns despite equivalent numeric meaning. |
| Translation | मैं कल नहीं आ पाऊँगा। → I won't be able to come tomorrow. | Correct result on this case. |
| Name/translation error | राहुल को 250 रुपये वापस कर देना। → Rakhul ko 250 rupees back. | Mixed-language and name-spelling failure. |

Tone control is imperfect: some formal requests remain informal, some inputs are unchanged, and obligation wording can shift. Names, negation and numbers need review. The 50-word subset and 12 writing cases are small, and references have not been independently reviewed by a Hindi expert. The report includes these limitations rather than presenting every completed response as correct.

## Run and demo

1. Double-click run.bat; open http://127.0.0.1:5050.
2. Convert `mujhe kal college jana hai`; toggle English preservation and inspect spellings.
3. Try concise phrasing on `मैं यह कहना चाहता हूँ कि मैं कल नहीं आ पाऊँगा।`.
4. Try formal phrasing on `कृपया इसे test@example.com पर भेज देना।`.
5. Optionally translate `मैं कल नहीं आ पाऊँगा।` to English.
6. Edit, copy and download. Inspect actual errors in reports/.

Fresh setup and evaluation commands are in README.md. Downloaded weights and runtime binaries are excluded from the source ZIP; scripts/setup_sovereign.py obtains and verifies them. The local Git repository is initialized; publishing to GitHub requires the student's account. Add team identifiers in the course cover sheet/submission portal as required.

## References

- Official starting-point converter: https://github.com/AI4Bharat/IndianNLP-Transliteration
- BharatGen Param1: https://huggingface.co/bharatgenai/Param-1-2.9B-Instruct
- Community GGUF conversion: https://huggingface.co/arunmcops/Param-1-2.9B-Instruct-GGUF
- Official Aksharantar dataset: https://huggingface.co/datasets/ai4bharat/Aksharantar
- llama.cpp execution runtime: https://github.com/ggml-org/llama.cpp
