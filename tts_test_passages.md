# TTS Quality Test Passages

These standardized passages will be used to compare TTS models. Each model will generate audio for all passages using identical settings.

## Passage 1: Short & Simple (Baseline Quality Test)
**Purpose**: Quick quality check, clarity, pronunciation

```
The old clock on the mantelpiece struck twelve. Margaret closed her book and looked out the window at the falling snow.
```

## Passage 2: Medium Narrative (Flow & Consistency)
**Purpose**: Test natural pacing, sentence variety, and narrative flow

```
It was a bright cold day in April, and the clocks were striking thirteen. Winston Smith, his chin nuzzled into his breast in an effort to escape the vile wind, slipped quickly through the glass doors of Victory Mansions, though not quickly enough to prevent a swirl of gritty dust from entering along with him. The hallway smelt of boiled cabbage and old rag mats.
```

## Passage 3: Dialogue (Character Voices & Quotations)
**Purpose**: Test handling of quotations, multiple speakers, punctuation

```
"Where are you going?" asked the old man.

"To the market," she replied, adjusting her basket. "Mother needs flour for tomorrow's bread."

He nodded slowly. "Be careful out there. The roads are icy this time of year."

"I always am," she said with a gentle smile.
```

## Passage 4: Emotional & Expressive (Prosody & Feeling)
**Purpose**: Test ability to convey emotion, tension, and dramatic tone

```
Her heart pounded as she reached for the door handle. Behind it, she could hear muffled voices—angry, desperate voices. She had come too far to turn back now. Taking a deep breath, she pushed the door open. The room fell silent. Every eye turned toward her.
```

## Passage 5: Long-Form Consistency (Extended Narration)
**Purpose**: Test voice consistency over longer passages, fatigue resistance

```
The morning sun filtered through the dusty windows of the old library, casting long shadows across rows of forgotten books. Dr. Harrison had spent the last three months searching for a single reference—a footnote in an obscure journal from 1847 that might confirm his theory. His colleagues thought him mad, wasting his sabbatical on such a trivial pursuit. But he knew better.

As he climbed the rickety ladder to reach the top shelf, his fingers traced the spines of leather-bound volumes, each one a portal to another time. The air smelled of aged paper and leather, a scent he had grown to love over his forty years in academia. Finally, his hand stopped on a thin green volume, barely visible between two larger texts.

"This is it," he whispered to himself, carefully extracting the book. His hands trembled slightly as he opened to the index. There—page 247—exactly where the catalog said it would be. He descended the ladder slowly, clutching his prize, already composing the opening paragraph of the paper that would vindicate his research.
```

## Passage 6: Technical & Proper Nouns (Pronunciation Accuracy)
**Purpose**: Test handling of numbers, dates, proper nouns, technical terms

```
On December 15th, 1791, the Bill of Rights was ratified. James Madison, often called the "Father of the Constitution," drafted the first ten amendments to address concerns about centralized governmental power. The First Amendment alone encompasses five fundamental freedoms: speech, religion, press, assembly, and petition.
```

---

## Grading Criteria

For each sample, rate on a scale of 1-5:

1. **Naturalness**: Does it sound human-like or robotic?
2. **Clarity**: Is pronunciation clear and accurate?
3. **Prosody**: Does it have natural rhythm, intonation, and pacing?
4. **Expressiveness**: Does it convey appropriate emotion and tone?
5. **Consistency**: Does the voice remain stable throughout?
6. **Audiobook Suitability**: Could you listen to this for hours?

**Overall Score**: Average of all criteria (1-5)

---

## Notes on Testing

- All models should use the same voice reference file (if applicable)
- Output should be WAV or high-quality MP3 (same format for all)
- Files should be named clearly: `[model_name]_passage[number].wav`
- Generate all samples in a single test run to ensure fair comparison
