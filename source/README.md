# source/

Put the authoritative brief here as **`source/source_campaign.pdf`**, then run:

```bash
python scripts/studio.py ingest
```

This writes `source/extracted/source_campaign.txt` and `output/reconciliation.json`
(where each of the 22 video ids appears, nearby durations, ids in the PDF that are
not planned and vice-versa). Scripts are then transcribed into `plans/videos/*.json`
and reviewed — nothing is auto-invented.
