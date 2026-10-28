# Built in Detroit, Bound for the Track

A 500-drone light show that tells my story in the sky: who I am, where I've worked, where I'm from, and where I want to go next, which is the race track.

I'm learning drone design, and I built this show to put that skill to work on something personal. It was also part of my application to Ford Racing's NASCAR program.

**Watch the 3D preview:** the live page is in this repo's GitHub Pages site under `/ford-racing/`. The file behind it is `docs/ford-racing/index.html` at the top of the repo.

## Running order

| # | Formation | What it says |
|---|---|---|
| 1 | LAKITHIA WILLIAMS, PMP | My name |
| 2 | BORN IN MOTORCITY over a skyline | Detroit |
| 3 | AUTOMOTIVE RUNS IN THE BLOOD | Where I come from |
| 4 | Locomotive, jet, bike | Norfolk Southern, UTC Aerospace and Collins Aerospace, Peloton |
| 5 | Stock car, NEXT LAP, FORD RACING | Where I'm headed |
| 6 | READY TO RACE over a checkered flag | The ask |
| 7 | QR code over CONNECT | Scan it to open my LinkedIn (held 8 seconds) |
| 8 | Landing | Back on the pad |

The show opens with the drones already lit in the first formation.

The icons on slide 4 are my own drawings, not company logos.

The QR code on slide 7 points to [linkedin.com/in/lakithia-williams](https://linkedin.com/in/lakithia-williams). It's a 29×29 code where 410 drones light the squares a printed code would have dark, so it reads light-on-dark. Most newer phone cameras read that, but some don't.

## How it works

`show.py` draws each picture on a small canvas, then spreads 500 points evenly along the lines and fills. For every move between pictures it:

- matches drones to their new spots with the Hungarian algorithm, so total travel stays as short as possible
- bows each drone out into one of 13 depth layers, 2 m apart, so crossing paths pass in front of or behind each other, trying 33 different layer assignments and keeping the one with the most room
- splits the landing into three legs (slide into your landing row, drop to 12 m over your pad, set down) so no paths cross
- stretches the move until the fastest drone stays under 12 m/s (change `MAX_SPEED` in `show.py` to match a real fleet's limits)
- checks the spacing between every pair of drones at 201 points along the move

The numbers from the current build:

| Check | Result |
|---|---|
| Drones | 500 |
| Show length | 1:16 |
| Top speed | 12 m/s |
| Closest pass between any two drones | 1.5 m |
| Max altitude | 95 m |
| Picture width | 150 m |

`check.py` reads the exported flight files back and recomputes speed, spacing and altitude from them, so the numbers above come from the files and not from the plan.

## Run it

```
pip install -r requirements.txt
python show.py            # builds output/show.json and output/drones/*.csv
python check.py sheet.png # re-checks the flight files and draws every formation on one image
python build_preview.py   # puts the show into ../docs/ford-racing/index.html
```

## Files

- `show.py` builds the formations, the flight paths and the safety checks
- `check.py` re-checks the exported paths
- `build_preview.py` and `preview/template.html` make the 3D preview
- `output/drones.zip`: 500 flight files, `drone_001.csv` to `drone_500.csv`, one path per drone at 10 Hz in Skybrush's CSV layout (`Time [msec], x [m], y [m], z [m], Red, Green, Blue`). They're zipped to keep the upload small; `python show.py` also rebuilds them into `output/drones/`.
- `../docs/ford-racing/index.html`: the preview page that GitHub Pages serves

## What this is and isn't

This is a design and simulation. It hasn't been flown. The flight files start with the drones already in the first formation, so a real flight would need a takeoff added in front. Flying it for real would take show drones and their own ground control software, a site plan, and an FAA waiver under 14 CFR 107.35, since one pilot can't fly more than one drone at a time without one. I'm working toward my Part 107 remote pilot certificate now.
