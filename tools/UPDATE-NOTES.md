# Xaero's World Map update review

Reviewed 2026-10-26 for the separately authorized World Map update. This is
a static inspection of the actual candidate JARs, not a runtime PASS.

| Component | Version and source | SHA256 |
| --- | --- | --- |
| Original World Map, BASE mod ID `xaeroworldmap` | 1.39.2, [CurseForge file 5987149](https://www.curseforge.com/minecraft/mc-mods/xaeros-world-map/files/5987149) | `207895a2f0d04e128b952d959855dfb9582eb2176bd840045a74b2f9debf35ee` |
| Candidate World Map, same BASE mod ID | 1.47.0, [CurseForge file 9067273](https://www.curseforge.com/minecraft/mc-mods/xaeros-world-map/files/9067273) | `88c6d844163c95a94d92bc6d87d9011cc840bd6207c3099a81b113d4450a3f6b` |
| Newly supplied dependency, NEW mod ID `xaerolib` | XaeroLib 1.7.3, nested `META-INF/jarjar/xaerolib-forge-1.20.1-1.7.3.jar` | `99fa706a2b8d6a1cc27390639a09fe366c084e34b5614a4b96992522ca425a96` |

## Native compatibility and dependency

Both candidate JARs declare Forge/FML `[46,48)` and Minecraft
`[1.20,1.20.1]`, including this pack's Forge 47.3.7/Minecraft 1.20.1.
Their 711 classes have major version at most 61, compatible with Java 17.
These checks do not prove a complete client launch.

The map requires `xaerolib [1.0,)`. Its actual JarJar descriptor supplies
XaeroLib 1.7.3 with selection range `[1.7.0,1.8)`: no standalone XaeroLib or
other common library update is required. Optional Open Parties and Claims,
Minimap and Better PVP integrations are absent.

## World mutation and Safety decision

Native method/field references and concrete teleport, inventory,
chunk-reflection, server mixin, handshake and permission/config paths were
inspected with `javap`. No direct block/chunk/palette mutation, inventory
clear/removal, entity damage/spawn or `ServerPlayer` teleport call was found.

`Misc.hasItem` reads inventory lists. `MapWriter.writeChunk` writes map
tiles and the injected `xaero_wm_chunkClean` boolean. The world-save reader
requests Minecraft's normal chunk save before reading region data. Server
mixins add Xaero's own data fields. These paths do not edit terrain.

`MapTeleporter.teleport` and `PlayerTeleporter.teleport` format the configured
command and submit it through the actual local player's
`ClientPacketListener` command/chat route, preserving native server command
permissions. Optional claim/unclaim/anchor actions use Open Parties and
Claims' client request API; that absent mod's authorization was not tested.

This pack has no Modified Safety framework. No new caster-based terrain or
inventory ability requiring a Safety module was identified; no transplant
is needed. World Map stays BASE, while the bundled dependency stays NEW.

## Native config permission qualification

XaeroLib checks packet direction and preserves the real sender through
`enqueueWork`. Profile edit/delete/info/request paths check
`hasServerProfileEditPermission`, computed from that player's operator
level 2 or `EDIT_SERVER_PROFILES`. Adapters include Forge permissions, FTB
Ranks, Prometheus and dedicated-side LuckPerms; optional providers are absent.

The creation path has a separate static concern:
`ConfigProfileCreatePacket.ServerHandler` calls
`ServerPlayerConfigSynchronizer.onCreateConfigProfilePacket`, which calls
`ServerConfigChannelSynchronizer.onCreateConfigProfilePacket(id,name,copy)`
without retaining the sender. No equivalent permission check precedes
add/copy/name/save, and an existing ID can be reused. Therefore universal
config permission gating is not established. This affects own server config;
terrain/inventory bypass or practical packet exploitation was not shown.

Client/world acceptance, LAN, old map-cache migration and adversarial packet
testing remain separate. The original dedicated Copperative failure is not
a result for this updated candidate.
