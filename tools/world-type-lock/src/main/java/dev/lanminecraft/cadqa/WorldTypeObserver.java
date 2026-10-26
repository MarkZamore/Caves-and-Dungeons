package dev.lanminecraft.cadqa;

import java.lang.instrument.Instrumentation;
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
import java.util.concurrent.Executor;
import java.util.concurrent.atomic.AtomicBoolean;

/** Optional QA observer: no transformer, world selection, or world creation. */
public final class WorldTypeObserver {
    private static final AtomicBoolean STARTED = new AtomicBoolean();
    private static final AtomicBoolean QUEUED = new AtomicBoolean();
    private static volatile String previous;
    private static volatile Path output;
    private static volatile Path stop;

    private WorldTypeObserver() { }

    public static void premain(String arguments, Instrumentation instrumentation) throws Exception {
        start(arguments, instrumentation);
    }

    public static void agentmain(String arguments, Instrumentation instrumentation) throws Exception {
        start(arguments, instrumentation);
    }

    static Path artifactPath(String value) {
        Path path = Path.of(value).normalize();
        boolean artifacts = false;
        for (Path part : path) artifacts |= part.toString().equalsIgnoreCase("artifacts");
        if (!path.isAbsolute() || !artifacts || !path.getFileName().toString().endsWith(".jsonl"))
            throw new IllegalArgumentException("An absolute .jsonl output beneath artifacts is required");
        return path;
    }

    private static void start(String arguments, Instrumentation instrumentation) throws Exception {
        Path destination = artifactPath(arguments);
        if (!STARTED.compareAndSet(false, true))
            throw new IllegalStateException("World type observer is already running in this JVM");
        output = destination;
        stop = destination.resolveSibling(destination.getFileName() + ".stop");
        Files.createDirectories(destination.getParent());
        emit(Map.of("status", "observer-started", "mode", "read-only", "minecraft", "1.20.1"));
        Thread worker = new Thread(() -> watch(instrumentation), "cad-world-type-observer");
        worker.setDaemon(true);
        worker.start();
    }

