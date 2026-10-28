# FTB Quests: состав, формат и границы Safety

Проверено 28 октября 2026 года для Minecraft 1.20.1, Forge 47.3.7 и Java 17. Источники файлов принадлежат FTB Team. Это проверка метаданных, конкретного байткода и используемых путей; результат полного клиента, мира и локализации фиксируется отдельно в `TESTING-STATUS.md`.

## Новые компоненты

Ни один существующий авторский JAR для установки квестбука не обновляется. Имеющаяся Architectury 9.2.14 удовлетворяет требованиям всех трёх компонентов. Все три новых mod ID относятся к NEW; их последующие обновления не превращают их в BASE.

| Mod ID | Версия и файл | CurseForge project/file | Размер, байт | SHA256 |
| --- | --- | --- | ---: | --- |
| `ftbquests` | `ftb-quests-forge-2001.4.22.jar` | 289412 / 8078538 | 1255469 | `9ea9d159a78a2724cfe0457b024680fdb52a2126eff9cfa5280a30578f647a68` |
| `ftblibrary` | `ftb-library-forge-2001.2.13.jar` | 404465 / 8226927 | 780558 | `41810281b65336265cae2c88412022d02f2f0a3f28c66a06173d86f98acf14a7` |
| `ftbteams` | `ftb-teams-forge-2001.3.2.jar` | 404468 / 7499810 | 252579 | `b1cb4d82ea9f137a87e12a7aaf3329619294b56f7d70337dfd557a76e10b6e07` |

Официальные страницы и проверенные файлы:

