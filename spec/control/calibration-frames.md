# Calibration frames

Scope: creating and selecting the calibration data the imager applies to light frames: the
dark library, bias and flat frames, the hot-pixel correction (HPC), and the stored per-type
settings. It sits above camera control ([viewing-and-exposure.md](viewing-and-exposure.md)) and
the filter wheel ([focus-and-filter.md](focus-and-filter.md)); its products are consumed by
[stacking.md](stacking.md). Event framing is in [events/families.md](events/families.md).
Per-method detail stays in the catalog cards.

App names: “Dark Frame Capture” (and its wide-angle form) builds master darks; “Dark Frame Library”
and “Enable Dark Frame Library” are the temperature dark library (INFERRED); “Dark Correction” and
“Capture dark frame before each enhancement” are `auto_master_dark`, a separate setting; “Hot Pixels
Correction” (and its wide-angle form) is HPC; “Flat Capture” and “Restore Factory Flats” are the
flat-frame methods. Names are the English strings of iOS app 3.4.0; links are READ (app call sites)
unless marked.

## Conventions

As in [viewing-and-exposure.md](viewing-and-exposure.md#conventions): RFC 2119 words bind
clients; labels READ, OBSERVED, INFERRED, unresolved; READ is the 64-bit build of firmware
9.31 unless stated. A `start_*` success reply means a worker was launched, never that a file
was written.

Basis: static analysis of firmware 9.31 / app 3.3.2, with deltas from firmware 9.75 / app 3.4.0 (64-bit
imager read in full; the 32-bit imager only spot-checked). Statements without a version tag are
firmware 9.31 and are unchanged in 9.75 unless a 9.75 note follows them.

## Contents

- [Dark library](calibration-frames/dark-library.md)
- [Frames and interactions](calibration-frames/frames-and-interactions.md)

## Relocated sections

These anchors retain navigation from generated cards; the linked sections are the primary text.

<a id="3-dark-library"></a>

- [Dark library](calibration-frames/dark-library.md#building-the-dark-library)

<a id="31-temperature-dark-library-firmware-975"></a>

- [Temperature dark library (firmware 9.75)](calibration-frames/dark-library.md#temperature-dark-library-firmware-975)

<a id="4-bias-and-flat-frames"></a>

- [Bias and flat frames](calibration-frames/frames-and-interactions.md#bias-and-flat-frames)

<a id="41-selecting-frames"></a>

- [Selecting frames](calibration-frames/frames-and-interactions.md#selecting-frames)

<a id="5-hot-pixel-correction-hpc"></a>

- [Hot-pixel correction (HPC)](calibration-frames/frames-and-interactions.md#hot-pixel-correction-hpc)

