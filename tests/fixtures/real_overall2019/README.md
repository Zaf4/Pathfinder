# Real water maze data (subset)

Two mice (B6_9 = C57BL/6, D2_9 = DBA/2), all 30 trials each: 18 acquisition trials (days 1–3) and 12 reversal trials (days 4–5, platform moved). Trial 6 on days 3 and 5 is a probe trial with no platform.

**Source:** Overall RW & Kempermann G (2019). *Water maze tracking data.* figshare. https://doi.org/10.6084/m9.figshare.10248158.v3. Licensed CC BY 4.0. The tracks were recorded with Noldus EthoVision.

**Conversion** (from the Rtrack JSON archive):
- The raw pixel coordinates were converted to EthoVision-style `.xlsx` exports in cm, with the pool centre at (0, 0) and y pointing up.
- Lost samples are written as `-`, as EthoVision does.
- The dataset gives no physical size. A 120 cm pool is assumed: the 190 px pool with its 20 px platform matches a standard 120 cm mouse pool with a ~12.6 cm platform.

`truth.json` holds the study's actual platform positions, used to test goal detection. `tests/golden/real_overall2019_*.csv` is the output of the original Pathfinder for these files.
