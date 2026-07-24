# Knowledge Base Sources — Lake Victoria Flood Risk Agent

Citation register for every document in `knowledge/`. It records where the
agent's grounding comes from and the licensing status, so the project only
redistributes what it is allowed to.

## Citation template

For every file added to `knowledge/pdfs/` or `knowledge/notes/`:

```
### <short id>  —  <filename>
- Title: <full title>
- Author / Publisher: <author(s) or organization>
- Year: <year>
- Type: <government report | journal article | NGO assessment | notes>
- URL: <direct link>
- License: <CC-BY | open government | (c) publisher - link only>
- Redistributable in this repo?: <yes / no>
- Used for: <what the agent draws from it>
```

**Rule:** government reports (NDMA, Kenya Met, WMO/APFM), UN/OCHA, and CC-BY
journal articles are generally safe to commit. Paywalled or all-rights-reserved
material gets a **citation and link only** - no PDF in the repo.

---

## Recommended documents for the Lake Victoria basin

Download the open ones into `knowledge/pdfs/`. These are real, currently
available sources covering the basin.

### apfm-lake-victoria-strategy  -  lake_victoria_flood_strategy.pdf
- Title: Strategy for Flood Management for Lake Victoria Basin, Kenya
  (Pilot National Strategy)
- Author / Publisher: Associated Programme on Flood Management (WMO / GWP)
- Type: international programme report
- URL: https://www.floodmanagement.info/floodmanagement/wp-content/uploads/2020/07/Pilot_National_Strategy_for_Kenya.pdf
- License: WMO/APFM public programme document - check terms; generally citable
- Redistributable in this repo?: yes (attribution)
- Used for: dyke breaches in Budalangi and the Nyando floodplains, numbers
  affected, inundation in the lower Nzoia basin near the lake confluence
- **This is the single most relevant document for this project - add it first.**

### opere-floods-kenya  -  floods_in_kenya_chapter.pdf
- Title: Floods in Kenya (book chapter)
- Author / Publisher: Alfred Opere - University of Nairobi repository
- Type: academic book chapter
- URL: https://erepository.uonbi.ac.ke/server/api/core/bitstreams/8ee4441f-c4e1-4c2c-88b4-59443af5fb0e/content
- License: university repository - open access; verify terms
- Redistributable in this repo?: yes if open access
- Used for: rising Lake Victoria levels impeding flood discharge into the lake;
  identification of the lower Nzoia (Budalangi) and lower Nyando (Kano plains)
  as Kenya's principal flood zones alongside the Tana

### nyakundi-kano-plains  -  kano_plains_precautionary_measures.pdf
- Title: Socio-economic characteristics of the community that determine ability
  to uptake precautionary measures to mitigate flood disaster in Kano Plains,
  Kisumu County, Kenya
- Author / Publisher: Nyakundi et al.
- Type: journal article
- URL: https://www.researchgate.net/publication/284797411
- License: verify per-article; if not open, cite and link only
- Used for: Nyando sub-county within the Lake Victoria lowlands and floodplains;
  slow-onset, predictable river flooding; annual relief cost estimates

### maseno-nyando-budalangi  -  CITE ONLY unless open
- Title: Effects of Floods on Economic Value of Crops, Livestock Production and
  Land Among Communities of Nyando and Budalangi in the Lake Victoria Basin,
  Kenya
- Author / Publisher: Maseno University repository
- Type: thesis / journal article
- URL: https://repository.maseno.ac.ke/handle/123456789/3799
- Used for: combined economic effects of flooding on crops, livestock and land
  in Nyando and Budalangi; household vulnerability

### uon-budalangi-livelihoods  -  CITE ONLY unless open
- Title: Livelihood Diversification and Sustainability: the Case of Flood Prone
  Areas of Budalang'i Constituency, Busia County
- Author / Publisher: University of Nairobi repository
- URL: https://erepository.uonbi.ac.ke/handle/11295/59198
- Used for: Budalangi's long flood history and community coping strategies

### ndma-bulletin  -  ndma_drought_bulletin.pdf  (KEEP from original project)
- Title: National Drought Early Warning Bulletin
- Author / Publisher: National Drought Management Authority (NDMA), Kenya
- URL: https://www.ndma.go.ke/drought-information/
- License: Kenya Government public information
- Redistributable in this repo?: yes
- Used for: national context and county classifications. Note that NDMA focuses
  on ASAL counties, so it provides background rather than lakeside detail.

---

## Documents carried over from the Tana River version

The original project's Tana-specific PDFs (`tana_delta_inundation_mapping.pdf`,
`odoyo-tana-flood`, the Okoko governance paper) are **not relevant to the Lake
Victoria basin** and have been removed from `knowledge/pdfs/` for this workshop.
They describe a different hydrological system. After adding the new documents,
re-run `build_index.py` so the retrieval index reflects the new corpus.

---

## Notes

- After adding or removing any document, re-run:
  `python -c "from src.rag.build_index import build_index; print(build_index())"`
- Keep this file in sync with the actual contents of `knowledge/`.
- Prefer government and programme reports for live figures - they are the most
  authoritative and the safest to redistribute.
