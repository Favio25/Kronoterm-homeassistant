# Kronoterm issue audit and v1.6.9 fix validation

## v1.7.0 follow-up hardening

Version 1.7.0 completes the safe follow-up work identified by this audit:

- Energy and calculated-power unique IDs are config-entry scoped, with a
  migration that preserves existing entity IDs while allowing multiple Cloud
  accounts.
- Setup flows prevent duplicate Cloud accounts and Modbus endpoints; account
  identifiers are hashed so usernames are not stored in unique IDs.
- Cloud reauthentication, transport-specific options, immediate option reloads,
  redacted diagnostics, and disabled-by-default connection-health sensors were
  added.
- Modbus setup validation now uses the same one-based address conversion and
  fixed-transaction-ID packet normalization as runtime polling.
- Kronoterm's corrected previous-day totals are exposed as new current-state
  sensors. Historical entity states are deliberately not rewritten.
- Eighteen offline regression tests and an isolated Home Assistant 2026.7.3
  startup verified both the Cloud and Modbus entries with no runtime errors.

Cascade support and speculative register remapping remain deliberately deferred
until representative hardware or payload data is available.

Audit date: 2026-07-22

Baseline: repository `main` at `4e4ff34`, integration version 1.6.7. The local
fix candidate is version 1.6.9. Testing used read-only Cloud and Modbus TCP
polls in the isolated Home Assistant Core 2026.7.3 instance at
`127.0.0.1:18123`. No production Home Assistant files were used, no credentials
were recorded, no packets were captured, and no heat-pump controls were
operated.

## Findings and implementation status

| Issue | Assessment | v1.6.9 action |
|---|---|---|
| #51 Multiple accounts overwrite each other | Confirmed source defect; two Cloud accounts were not available for direct reproduction | Each Cloud entry now receives an auto-cleaned private Home Assistant client session and cookie jar. |
| #52 Login failure, duplicates, missing metrics | Authentication mismatch and incorrect SCOP/energy decoding confirmed | Config flow and runtime now share the BasicAuth-then-PHP-session helper. SCOP uses three decimals. Both energy words are combined and the documented electrical/thermal register labels are restored. |
| #53 Loop 2 temperature missing | Not reproduced; current readings match disabled loops and a disconnected thermostat | No thermostat or Modbus address mappings were changed. Optional Cloud pages now fail independently, preventing one unsupported page from discarding valid sibling responses. |
| #54 Duplicate entities and login selection | Duplicate presentation confirmed; no duplicate unique IDs on a fresh installation | Status/control and measured/climate entities now have distinct display names in English, German, Italian, and Slovenian. The duplicate DHW `boiler_temp` sensor was removed. Config-entry migration preserves the older canonical `dhw_current_temperature` unique ID and removes or migrates the later duplicate registry entry. |
| #23 Previous-day energy correction | Deferred; no reliable overnight fixture | No historical-energy behavior was changed. |
| #21 Cascade support | Deferred; no representative cascade installation or payload | No cascade behavior was added. |

The Cloud response logger was also changed to record only request metadata and
payload size. It no longer dumps device payloads into debug logs.
Modbus TCP responses with the controller's fixed transaction ID are normalized
to the active serialized request ID so polling continues on current pymodbus.

## Validation

- Home Assistant loaded the patched integration as version 1.6.9.
- Cloud authentication failed its legacy BasicAuth handshake as before, then
  succeeded through the shared PHP-session fallback.
- Cloud and Modbus entries both initialized after repeated container restarts.
- The registry still contains 131 entities: 65 Cloud and 66 Modbus, with no
  disabled entries and no duplicate `(platform, unique_id)` pairs.
- Live display names now distinguish `Additional Source Status` from
  `Additional Source Control`, and `DHW Temperature` from `DHW Thermostat`.
- Both Cloud and Modbus now report SCOP `5.413`, electrical energy `19380.0 kWh`,
  and thermal energy `104907.9 kWh`; the energy ratio also equals `5.413`.
- JSON parsing, `git diff --check`, and all eleven offline
  regression/deferred-behavior tests pass.

## Deliberately unchanged

- Loop 2 thermostat values and Modbus address mappings (#53).
- Cascade discovery, membership, aggregation, and controls (#21).
- Previous-day entity/statistics correction (#23).
- COP scaling remains at two decimals because the compressor was idle during
  testing and there is no evidence that COP uses the SCOP counter's format.

## Remaining optional checks

- Two simultaneous standard-Cloud accounts with distinct `hp_id` values.
- A DHW-Cloud account to exercise the registry migration on real legacy data.
- Recorder/source snapshots around midnight for #23.

## Credential and capture policy

No Cloud credentials or packet capture are required. A full capture is avoided
because HTTP authorization headers and session cookies may be recoverable from
it. If another account is needed later, it should be added by the user through
the isolated Home Assistant UI; credentials should not be sent to the tester.
