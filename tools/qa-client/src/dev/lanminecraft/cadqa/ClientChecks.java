package dev.lanminecraft.cadqa;

import java.lang.instrument.Instrumentation;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Properties;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.Executor;
import java.util.concurrent.atomic.AtomicBoolean;

/** Explicit fixture-only native checks. No transformer, input injection, or test doubles. */
public final class ClientChecks {
    private static final AtomicBoolean STARTED = new AtomicBoolean();
    private static final AtomicBoolean QUEUED = new AtomicBoolean();
    private static volatile int phase;
    private static volatile long since;
    private static volatile boolean failed;
    private static volatile boolean serverObserved;
    private static Path root, output, saves, world;
    private static String mode, worldName, expected, seed, sourceWorld, expectedGenerator;
    private static Object creationScreen, client;
    private static Object previousSettings;
    private static boolean initialStructures = true, initialBonus;
    private static long begun;
    private static Properties configuration;
    private static List<?> contentAdvancements;
    private static boolean languagePrepared;
    private static boolean lanPublished;
    private static volatile java.util.concurrent.CompletableFuture<?> contentReload;
    private static volatile Throwable contentReloadFailure;
    private static boolean contentReloadRequested, contentReloadDone;

    public static void agentmain(String argument, Instrumentation instrumentation) throws Exception {
        if (!STARTED.compareAndSet(false, true)) throw new IllegalStateException("Checks already attached");
        Path spec = owned(Path.of(argument).toRealPath());
        Properties p = new Properties();
        try (var reader = Files.newBufferedReader(spec, StandardCharsets.UTF_8)) { p.load(reader); }
        configuration = p;
        root = owned(Path.of(required(p, "gameDirectory")).toRealPath());
        output = owned(Path.of(required(p, "output")).toAbsolutePath().normalize());
        if (Files.exists(output)) throw new IllegalArgumentException("Fresh output label required");
        if (!Files.isDirectory(output.getParent())) throw new IllegalArgumentException("Precreate evidence directory");
        worldName = required(p, "world");
        if (!worldName.matches("CAD-QA-[A-Za-z0-9-]{1,48}")) throw new IllegalArgumentException("Owned QA world name required");
        mode = required(p, "mode");
        if (!Set.of("create-normal", "create-locked", "load-existing", "recreate", "missing-required").contains(mode)) throw new IllegalArgumentException("Unknown QA mode");
        sourceWorld = p.getProperty("sourceWorld", "");
        if (mode.equals("recreate") && !sourceWorld.matches("CAD-QA-[A-Za-z0-9-]{1,48}")) throw new IllegalArgumentException("Owned recreation source required");
        seed = p.getProperty("seed", "3141592653589793238");
        expectedGenerator = p.getProperty("expectedGenerator", mode.equals("load-existing")
                ? "net.minecraft.world.level.levelgen.FlatLevelSource"
                : "net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator");
        if (!Set.of("net.minecraft.world.level.levelgen.FlatLevelSource", "net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator").contains(expectedGenerator))
            throw new IllegalArgumentException("Unreviewed expected generator");
        Long.parseLong(seed);
        expected = mode.equals("create-normal") ? "minecraft:normal" : "caves_and_dungeons:modded_mines";
        saves = root.resolve("saves"); world = saves.resolve(worldName);
        if (!mode.equals("load-existing") && Files.exists(world)) throw new IllegalArgumentException("Fresh QA world required");
        if (mode.equals("load-existing") && !Files.isRegularFile(world.resolve("level.dat"))) throw new IllegalArgumentException("Prepared independent level.dat required");
        Path snapshot = owned(Path.of(required(p, "inputSnapshot")).toRealPath());
        byte[] sha = java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(snapshot));
        emit(Map.of("event", "started", "mode", mode, "world", worldName,
                "inputSnapshotSha256", java.util.HexFormat.of().formatHex(sha), "physicalInput", false));
        begun = since = System.nanoTime();
        Thread worker = new Thread(() -> watch(instrumentation), "cad-native-client-checks");
        worker.setDaemon(true); worker.start();
    }

    private static String required(Properties p, String key) {
        String s = p.getProperty(key); if (s == null || s.isBlank()) throw new IllegalArgumentException("Missing " + key); return s;
    }
    private static Path owned(Path path) {
        Path n = path.toAbsolutePath().normalize();
        if (!path.isAbsolute() || n.toString().contains("..")) throw new IllegalArgumentException("Absolute owned path required");
        boolean artifacts = false; for (Path part : n) artifacts |= part.toString().equalsIgnoreCase("artifacts");
        if (!artifacts) throw new IllegalArgumentException("QA path must be inside artifacts");
        return n;
    }
    private static void watch(Instrumentation instrumentation) {
        while (!failed && phase < 8) {
            try {
                if (System.nanoTime() - begun > 900_000_000_000L) throw new IllegalStateException("Native QA exceeded 15 minutes");
                if (client == null) {
                    Class<?> c = Arrays.stream(instrumentation.getAllLoadedClasses()).filter(t -> t.getName().equals("net.minecraft.client.Minecraft")).findFirst().orElse(null);
                    if (c != null) client = method(c, "m_91087_").invoke(null);
                }
                if (client instanceof Executor executor && QUEUED.compareAndSet(false, true)) executor.execute(() -> {
                    try { tick(); } catch (Throwable failure) { fail(failure); } finally { QUEUED.set(false); }
                });
                Thread.sleep(500);
            } catch (Throwable failure) { fail(failure); }
        }
    }
    private static void tick() throws Exception {
        Path actual = ((java.io.File) field(client.getClass(), "f_91069_").get(client)).toPath().toRealPath();
        require(actual.equals(root), "client game directory matches designated fixture");
        Object screen = field(client.getClass(), "f_91080_").get(client);
        Object player = field(client.getClass(), "f_91074_").get(client);
        Object level = field(client.getClass(), "f_91073_").get(client);
        String screenName = screen == null ? "none" : screen.getClass().getName();
        if (phase == 0) {
            require(player == null && level == null && call(client, "m_91092_") == null, "start without a loaded world");
            if (screenName.equals("net.minecraft.client.gui.screens.AccessibilityOnboardingScreen")) {
                call(screen, "m_7379_");
                emit(Map.of("event", "native-onboarding-done"));
                return;
            }
            if (!languagePrepared && (screenName.equals("net.minecraft.client.gui.screens.TitleScreen") || screenName.equals("net.minecraft.client.gui.screens.worldselection.CreateWorldScreen"))) {
                String selectedLanguage = configuration.getProperty("language", "ru_ru");
                require(Set.of("ru_ru", "en_us").contains(selectedLanguage), "reviewed QA language");
                Object languages = call(client, "m_91102_");
                invoke(languages, "m_264110_", selectedLanguage);
                invoke(languages, "m_6213_", call(client, "m_91098_"));
                languagePrepared = true;
                emit(Map.of("event", "native-language-loaded", "language", call(languages, "m_264236_")));
            }
            if (screenName.equals("net.minecraft.client.gui.screens.worldselection.CreateWorldScreen") && !mode.equals("load-existing") && !mode.equals("recreate")) {
                emit(Map.of("event", "resume-owned-create-screen", "forge", "47.3.7"));
                phase = 1; return;
            }
            if (!screenName.equals("net.minecraft.client.gui.screens.TitleScreen")) return;
            String forge = String.valueOf(Class.forName("net.minecraftforge.versions.forge.ForgeVersion", false, client.getClass().getClassLoader()).getMethod("getVersion").invoke(null));
            require(forge.equals("47.3.7"), "exact Forge version 47.3.7");
            emit(Map.of("event", "title-ready", "forge", forge, "maxTextureSize", glLimit()));
            if (mode.equals("load-existing")) {
                Object flows = call(client, "m_231466_"); invoke(flows, "m_233133_", screen, worldName); phase = 3;
            } else if (mode.equals("recreate")) {
                Object access = invoke(call(client, "m_91392_"), "m_78260_", sourceWorld);
                try {
                    Object pair = invoke(call(client, "m_231466_"), "m_246225_", access);
                    Object settings = call(pair, "getFirst"), context = call(pair, "getSecond");
                    Object sourceOptions = call(context, "f_244272_");
                    seed = String.valueOf(call(sourceOptions, "m_245499_"));
                    initialStructures = (Boolean)call(sourceOptions, "m_247749_");
                    initialBonus = (Boolean)call(sourceOptions, "m_245100_");
                    Class<?> c = Class.forName("net.minecraft.client.gui.screens.worldselection.CreateWorldScreen", false, client.getClass().getClassLoader());
                    Object recreated = find(c, "m_275847_", 5).invoke(null, client, screen, settings, context, null);
                    invoke(client, "m_91152_", recreated);
                    emit(Map.of("event", "native-recreate-opened", "sourceWorld", sourceWorld, "sourceSeed", seed,
                            "sourceStructures", initialStructures, "sourceBonusChest", initialBonus));
                } finally { ((AutoCloseable)access).close(); }
                phase = 1;
            } else {
                Class<?> c = Class.forName("net.minecraft.client.gui.screens.worldselection.CreateWorldScreen", false, client.getClass().getClassLoader());
                find(c, "m_232896_", 2).invoke(null, client, screen); phase = 1;
            }
            since = System.nanoTime(); return;
        }
        if (phase == 1) {
            if (!screenName.equals("net.minecraft.client.gui.screens.worldselection.CreateWorldScreen")) return;
            creationScreen = screen;
            Object state = call(screen, "m_267748_");
            Map<String, Object> before = screenState(state);
            emit(Map.of("event", "initial-world-state", "state", before,
                    "structures", call(state, "m_267615_"), "bonusChest", call(state, "m_267593_")));
            require(expected.equals(entryId(call(state, "m_267828_"))), "expected initial preset");
            if (mode.equals("missing-required")) {
                singletonLists(state);
                invoke(state, "m_267649_", worldName);
                missingRequired(state, screen);
                return;
            }
            boolean locked = !mode.equals("create-normal");
            if (locked) {
                singletonLists(state);
                require(initialStructures == (Boolean)call(state, "m_267615_"), "structures retained after constructor");
                require(initialBonus == (Boolean)call(state, "m_267593_"), "bonus chest retained after constructor");
                if (mode.equals("recreate")) require(seed.equals(String.valueOf(call(state, "m_267707_"))), "recreation retains original seed");
                runtimeCodecEquivalence(state);
            }
            invoke(state, "m_267649_", worldName); invoke(state, "m_267759_", seed);
            String gameMode = String.valueOf(call(state, "m_267761_"));
            String difficulty = String.valueOf(call(state, "m_267816_"));
            if (locked) {
                Object flat = registryEntry(state, "minecraft:flat");
                invoke(state, "m_267770_", false); invoke(state, "m_267666_", true);
                invoke(state, "m_267576_", flat);
                require("minecraft:flat".equals(entryId(call(state, "m_267828_"))), "native flat selection test reached state");
                Object settings = call(state, "m_267573_"); invoke(state, "m_267692_", settings);
                singletonLists(state);
                require(expected.equals(entryId(call(state, "m_267828_"))), "native settings refresh restores required preset");
                require(seed.equals(String.valueOf(call(state, "m_267707_"))), "seed retained after settings refresh");
                require(gameMode.equals(String.valueOf(call(state, "m_267761_"))) && difficulty.equals(String.valueOf(call(state, "m_267816_"))), "independent gameplay settings retained");
                require(!(Boolean)call(state, "m_267615_") && (Boolean)call(state, "m_267593_"), "structure and bonus flags retained after refresh");
                invoke(state, "m_267770_", true); invoke(state, "m_267666_", false);
                Object nav = field(screen.getClass(), "f_267490_").get(screen);
                for (int tab : List.of(1,2,0)) { invoke(nav, "m_276089_", tab, false); singletonLists(state); }
                emit(Map.of("event", "native-tab-roundtrip-retained", "tabs", List.of(1,2,0)));
                previousSettings = call(state, "m_267573_");
                Object config = call(previousSettings, "f_243842_");
                Object pair = invoke(screen, "m_267637_", config);
                require(pair != null, "native datapack repository prepared");
                Object repository = call(pair, "getSecond");
                invoke(screen, "m_269431_", repository, config, (java.util.function.Consumer<Object>)unused -> { });
                emit(Map.of("event", "native-datapack-reload-started", "before", before, "seed", seed, "gameMode", gameMode, "difficulty", difficulty));
                phase = 2; return;
            }
            emit(Map.of("event", "creation-state", "before", before, "seed", seed, "gameMode", gameMode, "difficulty", difficulty));
            method(screen.getClass(), "m_100972_").invoke(screen);
            require(expected.equals(entryId(call(state, "m_267828_"))), "onCreate selected required preset before dimensions baked");
            emit(Map.of("event", "native-onCreate-returned", "selected", entryId(call(state, "m_267828_"))));
            phase = 3; since = System.nanoTime(); return;
        }
        if (phase == 2) {
            if (screenName.equals("net.minecraft.client.gui.screens.ConfirmScreen")) throw new IllegalStateException("Native datapack validation failed");
            if (screen != creationScreen) return;
            Object state = call(screen, "m_267748_");
            if (call(state, "m_267573_") == previousSettings) return;
            singletonLists(state);
            require(expected.equals(entryId(call(state, "m_267828_"))), "required selected preset retained after real datapack reload");
            require(seed.equals(String.valueOf(call(state, "m_267707_"))), "seed retained after real datapack reload");
            require((Boolean)call(state, "m_267615_") && !(Boolean)call(state, "m_267593_"), "structure and bonus flags retained after real datapack reload");
            emit(Map.of("event", "native-datapack-reload-completed", "state", screenState(state), "seed", seed));
            invoke(state, "m_267576_", registryEntry(state, "minecraft:flat"));
            require("minecraft:flat".equals(entryId(call(state, "m_267828_"))), "native alternate selected immediately before create");
            method(screen.getClass(), "m_100972_").invoke(screen);
            require(expected.equals(entryId(call(state, "m_267828_"))), "onCreate re-applies required preset before bake");
            emit(Map.of("event", "native-onCreate-returned", "selected", entryId(call(state, "m_267828_"))));
            phase = 3; since = System.nanoTime(); return;
        }
        if (phase == 3) {
            if (screenName.equals("net.minecraft.client.gui.screens.ConfirmScreen")) {
                // Accept only the fixture's ordinary experimental world warning callback.
                Object callback = field(screen.getClass(), "f_95649_").get(screen);
                find(callback.getClass(), "accept", 1).invoke(callback, true);
                emit(Map.of("event", "native-experimental-confirmation-accepted")); return;
            }
            if (screenName.equals("net.minecraft.client.gui.screens.worldselection.ConfirmExperimentalFeaturesScreen")) {
                Object callback = field(screen.getClass(), "f_244340_").get(screen);
                find(callback.getClass(), "accept", 1).invoke(callback, true);
                emit(Map.of("event", "native-experimental-features-confirmation-accepted")); return;
            }
            if (screenName.equals("net.minecraft.client.gui.screens.AlertScreen") || screenName.contains("ErrorScreen"))
                throw new IllegalStateException("Native creation/load showed " + screenName);
            Object server = call(client, "m_91092_");
            if (player == null || level == null || server == null || screenName.equals("net.minecraft.client.gui.screens.ReceivingLevelScreen")) return;
            emit(Map.of("event", "client-world-entered", "clientLevelClass", level.getClass().getName(),
                    "playerClass", player.getClass().getName(), "position", position(player), "screen", screenName));
            phase = 4; since = System.nanoTime(); return;
        }
        if (phase == 4 && System.nanoTime() - since > 12_000_000_000L) {
            Object server = call(client, "m_91092_");
            if (Boolean.parseBoolean(configuration.getProperty("reloadBeforeContent", "false")) && !contentReloadDone) {
                if (!contentReloadRequested) {
                    contentReloadRequested = true;
                    ((Executor)server).execute(() -> {
                        try {
                            Object packs = call(server, "m_129891_");
                            Object selected = call(packs, "m_10523_");
                            emit(Map.of("event", "native-content-reload-started", "selectedPacks", selected));
                            contentReload = (java.util.concurrent.CompletableFuture<?>)invoke(server, "m_129861_", selected);
                        } catch (Throwable t) { contentReloadFailure = t; }
                    });
                }
                if (contentReloadFailure != null) throw new IllegalStateException("Native server content reload failed", contentReloadFailure);
                if (contentReload == null || !contentReload.isDone()) return;
                contentReload.join(); contentReloadDone = true;
                emit(Map.of("event", "native-content-reload-completed"));
            }
            if (!serverObserved) {
                ((Executor) server).execute(() -> {
                    try { observeServer(server); serverObserved = true; } catch (Throwable failure) { fail(failure); }
                });
                phase = 5;
            }
            return;
        }
        if (phase == 5 && serverObserved) {
            Object server = call(client, "m_91092_");
            if (!lanPublished) {
                Object gameType = Class.forName("net.minecraft.world.level.GameType", false, client.getClass().getClassLoader()).getEnumConstants()[0];
                boolean published = (Boolean) invoke(server, "m_7386_", gameType, false, 25587);
                require(published && (Boolean) call(server, "m_6992_"), "native integrated LAN published");
                emit(Map.of("event", "integrated-lan-published", "port", call(server, "m_7010_"), "guestJoinTested", false));
                lanPublished = true;
            }
            if (configuration.containsKey("contentOutput")) {
                if (!ContentChecks.ready()) return;
                ContentChecks.inspectClient(client, contentAdvancements, configuration);
            }
            phase = 6; since = System.nanoTime(); return;
        }
        if (phase == 6 && System.nanoTime() - since > 8_000_000_000L) {
            call(level, "m_7462_"); // same disconnect-before-clear ordering as native pause-menu Save and Quit
            call(client, "m_91399_"); phase = 7; since = System.nanoTime(); return;
        }
        if (phase == 7 && level == null && call(client, "m_91092_") == null) {
            require(Files.isRegularFile(world.resolve("level.dat")), "world saved to designated QA path");
            emit(Map.of("event", "completed", "mode", mode, "savedWorld", worldName,
                    "levelDatBytes", Files.size(world.resolve("level.dat")), "worldEntered", true,
                    "integratedLanPublished", true, "guestJoinTested", false, "physicalInput", false));
            phase = 8; call(client, "m_91395_");
        }
    }

    private static void observeServer(Object server) throws Exception {
        Object level = call(server, "m_129783_"); Object data = call(server, "m_129910_");
        Object options = call(data, "m_246337_"); long actualSeed = ((Number) call(options, "m_245499_")).longValue();
        if (!mode.equals("load-existing")) require(actualSeed == Long.parseLong(seed), "actual persisted seed matches UI seed");
        Object chunkCache = call(level, "m_7726_"); Object generator = call(chunkCache, "m_8481_");
        require(generator.getClass().getName().equals(expectedGenerator), "actual Overworld generator matches scenario " + expectedGenerator);
        Object spawn = call(level, "m_220360_");
        Object players = call(server, "m_6846_"); List<?> list = (List<?>) call(players, "m_11314_");
        require(list.size() == 1, "one actual integrated server player");
        Object player = list.get(0); Object pos = call(player, "m_20183_");
        int x = ((Number) call(pos, "m_123341_")).intValue(), y = ((Number) call(pos, "m_123342_")).intValue(), z = ((Number) call(pos, "m_123343_")).intValue();
        Class<?> blockPos = Class.forName("net.minecraft.core.BlockPos", false, level.getClass().getClassLoader());
        Constructor<?> c = blockPos.getConstructor(int.class, int.class, int.class);
        Map<String, Integer> blocks = new TreeMap<>();
        for (int dx = -5; dx <= 5; dx++) for (int dy = -3; dy <= 3; dy++) for (int dz = -5; dz <= 5; dz++) {
            Object state = invoke(level, "m_8055_", c.newInstance(x + dx, y + dy, z + dz));
            String b = String.valueOf(call(state, "m_60734_")); blocks.merge(b, 1, Integer::sum);
        }
        emit(Map.of("event", "actual-server-world", "seed", actualSeed, "tickCount", call(server, "m_129921_"),
                "generator", generator.getClass().getName(), "spawn", String.valueOf(spawn), "playerPosition", position(player),
                "nearbyBlocks", blocks, "scanRadius", List.of(5, 3, 5), "dimension", String.valueOf(call(level, "m_46472_"))));
        if (configuration.containsKey("contentOutput")) {
            contentAdvancements = new ArrayList<>((java.util.Collection<?>) call(call(server, "m_129889_"), "m_136028_"));
            ContentChecks.inspectServer(server, player, configuration);
        }
    }

    private static Map<String, Object> screenState(Object state) throws Exception {
        return Map.of("selected", entry(call(state, "m_267828_")), "normal", entries(call(state, "m_267815_")), "alternative", entries(call(state, "m_267674_")));
    }
    @SuppressWarnings("unchecked")
    private static void missingRequired(Object state, Object screen) throws Exception {
        require(field(client.getClass(), "f_91073_").get(client) == null && call(client, "m_91092_") == null,
                "negative test has no loaded world");
        Path helperJar = root.resolve("mods/cad-world-type-lock-1.0.0.jar");
        String helperHash = java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(helperJar)));
        Object registry = presetRegistry(state);
        require(registry.getClass().getName().equals("net.minecraft.core.MappedRegistry"), "actual native MappedRegistry required");
        Map<Object, Object> byKey = (Map<Object, Object>)field(registry.getClass(), "f_205842_").get(registry);
        Object key = null;
        for (Object k : byKey.keySet()) if (expected.equals(String.valueOf(call(k, "m_135782_")))) key = k;
        require(key != null, "native required entry initially present");
        int count = byKey.size();
        require(byKey.remove(key) != null && byKey.size() == count - 1, "removed only required backing entry in unused QA context");
        for (Object row : (Set<?>)call(registry, "m_6579_"))
            require(!expected.equals(String.valueOf(call(((Map.Entry<?, ?>)row).getKey(), "m_135782_"))), "native entrySet confirms missing required key");
        method(state.getClass(), "m_267608_").invoke(state);
        for (String getter : List.of("m_267815_", "m_267674_")) {
            List<?> entries = (List<?>)call(state, getter);
            require(entries.size() == 1 && entryId(entries.get(0)).equals("<unbound>"), "missing required preset cannot expose fallback type");
        }
        emit(Map.of("event", "missing-required-native-context", "faultInjection", "one actual MappedRegistry.byKey entry removed; production JAR unchanged", "state", screenState(state)));
        method(screen.getClass(), "m_100972_").invoke(screen);
        Object alert = field(client.getClass(), "f_91080_").get(client);
        require(alert != null && alert.getClass().getName().equals("net.minecraft.client.gui.screens.AlertScreen"), "native AlertScreen shown on refused create");
        String title = String.valueOf(call(call(alert, "m_96636_"), "getString"));
        String body = String.valueOf(call(field(alert.getClass(), "f_238618_").get(alert), "getString"));
        require(title.equals("\u041d\u0435\u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u043c\u0438\u0440"), "localized refusal title");
        require(body.contains("\u0428\u0430\u0445\u0442\u044b \u0441 \u041c\u043e\u0434\u0430\u043c\u0438"), "localized refusal identifies required world type");
        require(!Files.exists(world), "refused create wrote no world folder");
        require(field(client.getClass(), "f_91073_").get(client) == null && call(client, "m_91092_") == null,
                "refused create started no client level or integrated server");
        require(helperHash.equals(java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(helperJar)))), "production helper JAR unchanged by negative test");
        emit(Map.of("event", "completed", "mode", mode, "creationRefused", true, "noSaveFolder", true, "title", title, "body", body,
                "productionJarChanged", false, "helperSha256", helperHash, "physicalInput", false));
        phase = 8; call(client, "m_91395_");
    }
    private static void runtimeCodecEquivalence(Object state) throws Exception {
        ClassLoader loader = state.getClass().getClassLoader();
        Object normalHolder = call(registryEntry(state, "minecraft:normal"), "f_267398_");
        Object customHolder = call(registryEntry(state, expected), "f_267398_");
        Object normal = call(normalHolder, "m_203334_");
        Object custom = call(customHolder, "m_203334_");
        Object access = call(call(state, "m_267573_"), "m_246480_");
        Class<?> jsonOps = Class.forName("com.mojang.serialization.JsonOps", false, loader);
        Object json = jsonOps.getField("INSTANCE").get(null);
        Class<?> registryOps = Class.forName("net.minecraft.resources.RegistryOps", false, loader);
        Object ops = find(registryOps, "m_255058_", 2).invoke(null, json, access);
        Object codec = field(Class.forName("net.minecraft.world.level.levelgen.presets.WorldPreset", false, loader), "f_226414_").get(null);
        java.util.function.Consumer<String> onError = message -> { throw new IllegalStateException("Native preset codec: " + message); };
        Object encodedNormal = invoke(invoke(codec, "encodeStart", ops, normal), "getOrThrow", false, onError);
        Object encodedCustom = invoke(invoke(codec, "encodeStart", ops, custom), "getOrThrow", false, onError);
        require(encodedNormal.equals(encodedCustom), "actual loaded normal/custom preset codec dimensions equivalent");
        emit(Map.of("event", "runtime-preset-codec-equivalence", "equal", true, "normalId", "minecraft:normal", "customId", expected));
    }
    private static List<Object> entries(Object list) throws Exception { List<Object> out = new ArrayList<>(); for (Object e : (List<?>) list) out.add(entry(e)); return out; }
    private static Map<String, Object> entry(Object entry) throws Exception { return Map.of("id", entryId(entry), "displayName", call(call(entry, "m_267572_"), "getString")); }
    private static String entryId(Object entry) throws Exception {
        Object holder = call(entry, "f_267398_"); if (holder == null) return "<unbound>";
        Optional<?> key = (Optional<?>) call(holder, "m_203543_");
        return key.isPresent() ? String.valueOf(call(key.get(), "m_135782_")) : "<unbound>";
    }
    private static Object registryEntry(Object state, String id) throws Exception {
        ClassLoader l = state.getClass().getClassLoader(); Object registry = presetRegistry(state);
        for (Object row : (Set<?>) call(registry, "m_6579_")) {
            Map.Entry<?, ?> e = (Map.Entry<?, ?>) row;
            if (id.equals(String.valueOf(call(e.getKey(), "m_135782_")))) {
                Optional<?> holder = (Optional<?>) invoke(registry, "m_203636_", e.getKey());
                return Class.forName("net.minecraft.client.gui.screens.worldselection.WorldCreationUiState$WorldTypeEntry", false, l)
                        .getConstructor(Class.forName("net.minecraft.core.Holder", false, l)).newInstance(holder.orElseThrow());
            }
        }
        throw new IllegalStateException("Native preset absent " + id);
    }
    private static Object presetRegistry(Object state) throws Exception {
        Object settings = call(state, "m_267573_"); Object access = call(settings, "m_246480_");
        ClassLoader l = state.getClass().getClassLoader(); Object key = field(Class.forName("net.minecraft.core.registries.Registries", false, l), "f_256729_").get(null);
        return invoke(access, "m_175515_", key);
    }
    private static void singletonLists(Object state) throws Exception {
        for (String getter : List.of("m_267815_", "m_267674_")) {
            List<?> list = (List<?>) call(state, getter);
            require(list.size() == 1 && expected.equals(entryId(list.get(0))), "only required preset in " + getter);
            require("\u0428\u0430\u0445\u0442\u044b \u0441 \u041c\u043e\u0434\u0430\u043c\u0438".equals(String.valueOf(call(call(list.get(0), "m_267572_"), "getString"))), "exact Russian preset name");
        }
    }
    private static List<Object> position(Object player) throws Exception { return List.of(call(player, "m_20185_"), call(player, "m_20186_"), call(player, "m_20189_")); }
    private static Object glLimit() {
        try { return Class.forName("org.lwjgl.opengl.GL11", false, client.getClass().getClassLoader()).getMethod("glGetInteger", int.class).invoke(null, 3379); }
        catch (Throwable t) { return "unavailable:" + t.getClass().getSimpleName(); }
    }
    private static void require(boolean value, String label) { if (!value) throw new IllegalStateException(label); }
    private static Object call(Object receiver, String name) throws Exception { return method(receiver.getClass(), name).invoke(receiver); }
    private static Object invoke(Object receiver, String name, Object... args) throws Exception { return find(receiver.getClass(), name, args.length).invoke(receiver, args); }
    private static Method method(Class<?> c, String name) throws Exception { return find(c, name, 0); }
    private static Method find(Class<?> c, String name, int n) throws Exception {
        for (Class<?> t = c; t != null; t = t.getSuperclass()) for (Method m : t.getDeclaredMethods()) if (m.getName().equals(name) && m.getParameterCount() == n) { m.setAccessible(true); return m; }
        for (Method m : c.getMethods()) if (m.getName().equals(name) && m.getParameterCount() == n) { m.trySetAccessible(); return m; }
        throw new NoSuchMethodException(c.getName() + "." + name);
    }
    private static Field field(Class<?> c, String name) throws Exception {
        for (Class<?> t = c; t != null; t = t.getSuperclass()) try { Field f = t.getDeclaredField(name); f.setAccessible(true); return f; } catch (NoSuchFieldException ignored) { }
        throw new NoSuchFieldException(c.getName() + "." + name);
    }
    private static void fail(Throwable failure) {
        failed = true; while (failure.getCause() != null) failure = failure.getCause();
        emit(Map.of("event", "failed", "phase", phase, "error", failure.getClass().getName(), "message", String.valueOf(failure.getMessage())));
        failure.printStackTrace();
    }
    private static synchronized void emit(Map<String, ?> map) {
        Map<String, Object> r = new LinkedHashMap<>(); r.put("timeUtc", Instant.now().toString()); r.putAll(map);
        String line = json(r);
        try { Files.writeString(output, line + "\n", StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND); }
        catch (Exception e) { throw new IllegalStateException("Cannot write QA evidence", e); }
        System.out.println("[CadNativeClientChecks] " + line);
    }
    private static String json(Object v) {
        if (v == null) return "null"; if (v instanceof Boolean || v instanceof Number) return v.toString();
        if (v instanceof Map<?, ?> m) return "{" + m.entrySet().stream().sorted(Comparator.comparing(e -> String.valueOf(e.getKey()))).map(e -> json(String.valueOf(e.getKey())) + ":" + json(e.getValue())).reduce((a,b) -> a + "," + b).orElse("") + "}";
        if (v instanceof Iterable<?> it) { List<String> s = new ArrayList<>(); for (Object e : it) s.add(json(e)); return "[" + String.join(",", s) + "]"; }
        StringBuilder s = new StringBuilder("\""); for (char c : v.toString().toCharArray()) switch (c) { case '"' -> s.append("\\\""); case '\\' -> s.append("\\\\"); case '\n' -> s.append("\\n"); case '\r' -> s.append("\\r"); case '\t' -> s.append("\\t"); default -> { if (c < 32) s.append(String.format("\\u%04x", (int)c)); else s.append(c); } } return s.append('"').toString();
    }
}
