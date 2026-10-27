# Open Football integration (build-time)

Open Football resolves synthetic outcomes from Luna XI's fictional database; Luna XI rebuilds the spatial detail for replays.
The app only reads the five normalised packages.

```bash
make open-football-bootstrap
make open-football-fictional-db
python services/simulator-adapter/openfootball_adapter.py convert --of-json services/simulator-adapter/sample_openfootball_export.json --scenario m1-comeback --out /tmp/m1.json
```
