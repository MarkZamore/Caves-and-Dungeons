# Тип мира «Шахты с Модами»

Согласованный пользователем новый настоящий preset имеет ID `caves_and_dungeons:modded_mines`, русское название «Шахты с Модами» и английское `Modded Mines`. Это наше дополнение к публичной сборке, а не восстановленный неизвестный генератор из ролика. Все три dimensions описаны так же, как в native `minecraft:normal`: сохраняются авторские пещеры, стартовый бункер и опасная поверхность, добавленные исходными модами. Helper не меняет рецепты, геометрию пещер, biome-generation настройки и правила этих модов.

`cad_world_type_lock` версии `1.0.0` рассчитан на Minecraft 1.20.1, Forge 47.3.7 и Java 17. Общий entrypoint не содержит client imports. Preset и data tags загружаются также на dedicated server; обязательные mixin перечислены только в секции `client`.

После каждого штатного обновления `WorldCreationUiState` оба списка типов мира, включая альтернативный с Shift, состоят из одного preset. При первоначальном конструировании dimensions применяются только в обязательном constructor-RETURN hook, когда seed, генерация строений и бонусный сундук уже инициализированы; раннее обновление списков их не переписывает. Перед `CreateWorldScreen.onCreate` helper повторно применяет preset до native bake и записи мира. Seed и прочие независимые опции сохраняются. Это распространяется на пересоздание и reload datapack. Открытие существующих и импортированных сохранений не проходит через эти точки и не ограничивается.

Если preset отсутствует, оба списка получают единственный незаполненный placeholder с подписью «Шахты с Модами (недоступно)». Он нужен, чтобы штатный `CycleButton` не получил пустой список. Создание отменяется до записи сохранения с локализованным сообщением о восстановлении файлов сборки. Другой генератор не применяется как запасной вариант. Отключение или удаление обязательного helper вручную не является поддерживаемой конфигурацией сборки.

Проверка Safety: helper добавляет выбор начального world preset и ограничение экрана создания. Он не вводит способности, владельцев, отложенные действия, runtime-запись блоков/chunk/palette или очистку инвентаря. Начальная генерация остаётся native normal с исходными базовыми модами; перенос Safety из другой сборки не требуется.

## Сборка и native-проверки

Для побайтового воспроизведения нужен Microsoft JDK 25.0.2; `javac --release 17 -g:none` выпускает Java 17 bytecode. Python 3.12 скачивает только два публичных Forge/Mixin compile JAR из `build-dependencies.json` и проверяет их SHA256. Minecraft JAR не входят в compile-зависимости и не распространяются этим инструментом. Reflection привязана к точным SRG-методам; соответствие им проверяется отдельно на настоящих Minecraft/Forge классах.

```bash
python tools/world-type-lock/build_helper.py --output artifacts/world-type-lock
```

CI использует `actions/setup-java` с `distribution: microsoft`, `java-version: 25.0.2`, затем ту же команду с `--verify-installed mods/cad-world-type-lock-1.0.0.jar`. Сборка не устанавливает и не публикует JAR. Canonical ZIP_STORED, фиксированные timestamps и платформа ZIP, отсортированные записи и LF ресурсов делают результат одинаковым на Windows и Linux. Выход: `artifacts/world-type-lock/cad-world-type-lock-1.0.0.jar`.

Локальные native-проверки используют подготовленные точные Minecraft 1.20.1/Forge 47.3.7 библиотеки и Java 17. Выполнять из корня сборки:

```powershell
$qaLauncher = Join-Path $env:USERPROFILE 'Documents\LANMinecraft\artifacts\caves-and-dungeons\baseline\Minecraft\Launcher'
python tools/world-type-lock/build_helper.py --output artifacts/world-type-lock --jdk 'C:\Tools\jdk-25.0.2' --native-shared (Join-Path $qaLauncher 'Shared') --native-java (Join-Path $qaLauncher 'JavaRuntimes\runtime\windows-x64\java-17\bin\java.exe')
```

`NativeResourcesTest` разбирает pack.mcmeta настоящим metadata serializer и JSON preset настоящим Minecraft WorldPreset codec, сравнивает полное native-представление с `minecraft:normal` и проверяет RU/EN названия. Для чистого vanilla registry bootstrap SRG стоит первым, `client-extra.jar` даёт родные ресурсы. Это не подменённые игровые fixtures. `MixinTransformTest` отдельно ставит Forge-client первым, проверяет SHA256 трёх target и применяет настоящий установленный Mixin transformer: обязательные вызовы ровно один раз, TAIL для списков, отменяемый HEAD для создания/подписи. Offline native-проверки не означают PASS полного клиента, мира или dedicated server; фактическая игровая приёмка фиксируется отдельно.

## Пассивный QA observer

`build_observer.py` собирает необязательный QA Java agent для клиента Minecraft 1.20.1. Он читает открытый `CreateWorldScreen`, список registry preset ID, выбранный holder и оба списка выбора. Снимки выполняются в игровом потоке и записываются только при изменении наблюдаемого состояния в JSONL под `artifacts`. Agent не добавляет transformer, не открывает экраны, не меняет выбранный preset и не создаёт мир. Для сборки не нужны Forge/ASM или игровые JAR.

```powershell
$observerRoot = Join-Path $env:USERPROFILE 'Documents\LANMinecraft\artifacts\caves-and-dungeons\world-type-observer'
python tools/world-type-lock/build_observer.py --output $observerRoot
```

Проверку исходной сборки сначала выполнить без observer. Затем подключить agent только к точно установленному PID согласованного QA-клиента:

```powershell
$observerJar = Join-Path $observerRoot 'cad-world-type-observer-1.20.1-0.1.0.jar'
$observerOutput = Join-Path $observerRoot 'presets.jsonl'
& 'C:\Tools\jdk-25.0.2\bin\java.exe' -cp $observerJar dev.lanminecraft.cadqa.AttachObserver <PID> $observerJar $observerOutput
```

После подключения открыть штатный экран создания мира. `registryIds`, `selected`, `normal` и `alternative` дают фактические ID и локализованные названия. Для остановки только observer создать файл `<observerOutput>.stop`; игра продолжает работать. Этот QA JAR не помещать в `mods` и не включать в поставку.

Исходный запуск до добавления helper подтвердил только шесть ванильных preset и отсутствие отдельного «Ультра Пещеры». После согласования геометрии пользователь выбрал описанный выше новый preset «Шахты с Модами». Observer сохраняется как независимый инструмент проверки исходного и итогового клиентов.
