# Public evidence boundary

The maintainer's acceptance archive is private. It contains operational records and
recordings that are not needed to run this source. Only the pre-existing sanitized
historical response-loss replay input required by the offline tests is included.
Its original identities/times/mode are preserved. Replaying it is recorded replay,
not a new transaction or fresh verification. Do not infer completion from this file.

Run `python3 -m unittest discover -v` after building the frontend for the source
regressions. The strict `scripts/check_completion.py` acceptance gate additionally
requires the private canonical verification records and bound artifacts. This public
source checkout intentionally cannot reproduce that private artifact audit.
