# Native client QA

Инструмент запускает проверки настоящих экранов и integrated server Minecraft 1.20.1 / Forge 47.3.7 через их реальные SRG API. Он не использует computer-use, физический ввод, transformer или подмену классов. JAR не поставляется в `mods`.

Тесты выполняются только по явно переданному PID и конфигурации независимого стенда внутри `artifacts`. Перед действиями сверяется реальная `Minecraft.gameDirectory`. Создаваемые миры имеют префикс `CAD-QA-`; существующие личные миры не используются. У каждого запуска нужен новый файл вывода.

## Сборка и подключение

```text
python tools/qa-client/build.py --jdk <JDK> --output <artifacts/qa-client>
java -cp <agent.jar> dev.lanminecraft.cadqa.AttachClientChecks <PID> <agent.jar> <qa.properties>
```

UTF-8 файл `qa.properties` содержит:

```properties
gameDirectory=<absolute-artifacts-game-directory>
output=<absolute-artifacts-evidence-file.jsonl>
inputSnapshot=<absolute-artifacts-input-snapshot.json>
world=CAD-QA-Final-Custom
mode=create-locked
seed=2718281828459045235
```

Значения Windows-путей записывайте через `/`, чтобы `Properties` не интерпретировал `\` как escape. `inputSnapshot` закрепляет фактически подготовленный состав; SHA256 этого файла записывается в первый результат.

- `create-normal`: исходная генерация без helper; создаёт обычный мир и проверяет реальный seed, генератор, игрока, небольшой снимок блоков вокруг него и публикацию integrated LAN.
- `create-locked`: проверяет оба списка, точное имя «Шахты с Модами», дефолты structures/bonus, сохранность независимых настроек, roundtrip трёх штатных вкладок, настоящий reload datapack и повторное применение пресета перед созданием после попытки выбрать flat.
- `load-existing`: открывает подготовленный независимый мир через `WorldOpenFlows`, без экрана создания. Для проверки чужого типа используйте отдельный чисто сохранённый flat fixture; его генератор ожидаемо отличается от noise.
- `recreate`: дополнительно требует `sourceWorld=CAD-QA-...`; читает реальный мир штатным `recreateWorldData` и открывает настоящий `createFromExisting`. Новый мир должен получить обязательный пресет, а исходный не переписывается.
- `missing-required`: только в ещё не использованном native creation context удаляет одну запись обязательного пресета из настоящего `MappedRegistry.byKey`, затем вызывает реальные `updatePresetLists` и `onCreate`. Проверяет единственный недоступный placeholder в обоих списках, локализованный `AlertScreen`, отсутствие нового мира и отсутствие integrated server. Это явная fault injection в одноразовой памяти стенда; production JAR и файлы сборки не меняются.

Для повторного присоединения после ошибки самого тестового инструмента допустим `--revision 2` с новым каталогом сборки и новым файлом результата. Это создаёт отдельный Agent-Class; классы игры не переопределяются. Уже начатые миры не переиспользуются.

## Границы доказательств и завершение

`completed` требует реального входа клиента, native world data, публикации LAN и сохранённого `level.dat`. Публикация LAN не означает вход второго клиента. Визуальная оценка, каждое действие игрока и dedicated server отдельно не подтверждаются этим инструментом. Каждый сбой имеет событие `failed`; не заменяйте его PASS лишь по факту появления файлов.

Завершение повторяет нативный порядок: `ClientLevel.disconnect()` перед `Minecraft.clearLevel()`, затем `Minecraft.stop()`. Если общий сервер завис в модовом callback, сохраняйте точный stack отдельно и не выдавайте непроведённое graceful shutdown за успех. Нельзя копировать незакрытый мир.

`--agent title-stop` собирает ограниченный native-stop для клиента без загруженного мира/сервера. `--agent server-stop` собирает отдельное восстановительное завершение только мира `CAD-QA-*` через штатный halt/save. Для этих двух JAR используется `AttachNativeStop <PID> <stop.jar> <absolute-game-directory>`. Native halt может ждать зависший callback и не является гарантией завершения. Принудительное завершение допустимо только после отдельного разрешения владельца конкретного одноразового fixture и никогда не считается успешным сохранением.

Сырые результаты, thread dumps и игровые логи остаются в `artifacts`; в публикационную документацию переносится только проверенное описание и границы.
