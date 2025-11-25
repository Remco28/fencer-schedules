# FTL Pool IDs Discovery - HTML Sample

**Source:** November NAC 2025 - Div I Men's Épée
**URL:** `https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7`
**Event ID:** `54B9EF9A9707492E93F1D1F46CF715A2`
**Pool Round ID:** `D6890CA440324D9E8D594D5682CC33B7`
**Date Captured:** 2025-11-20

## HTML Sample (Excerpt)

This is the actual HTML structure from FencingTimeLive containing the pool IDs JavaScript array.

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>FencingTimeLive - Pool Results</title>
    <link rel="stylesheet" href="/static/css/ftl.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>November NAC 2025</h1>
            <h2>Division I Men's Épée - Pool Round</h2>
        </div>

        <div id="poolsContainer">
            <!-- Pool results will be loaded here -->
        </div>

        <script type="text/javascript">
            var eventId = "54B9EF9A9707492E93F1D1F46CF715A2";
            var roundId = "D6890CA440324D9E8D594D5682CC33B7";
            var baseUrl = "/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7";

            // Pool IDs array - this is the key data structure
            var ids = [
                "130C4C6606F342AFBD607A193F05FAB1",
                "BAB54F30F50544188F2EA794B021A72B",
                "30877432D1026706D7E805DA846A32C3",
                "BB81E3C29B62179273C8EB5BB682575E",
                "C87A171AC826A6FCE48478DCB74F2134",
                "5D2CCE8038A39D5E0853964B50AF03B9",
                "71722F244F58D669CBEE3772A0770217",
                "21A278F64F7FD633DBDDE131CA3766E4",
                "D58E72E310275DFF6C15C0C8E9DF4696",
                "11A11F5125227C3712DA86A78C49EA20",
                "E32684B27B95E909348334896A68F812",
                "D810A485ED03241B4D419B1B673BD475",
                "5D05AD7853C1F76EB97706CA828BCA03",
                "85813DBAD3C681D06BD2AA399DAC946D",
                "C59C0996DAEEE6F529A279764017F2ED",
                "6CFC7403D75E173E4EAEDE5FE878F78E",
                "2978AA2447C462DDAED16DC0CF0B9CD7",
                "F78DF0CAC5E40C02D4E518CA6EAAC8D8",
                "2F01B7210760474F36E8B5359309CC62",
                "73931BDB2A0DF3DBE4D58FED8A728E7E",
                "CA0FA5F6B8A880627DF7FFE0297C79BF",
                "BDABE898736A3566F893697B59048119",
                "4F309FFEA518F32CF21449273D7CEE9D",
                "9136682575250DEF91799E2786D37484",
                "21599E3E9C8FE21DA80270815FE85DF2",
                "FBDAA35ADF9C1E2A8A3C0ED16BFE1684",
                "9EF307590D273E34F98DFF7E4C6428DA",
                "8099F4EFBACEA67C7D1AFCC4F14A3E3E",
                "04D42F8AC2ACAF127972D33E5901A19B",
                "BD47D5552C7F47E8E80E952EB9D8E96C",
                "F37CB990C801F97B7684319E1B429AD5",
                "64B858F9A3E247CB2C083EB8CB37F0A7",
                "2E9D34119F3374CEBD4D3FD81B6EE7B3",
                "BB1C863E2601A7462667A40844853040",
                "B7A05814D32FEB3E719E01FCD3FE22A4",
                "248AC9ED336DE7DAECD3ADA8B4F2222D",
                "3B41A3DBD199B364F73BB387D080589A",
                "B054C24026CDEA5B9A2145128EDFED86",
                "3BD39F917C10696489A30FD54C7B2C1D",
                "0E2ADCD93C0A5EB2D37DC2C9A7A5236B",
                "B4734865425FEEAA4E2FE981B29EE11B",
                "922CE1E6AF41E3A2517EE5BB9CDA1A2A",
                "3C984A24B9C429CA42DB0B956AF67442",
                "931A4C4555E1DB7E9E779F6BEE9CD564",
                "81FB339258E4D27EB0D1CB7C2B70A3A4"
            ];

            function loadPoolData() {
                ids.forEach(function(poolId, index) {
                    var poolNum = index + 1;
                    var poolUrl = baseUrl + "/" + poolId + "?dbut=true";
                    // AJAX call to load pool data...
                });
            }

            document.addEventListener('DOMContentLoaded', loadPoolData);
        </script>
    </div>
</body>
</html>
```

## Key Observations

1. **Pool IDs Location:** Line 217 (approx) in the actual HTML
2. **Variable Name:** Exactly `var ids = [...]` (note the spacing)
3. **Format:** Array of 32-character uppercase hex strings (no dashes)
4. **Count:** 45 pool IDs total for this event
5. **Round ID:** Embedded in URLs throughout the page as `D6890CA440324D9E8D594D5682CC33B7`

## Parser Requirements

The parser must:
- Extract the `var ids = [...]` block using regex
- Handle multiline arrays (IDs span many lines)
- Extract 32-character hex UUIDs
- Normalize to uppercase
- Extract the pool round ID from URL context in the HTML
- Be resilient to whitespace variations

## Test Event Details

- **Event:** November NAC 2025 - Div I Men's Épée
- **Event ID:** 54B9EF9A9707492E93F1D1F46CF715A2
- **Pool Round ID:** D6890CA440324D9E8D594D5682CC33B7
- **DE Round ID:** 08DE5802C0F34ABEBBB468A9681713E7
- **Total Pools:** 45
- **Example Pool ID:** 130C4C6606F342AFBD607A193F05FAB1 (Pool #1)
