package dev.lanminecraft.cadqa;

import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.Executor;

/** Native read/fixture-only checks for language overlays and the shipped FTB book. */
public final class ContentChecks {
    private static Map<String, Object> serverResult = new TreeMap<>();
    private static volatile boolean ready;
    private static volatile Throwable failure;

    public static boolean ready() throws Exception {
        if (failure != null) throw new IllegalStateException("Native FTB check failed", failure);
        return ready;
    }

    public static void inspectServer(Object server, Object player, Properties p) throws Exception {
        serverResult = new TreeMap<>();
        if (!Boolean.parseBoolean(p.getProperty("requireFtb", "false"))) { ready = true; return; }
        ClassLoader l = server.getClass().getClassLoader();
        Object file = Class.forName("dev.ftb.mods.ftbquests.quest.ServerQuestFile", false, l).getField("INSTANCE").get(null);
        require(file != null && !((Boolean)call(file, "isLoading")), "real server quest file loaded");
        List<?> chapters = (List<?>)call(file, "getAllChapters");
        List<?> tasks = (List<?>)call(file, "getAllTasks");
        require(!chapters.isEmpty() && !tasks.isEmpty(), "nonempty native FTB book");
        Object advancements = call(server, "m_129889_");
        serverResult.put("selectedDataPacks", call(call(server, "m_129891_"), "m_10523_"));
        require(((Collection<?>)serverResult.get("selectedDataPacks")).contains("cad-russian-display"), "required Russian display data pack active");
        Object team = invokeCompatible(file, "getOrCreateTeamData", player);
        Object candidate = null;
        int quests = 0, advancementTasks = 0;
        List<Map<String, Object>> taskRecords = new ArrayList<>();
        for (Object chapter : chapters) for (Object quest : (List<?>)call(chapter, "getQuests")) {
            quests++;
            require(((Collection<?>)call(quest, "getRewards")).isEmpty(), "quest has no rewards");
        }
        require(((List<?>)call(file, "getRewardTables")).isEmpty(), "no reward tables");
        require(!((Boolean)call(file, "isDropLootCrates")), "no loot crate drops");
        require(((List<?>)call(file, "getEmergencyItems")).isEmpty(), "no emergency rewards");
        for (Object task : tasks) {
            Map<String, Object> record = new TreeMap<>();
            record.put("id", call(task, "getCodeString")); record.put("class", task.getClass().getSimpleName());
            if (task.getClass().getName().equals("dev.ftb.mods.ftbquests.quest.task.AdvancementTask")) {
                advancementTasks++;
                Object id = field(task.getClass(), "advancement").get(task);
                Object advancement = invokeCompatible(advancements, "m_136041_", id);
                require(advancement != null, "loaded advancement target " + id);
                require(String.valueOf(field(task.getClass(), "criterion").get(task)).isEmpty(), "whole advancement task");
                record.put("advancement", String.valueOf(id));
                if (candidate == null && (Boolean)invokeCompatible(team, "canStartTasks", call(task, "getQuest"))
                        && (Boolean)invokeCompatible(team, "areDependenciesComplete", call(task, "getQuest"))
                        && !((Boolean)invokeCompatible(team, "isCompleted", task))
                        && !((Boolean)invokeCompatible(task, "canSubmit", team, player))
                        && !((Boolean)call(invokeCompatible(call(player, "m_8960_"), "m_135996_", advancement), "m_8193_"))) candidate = task;
            }
            taskRecords.add(record);
        }
        serverResult.putAll(Map.of("chapters", chapters.size(), "quests", quests, "tasks", tasks.size(),
                "advancementTasks", advancementTasks, "rewards", 0, "taskTargets", taskRecords));
        require(candidate != null, "startable advancement task for retroactive test");
        Object task = candidate;
        Object id = field(task.getClass(), "advancement").get(task);
        Object advancement = invokeCompatible(advancements, "m_136041_", id);
        Object progress = call(player, "m_8960_");
        require(!((Boolean)invokeCompatible(task, "canSubmit", team, player)), "incomplete advancement is not accepted");
        serverResult.put("negativeIncompleteAccepted", false);
        for (Object criterion : ((Map<?, ?>)call(advancement, "m_138325_")).keySet())
            invokeCompatible(progress, "m_135988_", advancement, criterion);
        require((Boolean)call(invokeCompatible(progress, "m_135996_", advancement), "m_8193_"), "native player advancement complete");
        invokeCompatible(team, "setProgress", task, 0L);
        require(((Number)invokeCompatible(team, "getProgress", task)).longValue() == 0, "reset only FTB fixture progress");
        require((Boolean)invokeCompatible(task, "canSubmit", team, player), "native advancement task detects preexisting advancement");
        serverResult.put("positiveCompletedAccepted", true);
        serverResult.put("retroactiveAdvancement", String.valueOf(id));
        serverResult.put("retroactiveTask", call(task, "getCodeString"));
        serverResult.put("retroactiveDependenciesComplete", invokeCompatible(team, "areDependenciesComplete", call(task, "getQuest")));
        Thread wait = new Thread(() -> {
            try {
                Thread.sleep(8000);
                ((Executor)server).execute(() -> {
                    try {
                        long actual = ((Number)invokeCompatible(team, "getProgress", task)).longValue();
                        require(actual > 0 && (Boolean)invokeCompatible(team, "isCompleted", task), "normal player tick restored advancement progress without a new grant");
                        serverResult.put("retroactiveNormalTickCompleted", true);
                        ready = true;
                    } catch (Throwable t) { failure = t; }
                });
            } catch (Throwable t) { failure = t; }
        }, "cad-native-retroactive-check");
        wait.setDaemon(true); wait.start();
    }

