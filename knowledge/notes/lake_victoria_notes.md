# Lake Victoria Basin — Flood Risk Notes

Curated context for the agent's grounded retrieval, covering the Kenyan Lake
Victoria basin: Kisumu, Homa Bay, Siaya, Busia and Migori counties. Statements
here are paraphrased from public sources listed in `sources.md`. Keep this file
factual and attributed.

## Why Lake Victoria is the centre of this study

Lake Victoria is the largest lake in Africa and the source of livelihoods for
millions in western Kenya. Its shoreline counties face a distinct flood problem
that differs from Kenya's arid north: flooding here is driven by rising lake
levels, river backflow at the lake outlets, and intense rainfall over the
catchment, rather than by flash floods in dry riverbeds.

Lake levels rose sharply during the exceptionally wet seasons of 2019–2020,
submerging shoreline settlements, farmland, schools and health facilities across
the lakeside counties and displacing large numbers of residents. Elevated lake
levels mean that even ordinary seasonal rain can cause backflow flooding.

## The Kano plains and the Nyando basin (Kisumu)

The Kano plains, east of Kisumu, are flat, low-lying and drained by the Nyando
River. The combination of low gradient, poor drainage and a high water table
makes the area flood repeatedly during the long rains (March–May) and again in
the short rains. Nyando is one of the most consistently flood-affected sub-basins
in western Kenya.

## Budalangi and the Nzoia River (Busia)

Budalangi, in Busia County, sits at the outlet of the Nzoia River into Lake
Victoria and is one of the most flood-prone locations in Kenya. Flooding occurs
when the Nzoia bursts its dykes or when high lake levels cause backflow up the
river. Repeated dyke breaches have displaced communities and destroyed crops.

## Siaya, Homa Bay and Migori

Siaya County's lakeshore and the Yala swamp area are exposed to both river and
lake flooding. Homa Bay and Migori counties face shoreline inundation and, in
places, flash flooding from the Kuja and Migori rivers. Across all lakeside
counties, fishing communities living close to the water are the most exposed
because their livelihoods require proximity to the lake.

## Exposure and equity

The people most exposed in this basin are typically small-scale farmers and
fishing households living on the floodplain, often with limited ability to
relocate. Vulnerability is unevenly distributed within communities, which is why
a physical hazard signal alone is insufficient: population exposure must be
combined with the hazard, and the reasoning behind any ranking must be visible
and auditable.

## A note on measuring floods near a large lake

Radar-based flood detection identifies standing water by its low backscatter.
Because Lake Victoria is permanent open water, it produces the same signal as a
flood. Any credible flood analysis in this basin must therefore mask permanent
water (for example using the JRC Global Surface Water dataset) so that what is
measured is *new* or seasonal water — actual flooding — rather than the lake
itself. This project applies that mask.
