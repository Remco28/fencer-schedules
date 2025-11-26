# FTL Pool Results JSON Sample

**Source:** November NAC 2025 - Division I Men's Épée
**Event ID:** `54B9EF9A9707492E93F1D1F46CF715A2`
**Pool Round ID:** `D6890CA440324D9E8D594D5682CC33B7`
**URL:** `https://www.fencingtimelive.com/pools/results/data/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7`

This file contains a representative sample of the pool results JSON returned by FTL after pool rounds complete. The JSON provides advancement status (`prediction` field) for each fencer.

## Sample Data

```json
[
  {
    "id": "425B00719E2740C18ECEC299142D3CF3",
    "v": 6,
    "m": 6,
    "vm": 1,
    "ts": 30,
    "tr": 9,
    "ind": 21,
    "prediction": "Advanced",
    "name": "IMREK Elijah S.",
    "div": "Gulf Coast",
    "country": "USA",
    "club1": "University Of Notre Dame NCAA",
    "club2": "Alliance Fencing Academy",
    "search": "imrek elijah s.|gulf coast|usa|university of notre dame ncaa|alliance fencing academy",
    "place": 1,
    "tie": false
  },
  {
    "id": "511E4E00E67041D884F44F6F4EF849B7",
    "v": 6,
    "m": 6,
    "vm": 1,
    "ts": 30,
    "tr": 12,
    "ind": 18,
    "prediction": "Advanced",
    "name": "GAO Daniel",
    "div": "New England",
    "country": "USA",
    "club1": "Cavalier Fencing Club",
    "club2": "Boston College NCAA",
    "search": "gao daniel|new england|usa|cavalier fencing club|boston college ncaa",
    "place": 2,
    "tie": false
  },
  {
    "id": "F808AF88F04A481B980EB14B3B1D93E9",
    "v": 5,
    "m": 5,
    "vm": 1,
    "ts": 25,
    "tr": 8,
    "ind": 17,
    "prediction": "Advanced",
    "name": "ELHUSSEINI Dylan",
    "div": "Gulf Coast",
    "country": "USA",
    "club1": "Alliance Fencing Academy",
    "search": "elhusseini dylan|gulf coast|usa|alliance fencing academy",
    "place": 3,
    "tie": false
  },
  {
    "id": "D4F3C8A1B2E547A89C1F2D3E4B5A6C7D",
    "v": 4,
    "m": 6,
    "vm": 0.667,
    "ts": 22,
    "tr": 18,
    "ind": 4,
    "prediction": "Eliminated",
    "name": "SMITH John",
    "div": "Mid Atlantic",
    "country": "USA",
    "club1": "Test Fencing Club",
    "club2": null,
    "search": "smith john|mid atlantic|usa|test fencing club",
    "place": 125,
    "tie": false
  },
  {
    "id": "E5G4D9B2C3F658B9AD2G3E4F5C6B7D8E",
    "v": 3,
    "m": 6,
    "vm": 0.5,
    "ts": 18,
    "tr": 22,
    "ind": -4,
    "prediction": "Cut",
    "name": "JONES Michael",
    "div": "South",
    "country": "USA",
    "club1": "Sample Academy",
    "search": "jones michael|south|usa|sample academy",
    "place": 180,
    "tie": true
  },
  {
    "id": "F6H5E0C3D4G769C0BE3H4F5G6D7C8E9F",
    "v": 2,
    "m": 6,
    "vm": 0.333,
    "ts": 15,
    "tr": 25,
    "ind": -10,
    "prediction": "",
    "name": "DOE Jane",
    "div": null,
    "country": "CAN",
    "club1": "Northern Club",
    "club2": "Second Club",
    "search": "doe jane|can|northern club|second club",
    "place": 250,
    "tie": false
  }
]
```

## Key Fields

- **`id`**: Fencer's unique identifier (32-char hex)
- **`v`**: Victories in pool rounds
- **`m`**: Total matches fenced
- **`vm`**: Victory/Match ratio (float)
- **`ts`**: Touches scored
- **`tr`**: Touches received
- **`ind`**: Indicator (TS - TR)
- **`prediction`**: Advancement status
  - `"Advanced"` = Fencer advances to DEs
  - `"Eliminated"` or `"Cut"` = Did not advance
  - Empty/missing = Unknown/unprocessed
- **`name`**: Fencer's full name
- **`div`**: Geographic division (optional)
- **`country`**: Country code
- **`club1`**: Primary club affiliation
- **`club2`**: Secondary club (optional)
- **`search`**: Internal FTL search string
- **`place`**: Overall placement after pools
- **`tie`**: Whether this placement is a tie

## Notes

- The actual November NAC event had 304 fencers
- Fencers are sorted by placement (ascending)
- `prediction` field is case-sensitive in the wild (`"Advanced"` with capital A)
- Some fields like `div` and `club2` may be `null` or missing
- The parser should normalize `prediction` to lowercase status values
