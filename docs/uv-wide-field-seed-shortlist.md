# 240-320 nm / 60 deg x 60 deg / 18 mm initial-structure shortlist

This shortlist uses the strict rectilinear interpretation of the supplied
specification: the four corners of a 60 deg x 60 deg rectangular field touch an
18 mm circular image area. That gives:

- effective focal length: 11.022704 mm
- maximum F-number at a 12 mm entrance pupil: 0.918559
- rectangular image area: 12.727922 mm x 12.727922 mm
- full diagonal field: 78.463041 deg

The requested Nyquist frequency is not known because detector sampling or limiting
resolution was not supplied. Consequently, MTF >= 0.4 at Nyquist cannot yet be
verified numerically.

## Rank result

The score is `100 * exp(-weighted engineering distance)`. It ranks metadata fit;
it is not a probability of meeting the final specification. Slower F-number and
narrower field receive a 3x asymmetric penalty. Weights are F-number 35%, field
30%, architecture 15%, spectrum 10%, and element-count complexity 10%.

| Rank | Seed | Score | Scale to 11.022704 mm | Main value | Main blocker |
|---:|---|---:|---:|---|---|
| 1 | CN113504627B | 65.579 | 1.418623x | F/0.97, 130 deg, all-spherical fused silica | 250-270 nm only; no published MTF/distortion; 121.344 um max RMS spot |
| 2 | CN112162388A | 53.619 | 1.477202x | >115 deg, F/# <1.3, >17.5 mm image circle, >90% relative illumination | inferred EFL; 250-280 nm only; no published MTF/distortion |
| 3 | CN107450163B | 21.579 | 0.355571x | 240-280 nm and compact 5-element topology | F/3 and 64 deg; diffractive surface is risky over 240-320 nm |
| 4 | CN115047595B | 13.665 | 0.440908x | published 240-400 nm broadband coverage | F/2, 25 deg and 13 elements |
| 5 | CN119335679B | 10.087 | 0.259969x | broad UV material/performance reference | F/2.5; field used in ranking is inferred and narrow |
| 6 | CN111061047B | 6.341 | 0.110227x | useful published MTF/illumination/distortion reference | full field only 11.34 deg |

## Recommendation

Use CN113504627B as the first optimization branch because it is the only found
prescription close to the required aperture while already offering surplus field.
Use CN112162388A as the independent second branch because its negative-front /
positive-rear architecture, image circle, and illumination claims are attractive.
Do not select either as the final design until both are rebuilt and compared under
the same wavelength, pupil, field grid, detector window, merit function, and
optimization budget.

The likely engineering path is to preserve one of these two wide-fast power layouts
while introducing CaF2/fused-silica color correction inspired by a broadband UV
reference. Simple geometric scaling alone cannot fix the missing 240-320 nm
coverage, F/# gap, distortion, or MTF.

## Primary documents

- [CN113504627B](https://patents.google.com/patent/CN113504627B/en)
- [CN112162388A](https://patents.google.com/patent/CN112162388A/zh)
- [CN107450163B](https://patents.google.com/patent/CN107450163B/en)
- [CN115047595B](https://patents.google.com/patent/CN115047595B/en)
- [CN119335679B](https://patents.google.com/patent/CN119335679B/en)
- [CN111061047B](https://patents.google.com/patent/CN111061047B/en)