    private static void watch(Instrumentation instrumentation) {
        while (!Files.exists(stop)) {
            try {
                Class<?> clientClass = Arrays.stream(instrumentation.getAllLoadedClasses())
                        .filter(type -> type.getName().equals("net.minecraft.client.Minecraft"))
                        .findFirst().orElse(null);
                if (clientClass != null) {
                    Object client = method(clientClass, "m_91087_", "getInstance").invoke(null);
                    if (client instanceof Executor executor && QUEUED.compareAndSet(false, true)) {
                        executor.execute(() -> {
                            try { snapshot(client); }
                            catch (Throwable failure) { emitFailure(failure); }
                            finally { QUEUED.set(false); }
                        });
                    }
                }
                Thread.sleep(500);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return;
            } catch (Throwable failure) {
                emitFailure(failure);
                try { Thread.sleep(1000); }
                catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); return; }
            }
        }
        emit(Map.of("status", "observer-stopped"));
    }

    private static void snapshot(Object client) throws Exception {
        Object screen = field(client.getClass(), "f_91080_", "screen").get(client);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("screen", screen == null ? null : screen.getClass().getName());
        if (screen != null && screen.getClass().getName().equals(
                "net.minecraft.client.gui.screens.worldselection.CreateWorldScreen")) {
            Object state = call(screen, "m_267748_", "getUiState");
            Object settings = call(state, "m_267573_", "getSettings");
            Object registries = call(settings, "m_246480_", "worldgenLoadContext");
            ClassLoader loader = state.getClass().getClassLoader();
            Class<?> registryKeys = Class.forName("net.minecraft.core.registries.Registries", false, loader);
            Object presetKey = field(registryKeys, "f_256729_", "WORLD_PRESET").get(null);
            Method registryMethod = Arrays.stream(registries.getClass().getMethods())
                    .filter(value -> List.of("m_175515_", "registryOrThrow").contains(value.getName()))
                    .filter(value -> value.getParameterCount() == 1)
                    .findFirst().orElseThrow(() -> new NoSuchMethodException("registryOrThrow"));
            registryMethod.trySetAccessible();
            Object registry = registryMethod.invoke(registries, presetKey);
            Object keys = call(registry, "m_6566_", "keySet");
            result.put("registryIds", ((java.util.Set<?>) keys).stream()
                    .map(String::valueOf).sorted().toList());
            result.put("selected", entry(call(state, "m_267828_", "getWorldType")));
            result.put("normal", entries(call(state, "m_267815_", "getNormalPresetList")));
            result.put("alternative", entries(call(state, "m_267674_", "getAltPresetList")));
            result.put("seed", call(state, "m_267707_", "getSeed"));
            result.put("observationOnly", true);
        }
        emit(result);
    }

    private static List<Object> entries(Object source) throws Exception {
        List<Object> values = new ArrayList<>();
        for (Object value : (List<?>) source) values.add(entry(value));
        return values;
    }

    private static Map<String, Object> entry(Object entry) throws Exception {
        Map<String, Object> result = new LinkedHashMap<>();
        Object holder = call(entry, "f_267398_", "preset");
        String id = null;
        if (holder != null) {
            Optional<?> key = (Optional<?>) call(holder, "m_203543_", "unwrapKey");
            if (key.isPresent()) id = String.valueOf(call(key.get(), "m_135782_", "location"));
        }
        result.put("id", id);
        Object component = call(entry, "m_267572_", "describePreset");
        result.put("displayName", call(component, "getString"));
        return result;
    }

    private static Object call(Object receiver, String... names) throws Exception {
        return method(receiver.getClass(), names).invoke(receiver);
    }

    private static Method method(Class<?> type, String... names) throws NoSuchMethodException {
        for (String name : names) {
            try {
                Method method = type.getMethod(name);
                method.trySetAccessible();
                return method;
            } catch (NoSuchMethodException ignored) { }
        }
        throw new NoSuchMethodException(type.getName() + " " + Arrays.toString(names));
    }

    private static Field field(Class<?> type, String... names) throws NoSuchFieldException {
        for (String name : names) {
            try {
                Field field = type.getField(name);
                field.trySetAccessible();
                return field;
            } catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(type.getName() + " " + Arrays.toString(names));
    }

    private static void emitFailure(Throwable failure) {
        Throwable cause = failure;
        while (cause.getCause() != null) cause = cause.getCause();
        emit(Map.of("status", "observer-error", "error", cause.getClass().getName(),
                "message", String.valueOf(cause.getMessage())));
    }

    private static synchronized void emit(Map<String, Object> value) {
        String state = json(value);
        if (state.equals(previous)) return;
        previous = state;
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("timeUtc", Instant.now().toString());
        record.putAll(value);
        try {
            Files.writeString(output, json(record) + "\n", StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            System.out.println("[CadWorldTypeObserver] " + state);
        } catch (Exception failure) {
            System.err.println("[CadWorldTypeObserver] Unable to write QA observation: "
                    + failure.getClass().getSimpleName());
        }
    }

    private static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof Boolean || value instanceof Number) return value.toString();
        if (value instanceof Map<?, ?> map) {
            return "{" + map.entrySet().stream().sorted(Comparator.comparing(e -> String.valueOf(e.getKey())))
                    .map(e -> json(String.valueOf(e.getKey())) + ":" + json(e.getValue()))
                    .reduce((left, right) -> left + "," + right).orElse("") + "}";
        }
        if (value instanceof Iterable<?> iterable) {
            List<String> items = new ArrayList<>();
            for (Object item : iterable) items.add(json(item));
            return "[" + String.join(",", items) + "]";
        }
        StringBuilder result = new StringBuilder("\"");
        for (char character : value.toString().toCharArray()) {
            switch (character) {
                case '"' -> result.append("\\\"");
                case '\\' -> result.append("\\\\");
                case '\n' -> result.append("\\n");
                case '\r' -> result.append("\\r");
                case '\t' -> result.append("\\t");
                default -> {
                    if (character < 32) result.append(String.format("\\u%04x", (int) character));
                    else result.append(character);
                }
            }
        }
        return result.append('"').toString();
    }
}
