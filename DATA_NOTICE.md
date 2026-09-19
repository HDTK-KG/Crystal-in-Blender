# Symmetry data

The application uses the existing `Database_of_crystal_symmetry/space_group.csv`
and `Wyckoff.csv` supplied with this repository. The input files are preserved
unchanged. Their original author, source URL, and redistribution license were
not recorded in this repository; this project does not assign them a new license.

The first column is a setting serial (1–530), not the ITA space-group number
(1–230). `space_group.csv` maps the two and records axes/origin choices.
`Wyckoff.csv` uses colon-separated records, continuation lines, and an explicit
`end of data` marker. Records after that marker are ignored. Centring translations
are applied separately, including primitive rhombohedral axes for choice `R`.

Validation checks all 3,467 listed positions against their multiplicities at
generic coordinates. This is an internal consistency test, not independent
certification of every source coordinate. Generation rejects multiplicity
collapse and incompatible cell metrics instead of silently accepting them.

Implementation references:

- [IUCr: centring translations](https://it.iucr.org/Ga/ch4o7v0001/Ispace_group.centring_type.html)
- [IUCr: rotation matrices and translations](https://www.iucr.org/what-we-do/education/pamphlets/rotation-matrices-and-translation-vectors-in-crystallography)
- [Blender: Principled BSDF](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html)