- [FTB Quests](https://www.curseforge.com/minecraft/mc-mods/ftb-quests-forge), [файл 8078538](https://www.curseforge.com/minecraft/mc-mods/ftb-quests-forge/files/8078538), [официальный CDN](https://edge.forgecdn.net/files/8078/538/ftb-quests-forge-2001.4.22.jar).
- [FTB Library](https://www.curseforge.com/minecraft/mc-mods/ftb-library-forge), [файл 8226927](https://www.curseforge.com/minecraft/mc-mods/ftb-library-forge/files/8226927), [официальный CDN](https://edge.forgecdn.net/files/8226/927/ftb-library-forge-2001.2.13.jar).
- [FTB Teams](https://www.curseforge.com/minecraft/mc-mods/ftb-teams-forge), [файл 7499810](https://www.curseforge.com/minecraft/mc-mods/ftb-teams-forge/files/7499810), [официальный CDN](https://edge.forgecdn.net/files/7499/810/ftb-teams-forge-2001.3.2.jar).

Несмотря на нынешнее название проектов «NeoForge» на сайте, указанные конкретные файлы имеют Forge 1.20.1 в официальных метаданных и `META-INF/mods.toml`. Устанавливаются именно они. Размеры и SHA256 вычислены по скачанным байтам, а не по названию страницы. Максимальная версия classfile во всех трёх JAR равна 61 (Java 17); встречающиеся классы 52 также совместимы с Java 17.

Требования прочитаны из `mods.toml` этих точных JAR:

| Компонент | Обязательные зависимости и диапазоны | Сторона |
| --- | --- | --- |
| Quests | Minecraft `[1.20.1,)`, Architectury `[9.0.8,)`, FTB Library `[2001.2.1,)`, FTB Teams `[2001.1.4,)` | `BOTH` |
| Library | Forge `[47.3,)`, Minecraft `[1.20,)`, Architectury `[9.0.8,)` | `BOTH` |
| Teams | Forge `[47.1.47,)`, Minecraft `[1.20.1,)`, Architectury `[9.1.12,)`, FTB Library `[2001.2.0,)` | `BOTH` |

В Library связь с Quests `[2001.4.8,)` необязательная и задаёт порядок. У Quests Item Filters `[2001.1.0-build.55,)` имеет `mandatory=false`. FTB XMod Compat отсутствует среди обязательных зависимостей. Для встроенных задач `advancement`/`checkmark` и обычных item ID иконок эти два мода не нужны. Выбранный квестбук не использует их фильтры, wildcard-предметы, Game Stages или сторонние task types. Иконка разбирается собственным `NBTUtils.read`, который передаёт ItemStack в `MissingItem.readItem`, без обращения к Item Filters.

## Формат и зачёт достижений

В точном Quests 2001.4.22 статический инициализатор `dev.ftb.mods.ftbquests.quest.BaseQuestFile` устанавливает `VERSION = 13`. `data.snbt` использует `version: 13`. Это формат линии 1.20.1; layout ItemStack из TerraFirma Rebirth 2 для Minecraft 1.21.1 сюда не переносится.

`dev.ftb.mods.ftbquests.util.NBTUtils.read(CompoundTag,String)` принимает `icon: "minecraft:stone"` либо старый ItemStack `{ id: "minecraft:stone", Count: 1b, tag: {...} }`. Строковый ID достаточен для обычной иконки. Поле `components` из 1.21.1 здесь не является заменой `tag`.

Задача достижения:

```snbt
{
    id: "0123456789ABCDEF"
    type: "advancement"
    advancement: "minecraft:story/mine_stone"
    criterion: ""
}
```

`AdvancementTask.readData` читает `advancement` и `criterion`; пустой `criterion` означает всё достижение. `canSubmit(TeamData,ServerPlayer)` на сервере получает достижение по точному ID через `ServerAdvancementManager.getAdvancement`, затем вызывает `PlayerAdvancements.getOrStartProgress`. При пустом критерии возвращает `AdvancementProgress.isDone`; при непустом использует `getCriterion(...).isDone`. Несуществующий ID возвращает `false`.

Точные SRG вызовы в данном Forge JAR: `MinecraftServer.m_129889_`, `ServerAdvancementManager.m_136041_`, `ServerPlayer.m_8960_`, `PlayerAdvancements.m_135996_`, `AdvancementProgress.m_8193_`; для отдельного критерия `AdvancementProgress.m_8214_` и `CriterionProgress.m_12911_`. Метод читает сохранённый прогресс, не выдаёт само достижение.

`AdvancementTask.autoSubmitOnPlayerTick()` возвращает 5. `FTBQuestsEventHandler.playerTick(Player)` для настоящего `ServerPlayer` получает team data, отклоняет locked team, проверяет `gameTime % 5 == 0`, незавершённость задачи и `TeamData.canStartTasks(quest)`, затем вызывает `Task.submitTask`. Поэтому уже выполненное достижение засчитывается после появления квестбука или открытия зависимости, без повторного получения достижения. Пять тиков означают примерно 0,25 секунды при 20 TPS; пауза и отставание сервера увеличивают реальное время. Это вывод из точного байткода, не заявление о непроведённом игровом сценарии.

Квесты используют устойчивые ID и `progression_mode: "flexible"`, чтобы игрок мог выполнять действия заранее. Зависимости задают порядок прохождения; сохранённый advancement остаётся доступен для последующего зачёта. FTB Teams хранит прогресс команды; книга не обещает изолированный прогресс каждого участника внутри общей FTB-команды.

## Проверка необходимости Safety

Для этого квестбука изменение Safety не требуется. Задачи достижений только читают `PlayerAdvancements`, задачи отметки меняют FTB progress. В поставляемых квестах нет reward-объектов, команд, выдачи XP/предметов, потребления предметов, процедур разрушения/очистки inventory, caster/owner ability или отложенных записей chunk/palette. `emergency_items` пуст, `drop_loot_crates` выключен. Изменяется сохранение FTB quest/team data, а не существующие registry ID исходных модов. Новые task-screen/barrier/loot-crate блоки FTB не размещаются книгой и не участвуют в её цепочках.

При этом сами FTB JAR содержат административные возможности. Их наличие проверено отдельно, а не скрыто за утверждением о пассивном квестбуке:

- Library 2001.2.13: `FTBLibraryCommands.registerCommands` ставит `requires` на корневой `/ftblibrary`; точный `lambda$registerCommands$0` вызывает `CommandSourceStack.m_6761_(2)`. Изменение времени/погоды, gamemode и NBT находится за этим разрешением.
- Library 2001.2.13: `net.EditNBTResponsePacket.handle` повторно проверяет `ServerPlayer.m_20310_(2)` до побочного эффекта, затем сравнивает полученный `info` с удаляемой серверной записью `FTBLibraryCommands.EDITING_NBT` для UUID отправителя. Только после этого разрешены `BlockEntity.load`, `Entity.load`, изменение player NBT или предмета в руке. Проверка одного command gate не использовалась как доказательство packet gate.
- Quests 2001.4.22: `net.EditObjectMessage.handle` требует `util.NetUtils.canEdit`, который получает player и `TeamData.getCanEdit(player)`, до `QuestObjectBase.readData`/сохранения. `integration.PermissionsHelper.hasEditorPermission(ServerPlayer,boolean)` принимает permission level 2 через `m_20310_(2)` либо явное `ftbquests.editor` от provider. `net.GiveItemToPlayerMessage` проверяет этот метод с default `false` внутри queued callback до `ItemStackHooks.giveItem`. Сама очередь не предоставляет permission.
- Quests 2001.4.22: `net.GetEmergencyItemsMessage.handle` выдаёт только `ServerQuestFile.getEmergencyItems()` с cooldown. Для данного профиля список пуст. Отсутствие reward-объектов также исключает вызов command/item/XP reward из пользовательского прохождения.
- Teams 2001.3.2: `net.UpdatePropertiesRequestMessage.handle` получает команду отправителя через `getTeamForPlayer`; `lambda$handle$0` требует `AbstractTeam.isOfficerOrBetter(senderUUID)` до `updatePropertiesFrom`.

Эти проверки относятся к указанным SHA и конкретному набору задач. Они не сертифицируют произвольные награды, внешние scripts/tasks или администраторов с выданными правами. При добавлении наград, item/fluid consumption, стороннего task type, world-writing integration либо обновлении любого FTB JAR проверку Safety необходимо повторить. Наличие только mod ID в индексе не доказывает покрытие прямых world/inventory путей.

## Источники и воспроизведение проверки

Для чтения логики использованы официальные исходники FTB, затем существенные ветви сверены через `javap -c -p` с тремя JAR по SHA выше:

- [AdvancementTask, Quests snapshot](https://github.com/FTBTeam/FTB-Quests/blob/a74ee04bf80e7fba2c8475112a07ace4a4abd0a6/common/src/main/java/dev/ftb/mods/ftbquests/quest/task/AdvancementTask.java).
- [FTBQuestsEventHandler, тот же snapshot](https://github.com/FTBTeam/FTB-Quests/blob/a74ee04bf80e7fba2c8475112a07ace4a4abd0a6/common/src/main/java/dev/ftb/mods/ftbquests/FTBQuestsEventHandler.java).
- [Library commands snapshot](https://github.com/FTBTeam/FTB-Library/blob/a5e77c17763c56b1fda75a11e24849f9fee92fb1/common/src/main/java/dev/ftb/mods/ftblibrary/FTBLibraryCommands.java).
- [Teams properties packet snapshot](https://github.com/FTBTeam/FTB-Teams/blob/f7dcaa9c6645ff6d0e0613c48b0836572224c8a6/common/src/main/java/dev/ftb/mods/ftbteams/net/UpdatePropertiesRequestMessage.java).

Команда для каждого исследуемого класса: `javap -classpath <точный-JAR> -c -p <полное-имя-класса>`. `META-INF/mods.toml` читается из того же архива. Локальные скачанные metadata, JAR и байткодные отчёты хранятся в игнорируемом `artifacts/ftb-research`; в этот документ не включены личные пути, игровые логи и данные миров.

Проверка настоящего клиента должна отдельно подтвердить русский `Language`, загруженные display-компоненты достижений, синхронизацию FTB книги, отсутствие rewards, отрицательный результат до достижения, зачёт после достижения и зачёт старого прогресса после reload/открытия зависимости. Нативный разбор SNBT, совпадение ranges и офлайн байткод не заменяют такой результат.
