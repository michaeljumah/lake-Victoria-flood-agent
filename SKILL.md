---
name: assess-flood-risk-lake-victoria
description: Assess and rank flood risk for the Kenyan Lake Victoria basin counties from a natural-language question, grounded in Earth Engine data, population exposure, and retrieved Kenyan documents.
---

# Skill: Assess Flood Risk in the Lake Victoria Basin

> A reusable skill in the I/O 2026 `SKILL.md` format. It encodes the standard
> procedure the agent follows to answer a climate-risk question for Kenya, so
> the same workflow can be invoked consistently and extended to new hazards.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `question` | yes | Plain-English question about flood risk around Lake Victoria. |
| `counties` | no | Specific county names. Omit for the five basin counties (Kisumu, Homa Bay, Siaya, Busia, Migori). |
| `start_date` / `end_date` | no | Analysis window (ISO dates). Defaults to the long-rains season. |
| `hazard` | no | Focus hazard: `flood`, `drought`, or `rainfall`. Inferred from the question if omitted. |

## Process

1. **Understand the question.** Identify the hazard, the geographic scope
   (specific counties or all of Kenya), and what the user wants ranked.
2. **Retrieve context.** Query the knowledge base for relevant Kenyan
   documentation (historical floods/droughts, county profiles, authority
   bulletins).
3. **Gather geophysical signals.** Pull flood (Sentinel-1 SAR), rainfall
   (CHIRPS), and elevation (SRTM) layers per county from Earth Engine.
4. **Quantify exposure.** Retrieve WorldPop population per county.
5. **Score and rank.** Combine the signals with the transparent weighted model
   into a per-county risk score and rank the counties.
6. **Fuse and explain.** Produce a grounded answer: ranked counties, factor-by
   factor explanations, source citations, confidence, and recommendations.

## Tool sequence

```
search_knowledge(query=<question>, top_k=4)
        │   retrieved Kenyan context (with sources)
        ▼
get_earth_engine_layers(counties=<scope>, start_date=…, end_date=…)
        │   flood / rainfall / elevation per county
        ▼
get_population_exposure(counties=<scope>)
        │   exposed population per county
        ▼
compute_risk_score(counties=<scope>)
        │   ranked, transparent risk scores
        ▼
   (fusion) → final grounded answer
```

For a pure-context question ("what does the flood strategy say about Budalangi?"), the
skill may stop after `search_knowledge`.

## Outputs

- A **ranked list** of counties by climate-risk score (0–1), highest first.
- Per-county **components** (flood, rainfall, population, elevation) and their
  weighted **contributions** to the score.
- **Exposed population** per county.
- A natural-language **explanation** with source attribution.
- A **confidence** indicator and **recommendations**.

## Example usage

**Question:**
> "Which counties around Lake Victoria face the highest flood risk, and who is
> most exposed?"

**Tool calls (plan):**
1. `search_knowledge(query="Lake Victoria basin flood risk Nyando Budalangi", top_k=4)`
2. `get_earth_engine_layers(counties=[], start_date="2026-03-01", end_date="2026-05-31")`
3. `get_population_exposure(counties=[])`
4. `compute_risk_score(counties=[])`

**Result (shape):**
> Ranked counties (e.g. Kisumu, Busia, Siaya…) with risk scores and
> exposed-population figures; an explanation tying the top ranks to high flood
> signal + low elevation + large exposed population, citing the NDMA bulletin
> and the Lake Victoria flood-management strategy; medium confidence (note if running on
> fallback data); and recommendations to pre-position resources in the top
> counties and validate against the latest field reports.
