# Private dedicated QA

These tools create an independent, disposable server fixture from the exact
Caves and Dungeons 1.4 author snapshot. They do not change the shipped pack,
copy a personal world, or prescribe dedicated-server roles for LAN players.
Every launcher participant can still host the ordinary embedded LAN server.

`prepare_server.py` verifies every author JAR and override against the
historical upstream lock, verifies the Forge installer against Forge's
published SHA1, installs Forge 47.3.7, and copies the verified source files.
Read-only library caches are optional; only matching named installer
artifacts are copied from them. The output must be empty and independent from
the shipped pack tree, or inside its ignored `artifacts/` directory.

```powershell
python -B tools/qa-server/prepare_server.py --out <empty-fixture> --java <java17.exe> --installer <forge-1.20.1-47.3.7-installer.jar> --library-cache <existing-libraries>
python -B tools/qa-server/run_server.py --server <fixture> --java <java17.exe>
```

The fixture binds only `127.0.0.1:25586`, uses a new `qa-baseline-world`, and
disables RCON/query. Its generated EULA acceptance is for this authorized QA
run. `run_server.py` requires the fixture marker and loopback properties,
waits for the actual `Done` log, observes another 15 seconds, then sends
`list`, `save-all flush`, and `stop`. A process exit code of zero without
`Done` is a failed test. Logs, crash reports, generated configuration, world
data and `qa-result.json` stay inside the fixture. This check does not assert
which world preset was used and does not substitute for a complete client
or embedded LAN check.

## Baseline result, 2026-10-26

The original 93-JAR snapshot on Minecraft 1.20.1, Forge 47.3.7 and Java
17.0.20.1 **failed before world creation** during mod construction. No
`Done`, world save or graceful shutdown was observed; Forge exited after
its crash report despite process exit code zero.

Two concrete causes were observed:

- Oculus 1.8.0 attempts to load the client `Screen` class on
  `DEDICATED_SERVER`. Its shader-rendering JAR is a valid client-only
  exclusion for this private fixture, and remains in the ordinary client
  distribution.
- Copperative 1.1.0 is shared content and must remain. Its constructor
  unconditionally registers `DynamicCopperativeDataPack` at source line 40.
  That class's constructor initializes `DynamicCopperativeResourcePack`,
  which invokes Moonlight's `DynClientResourcesGenerator` on the dedicated
  side. Moonlight's native guard throws `Client only class registered on
  server side! Issue from modcopperative` at source line 26.

The original Copperative JAR SHA256 is
`7d010e86e2aa2a34a531c54a629b385b831473080d8a08f98585f62bb710e3bb`.
The original Oculus JAR SHA256 is
`0945df0cba0f62b3901dd80c3268e5311b770ece78c78037a45db12ac0425fef`.
Neither JAR was patched, replaced or removed from the source pack.

A second bounded attempt moved only Oculus aside in the disposable fixture.
Copperative then remained the single fatal mod-construction failure; its
exact exception chain was unchanged. `Spec for CaD` and all other shared
world logic stayed present. This establishes that the untouched author
snapshot is not supported as a private dedicated server in this tested
combination. It says nothing conclusive about the separate embedded LAN
path, which runs on the client physical side.

Additional observed ERROR messages include YACL's missing mixin
`minVersion`, a dedicated-side attempt to load the client `Sheets` class,
and Zeta's client-event interface discovery. Missing optional compatibility
classes were also logged. These observations are retained separately from
the proven Copperative fatal chain; they are not silently suppressed or
declared harmless by this failed run.

The reviewed fixture-only exclusion is in `client-only-exclusions.json`.
For an already staged failed fixture, preserve its original observation and
apply the exact-hash exclusion before a second run:

```powershell
python -B tools/qa-server/apply_exclusions.py --server <fixture>
python -B tools/qa-server/run_server.py --server <fixture> --java <java17.exe>
```

`apply_exclusions.py` verifies all moves before changing the fixture, keeps
the first console/result/stage files in `qa-attempt-original93`, and moves
the JAR only into that fixture's `excluded-client-mods`. It never deletes a
mod or changes the historical upstream lock. For a new fixture, pass the
same JSON to `prepare_server.py --exclusions` instead.

Later launcher changes, including a separately authorized Xaero's World Map
update, are outside this baseline. The final shipped candidate needs its
own recorded acceptance; this failed dedicated baseline is not a PASS for
that candidate.

## Helper-only dedicated proof, 2026-10-26

A separate fixture loaded only `cad-world-type-lock-1.0.0.jar`, SHA256
`74c5db7e8382a8a9096e15df100699e9ceaf2067cf2c6c3f4610c243072318b1`,
with Minecraft 1.20.1, Forge 47.3.7 and Java 17.0.20.1. Its 104 native
library files were independently copied and verified; none of the author's
93 JARs was included. This fixture bound `127.0.0.1:25588` and requested
`level-type=caves_and_dungeons:modded_mines` for a new `qa-helper-world`.

The native server reached `Done`, ran another 15 seconds, accepted
`save-all flush` and `stop`, saved all dimensions and exited with code 0.
No ERROR/FATAL, client-class invalid-dist, linkage failure or preset/registry
parse failure was observed. Total observed process lifetime was 48.8 seconds.

Native `DedicatedServerProperties.WorldDimensionData` bytecode was inspected:
an absent selected preset invokes the fallback method that logs
`Failed to parse level-type ..., defaulting to ...`. That marker was absent
while the fresh world reached `Done`. Together with the exact single-helper
fixture, this confirms that the named preset was recognized and decoded by
the native server rather than silently falling back.

This is **only a PASS for the helper's dedicated physical-side loading and
native preset registration/decoding**. It does not override the original
pack's Copperative failure or prove the full shipped pack, client creation
UI, embedded LAN, author mod generation, cave appearance or visual output.
The helper's preset JSON preserves the ordinary three-dimension generators;
no special cave terrain is inferred from its name.

Evidence remains in the ignored `helper-dedicated` fixture: `qa-stage.json`,
`qa-console.log`, `qa-result.json`, `native-preset-selection-bytecode.txt` and
`helper-native-preset-proof.json`. `run_server.py --port 25588` selects this
fixture's port while retaining loopback and free-port checks. The process
completed, and the port was released.

The final helper was separately rerun after its client-constructor edge was
corrected: SHA256
`53068fe81266ad9a0679a7499d2e36f3f21f25b6fe3a832b16772c815b64efa4`,
18,407 bytes. The fresh `helper-dedicated-final` fixture again contained only
that helper and the same verified Forge 47.3.7 native libraries. With
`caves_and_dungeons:modded_mines`, it reached `Done`, ran another 15 seconds,
flushed/saved all dimensions and stopped normally with exit 0 (55.09 seconds
total). No ERROR/FATAL, invalid client-class dist or preset fallback was
observed; `level.dat` was created. The port was released.

Final exact-hash evidence is in that fixture's
`helper-native-preset-proof.json`, `qa-result.json`, `qa-stage.json` and
`qa-console.log`. This supersedes the older helper hash for final dedicated
side evidence. Neither dedicated run verifies the client constructor or
creation UI; those remain separate full-client checks.
