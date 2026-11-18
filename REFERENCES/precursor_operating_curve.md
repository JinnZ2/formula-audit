# precursor: measured operating points, seeds, sources

Status: PROPOSED tool; the table below is an OBSERVED run of the filed code.
Co-authored. Observer slots null.

```text
file        glyph/precursor.py, filed verbatim 2026-11-18
sha256      d2cdb8d71df9b9737b5a080a24e714f2c1f363a81f7140d6ce22e00654be7856
run         Python 3.13.x, 2026-11-18, from the repository root
```

## The delivered table

Delivered 2026-11-18, after the filing order (the order said "the table
above" and carried none; the table arrived in the next message). Kept as
delivered: 60-point series, 200 seeds each, counts of the PRECURSOR flag.

```text
window  limit  planted caught  white-noise false alarms
 4-16   0.5     0-30            0-1
 20     0.5     46              3
 20     0.3     87              12
 30     0.5     79              8
 30     0.3     120             20
```

Re-run here on the filed code, seeds 0 .. 199 (planted) and 10000 .. 10199
(white noise): every row reproduces exactly.

```text
window  limit  planted  white        window  limit  planted  white
 4      0.5      0       0            20     0.5     46       3
 8      0.5      1       0            20     0.3     87      12
12      0.5      7       0            30     0.5     79       8
16      0.5     30       1            30     0.3    120      20
```

Delivered readings, carried: short windows are blind; detection needs about
half the series as the window; the limit trades catches for false alarms.
"Early-warning signals need long series" is carried as known in the
literature: VERIFY. The selftest asserts the rate at window 30, limit 0.5
(catches at least 3 times the false alarms over its first 100 seeds), not a
single case.

Build error, carried from the delivery: the first planted signal alternated
sign, so its autocorrelation fell and it was no precursor. It was replaced by
the AR(1) signal whose memory grows.

## A second sweep, measured here

Three flag states over `trend_limit`, the first 100 seeds only. Two signals, 100 runs each, 60 points, `window` 30, `tau` 3.0,
`streak_limit` 3. Counts of the precursor flag out of 100.

```text
              planted (memory grows)        white noise
trend_limit   PRECURSOR  WATCH  NONE        PRECURSOR  WATCH  NONE
0.2               64       21    15             8        52    40
0.3               58       23    19             6        49    45
0.4               47       30    23             4        39    57
0.5               33       39    28             2        32    66     <- the selftest's point
0.6               23       37    40             2        23    75
0.7               13       29    58             1        16    83
0.8                6       15    79             0         8    92
```

Reading: raising `trend_limit` lowers false alarms and misses more planted
runs. At the selftest's point the flag catches 33 of 100 planted runs and
fires on 2 of 100 white-noise runs. WATCH (one of the two trends rising)
fires on white noise 32 times in 100 at that point.

Seeds and construction (as in the file's selftest):

```text
planted   seed s = 0 .. 99       rng = random.Random(s); x = 0
          for t in 0 .. 59:  x = (0.05 + 0.9 * t / 59) * x + rng.gauss(0, 1)
white     seed 10000 + s         rng.gauss(0, 1), 60 draws
every event: outcome PASS, state = the signal value, t = the index
```

Reproduce: call `glyph.precursor.check` on those 200 cases per row with
`declare = {"tau": 3.0, "window": 30, "streak_limit": 3, "trend_limit": L}`
and count `["precursor"]["flag"]`.

Limits of the table

```text
one construction   an AR(1) signal whose coefficient climbs from 0.05 to 0.95.
                   Other precursors (a slow drift, a step) were not run.
one window         30 of 60 points. Other windows and lengths were not run.
no other tau       tau does not enter the precursor when every event carries a state.
floats             rolling variance and autocorrelation are float sums. Python 3.12
                   changed how sum() adds floats; a count could differ by a run on
                   3.10 or 3.11. Not checked there.
no real log        every case is constructed. No event log from a real run was read.
```

## Sources

```text
Scheffer et al. 2009   early-warning signals of critical transitions: rising variance
                       and lag-1 autocorrelation. Recalled, not re-read: VERIFY.
Anthropic 2026         emotion-concepts work: an internal state that rises with each
                       failure and is relieved by a shortcut that "passes". Read via
                       secondary coverage only; the primary text was not read.
source practice        elders' calibration practice through cascades, sudden
                       fluctuations and destruction events. Oral tradition, unnamed.
```