    @SuppressWarnings("unchecked")
    public static void inspectClient(Object client, List<?> advancements, Properties p) throws Exception {
        ClassLoader l = client.getClass().getClassLoader();
        Object gson = Class.forName("com.google.gson.Gson", false, l).getConstructor().newInstance();
        Method parse = gson.getClass().getMethod("fromJson", String.class, Class.class);
        Map<String, Map<String, Object>> expected = new TreeMap<>();
        if (p.containsKey("contentExpectations")) {
            Map<String, Object> doc = (Map<String, Object>)parse.invoke(gson, Files.readString(owned(p.getProperty("contentExpectations"))), Map.class);
            for (Object row : (List<?>)doc.get("advancements")) {
                Map<String, Object> r = (Map<String, Object>)row; expected.put(String.valueOf(r.get("id")), r);
            }
        }
        Map<String, Map<String, Object>> records = new TreeMap<>();
        Object languages = call(client, "m_91102_");
        String original = String.valueOf(call(languages, "m_264236_"));
        try {
            for (String language : List.of("en_us", "ru_ru", "en_us")) {
                invokeCompatible(languages, "m_264110_", language);
                invokeCompatible(languages, "m_6213_", call(client, "m_91098_"));
                for (Object advancement : advancements) {
                    Object display = call(advancement, "m_138320_"); if (display == null) continue;
                    String id = String.valueOf(call(advancement, "m_138327_"));
                    Map<String, Object> record = records.computeIfAbsent(id, k -> new TreeMap<>());
                    Map<String, Object> text = Map.of("title", call(call(display, "m_14977_"), "getString"),
                            "description", call(call(display, "m_14985_"), "getString"));
                    if (record.containsKey(language)) require(record.get(language).equals(text), "English language roundtrip " + id);
                    record.put(language, text);
                    if (language.equals("ru_ru") && !expected.isEmpty()) {
                        Map<String, Object> match = expected.get(id);
                        require(match != null && Boolean.TRUE.equals(match.get("checked")), "audited native advancement " + id);
                        Map<String, Object> fields = (Map<String, Object>)match.get("fields");
                        for (String key : List.of("title", "description")) {
                            StringBuilder wanted = new StringBuilder();
                            for (Object part : (List<?>)fields.get(key)) wanted.append(((Map<?, ?>)part).get("ru"));
                            require(wanted.toString().equals(text.get(key)), "Russian native text " + id + "/" + key + ": " + text.get(key) + " != " + wanted);
                        }
                    }
                    if (!record.containsKey("definition")) {
                        Object json = call(call(advancement, "m_138313_"), "m_138400_");
                        record.put("definition", parse.invoke(gson, json.toString(), Map.class));
                        record.put("nativeDisplay", parse.invoke(gson, call(display, "m_14998_").toString(), Map.class));
                    }
                }
                if (language.equals("ru_ru") && p.containsKey("contentTranslations")) {
                    Map<String, Object> translations = (Map<String, Object>)parse.invoke(gson, Files.readString(owned(p.getProperty("contentTranslations"))), Map.class);
                    Class<?> component = Class.forName("net.minecraft.network.chat.Component", false, l);
                    for (Map.Entry<String, Object> entry : translations.entrySet()) {
                        Object text = component.getMethod("m_237115_", String.class).invoke(null, entry.getKey());
                        require(entry.getValue().equals(call(text, "getString")), "native overlay key " + entry.getKey());
                    }
                    serverResult.put("overlayKeysMatched", translations.size());
                }
            }
            if (p.containsKey("contentBaseline")) {
                Map<String, Object> base = (Map<String, Object>)parse.invoke(gson, Files.readString(owned(p.getProperty("contentBaseline"))), Map.class);
                Map<String, Object> old = (Map<String, Object>)base.get("advancements");
                require(old.keySet().equals(records.keySet()), "display advancement IDs retained");
                for (String id : records.keySet()) {
                    Map<String, Object> before = (Map<String, Object>)old.get(id);
                    Map<String, Object> after = records.get(id);
                    require(before.get("en_us").equals(after.get("en_us")), "English text retained " + id);
                    Map<String, Object> a = (Map<String, Object>)before.get("definition"), b = (Map<String, Object>)after.get("definition");
                    for (Map<String, Object> definition : List.of(a, b)) {
                        Map<String, Object> display = (Map<String, Object>)definition.get("display"); display.remove("title"); display.remove("description");
                        // Advancement requirements are AND rows of OR criteria; both orders are immaterial.
                        if (definition.get("requirements") instanceof List<?> requirements) {
                            List<List<String>> normalized = new ArrayList<>();
                            for (Object group : requirements) {
                                List<String> criteria = new ArrayList<>();
                                for (Object criterion : (List<?>)group) criteria.add(String.valueOf(criterion));
                                Collections.sort(criteria); normalized.add(criteria);
                            }
                            normalized.sort(Comparator.comparing(Object::toString));
                            definition.put("requirements", normalized);
                        }
                    }
                    Method toJson = gson.getClass().getMethod("toJson", Object.class);
                    Method jsonParser = Class.forName("com.google.gson.JsonParser", false, l).getMethod("parseString", String.class);
                    Object jsonBefore = jsonParser.invoke(null, toJson.invoke(gson, a));
                    Object jsonAfter = jsonParser.invoke(null, toJson.invoke(gson, b));
                    if (!jsonBefore.equals(jsonAfter)) {
                        Map<String, Object> mismatch = Map.of("id", id, "before", a, "after", b,
                                "beforeClass", a.getClass().getName(), "afterClass", b.getClass().getName());
                        Files.writeString(owned(p.getProperty("contentOutput") + ".definition-mismatch.json"),
                                String.valueOf(gson.getClass().getMethod("toJson", Object.class).invoke(gson, mismatch)), StandardCharsets.UTF_8);
                    }
                    require(jsonBefore.equals(jsonAfter), "criteria, rewards, parent and display behavior retained " + id);
                }
            }
            if (Boolean.parseBoolean(p.getProperty("requireFtb", "false"))) {
                invokeCompatible(languages, "m_264110_", "ru_ru");
                invokeCompatible(languages, "m_6213_", call(client, "m_91098_"));
                Class<?> fc = Class.forName("dev.ftb.mods.ftbquests.client.ClientQuestFile", false, l);
                Object file = fc.getField("INSTANCE").get(null);
                require(file != null, "synced client quest file");
                List<Object> localizedQuests = new ArrayList<>();
                for (Object chapter : (List<?>)call(file, "getAllChapters")) {
                    requireRussian(String.valueOf(call(call(chapter, "getTitle"), "getString")), "chapter title");
                    for (Object quest : (List<?>)call(chapter, "getQuests")) {
                        String title = String.valueOf(call(call(quest, "getTitle"), "getString"));
                        requireRussian(title, "quest title");
                        List<String> description = new ArrayList<>();
                        for (Object line : (List<?>)call(quest, "getDescription")) {
                            String text = String.valueOf(call(line, "getString"));
                            if (!text.isBlank()) requireRussian(text, "quest description");
                            description.add(text);
                        }
                        localizedQuests.add(Map.of("id", call(quest, "getCodeString"), "title", title, "description", description));
                    }
                }
                require(localizedQuests.size() == ((Number)serverResult.get("quests")).intValue(), "client/server quest count match");
                Object screen = fc.getMethod("openGui").invoke(null);
                require(screen != null && ((Optional<?>)call(file, "getQuestScreen")).isPresent(), "native FTB quest book opened");
                serverResult.put("clientQuestTexts", localizedQuests);
                serverResult.put("nativeBookScreen", screen.getClass().getName());
                Object nativeScreen = client.getClass().getField("f_91080_").get(client);
                require(nativeScreen != null, "actual Minecraft screen installed for FTB book");
                serverResult.put("nativeBookWrapper", nativeScreen.getClass().getName());
                call(nativeScreen, "m_7379_");
            }
        } finally {
            invokeCompatible(languages, "m_264110_", original);
            invokeCompatible(languages, "m_6213_", call(client, "m_91098_"));
        }
        Path output = owned(p.getProperty("contentOutput"));
        require(!Files.exists(output), "fresh content evidence output");
        Map<String, Object> evidence = Map.of("advancements", records, "displayCount", records.size(),
                "allRussianExpectationsMatched", !expected.isEmpty(), "englishRoundtrip", true, "ftb", serverResult);
        Files.writeString(output, String.valueOf(gson.getClass().getMethod("toJson", Object.class).invoke(gson, evidence)), StandardCharsets.UTF_8);
        System.out.println("[CadNativeContentChecks] " + records.size() + " native advancement displays; FTB=" + serverResult.getOrDefault("quests", 0));
    }

