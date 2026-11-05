# Aksharantar evaluation sample

The 50 word pairs in `aksharantar_sample.json` are an attributed subset of **AI4Bharat Aksharantar**, Hindi test split, by Yash Madhani, Sushane Parthan, Priyanka Bedekar, Ruchi Khapra, Anoop Kunchukuttan, Pratyush Kumar and Mitesh S. Khapra (2022).

- Official dataset: https://huggingface.co/datasets/ai4bharat/Aksharantar
- Pinned revision: `e418c1fc928d9f5393af33268472cf20c1891be8`
- File: `hin.zip`, member `hin_test.json`
- Selection: Python `random.Random(3235).sample(eligible, 50)`, before running inference. Eligibility is a Roman input containing only ASCII letters, length 2–30, matching this application's supported input. Original row identifiers and source groups are preserved. References are unchanged.
- Dataset card licensing: manually collected data under CC BY; mined data and existing sources under CC0. Preserve this attribution when sharing the sample. Consult the official dataset card for the complete source-specific terms.

This word-level sample supplements the 40 authored application tests. It does not replace task-specific evaluation and is not presented as a full Aksharantar benchmark score.