    private static void requireRussian(String text, String label) { require(text.matches("(?s).*[А-Яа-яЁё].*") && !text.trim().startsWith("{"), label + ": " + text); }
    private static Path owned(String path) {
        Path p = Path.of(path).toAbsolutePath().normalize();
        require(Arrays.stream(p.toString().split("[\\\\/]")).anyMatch(s -> s.equalsIgnoreCase("artifacts")), "content fixture must be inside artifacts");
        return p;
    }
    private static void require(boolean ok, String label) { if (!ok) throw new IllegalStateException(label); }
    private static Object call(Object receiver, String name) throws Exception { return invokeCompatible(receiver, name); }
    private static Object invokeCompatible(Object receiver, String name, Object... args) throws Exception {
        List<Method> methods = new ArrayList<>(Arrays.asList(receiver.getClass().getMethods()));
        for (Class<?> c = receiver.getClass(); c != null; c = c.getSuperclass()) methods.addAll(Arrays.asList(c.getDeclaredMethods()));
        for (Method m : methods) {
            if (!m.getName().equals(name) || m.getParameterCount() != args.length) continue;
            Class<?>[] types = m.getParameterTypes(); boolean compatible = true;
            for (int i = 0; i < args.length; i++) if (args[i] != null && !types[i].isInstance(args[i]) && !(types[i].isPrimitive() && args[i] instanceof Number)) compatible = false;
            if (compatible) { m.setAccessible(true); return m.invoke(receiver, args); }
        }
        throw new NoSuchMethodException(receiver.getClass().getName() + "." + name);
    }
    private static Field field(Class<?> type, String name) throws Exception { Field f = type.getDeclaredField(name); f.setAccessible(true); return f; }
}
