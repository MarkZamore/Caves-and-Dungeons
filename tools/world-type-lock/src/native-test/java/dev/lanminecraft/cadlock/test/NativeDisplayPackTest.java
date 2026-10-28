package dev.lanminecraft.cadlock.test;

import com.google.gson.JsonObject;
import dev.lanminecraft.cadlock.RussianDisplayPack;
import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.function.Consumer;

/** Actual native pack metadata/repository/resource selection; no replacement game classes. */
public final class NativeDisplayPackTest {
    private static final String DISPLAY = "data/nova_structures/advancements/adventure/tavern_quest.json";
    private NativeDisplayPackTest() { }

    public static void main(String[] args) throws Exception {
        if (args.length != 2)
            throw new IllegalArgumentException("Usage: NativeDisplayPackTest BUILTIN_ROOT ARTIFACTS_EVIDENCE");
        Path root = Path.of(args[0]).toAbsolutePath();
        Path evidence = Path.of(args[1]).toAbsolutePath();
        boolean owned = false;
        for (Path part : evidence) owned |= part.toString().equalsIgnoreCase("artifacts");
        if (!owned) throw new IllegalArgumentException("Native evidence must stay inside artifacts");
        Files.createDirectories(evidence);
        type("net.minecraft.SharedConstants").getMethod("m_142977_").invoke(null);
        type("net.minecraft.server.Bootstrap").getMethod("m_135870_").invoke(null);

        Object required = RussianDisplayPack.createPack(root);
        Class<?> packType = type("net.minecraft.server.packs.repository.Pack");
        require(Boolean.TRUE.equals(packType.getMethod("m_10449_").invoke(required)), "required=true");
        require(packType.getMethod("m_10451_").invoke(required).toString().equals("TOP"), "position TOP");
        Class<?> sourceType = type("net.minecraft.server.packs.repository.RepositorySource");
        Class<?> supplierType = type("net.minecraft.server.packs.repository.Pack$ResourcesSupplier");
        Object supplier = Proxy.newProxyInstance(loader(), new Class<?>[] { supplierType }, (proxy, method, values) -> {
            if (method.getDeclaringClass() == Object.class) return objectMethod(proxy, method, values);
            require(method.getName().equals("m_247679_"), "exact ResourcesSupplier API");
            return type("net.minecraftforge.resource.PathPackResources")
                    .getConstructor(String.class, boolean.class, Path.class)
                    .newInstance((String) values[0], true, root);
        });
        Class<?> component = type("net.minecraft.network.chat.Component");
        Object title = component.getMethod("m_237113_", String.class).invoke(null, "upstream priority probe");
        Class<?> resourceType = type("net.minecraft.server.packs.PackType");
        Object serverData = resourceType.getField("SERVER_DATA").get(null);
        Class<?> positionType = type("net.minecraft.server.packs.repository.Pack$Position");
        Class<?> packSource = type("net.minecraft.server.packs.repository.PackSource");
        Object upstream = packType.getMethod("m_245429_", String.class, component,
                boolean.class, supplierType, resourceType, positionType, packSource)
                .invoke(null, "mod:upstream", title, false, supplier, serverData,
                        positionType.getField("BOTTOM").get(null), packSource.getField("f_10528_").get(null));
        require(upstream != null, "native metadata accepts upstream comparison pack");
        Object repositorySource = Proxy.newProxyInstance(loader(), new Class<?>[] { sourceType },
                (proxy, method, values) -> {
                    if (method.getDeclaringClass() == Object.class) return objectMethod(proxy, method, values);
                    require(method.getName().equals("m_7686_"), "exact RepositorySource API");
                    @SuppressWarnings("unchecked") Consumer<Object> accept = (Consumer<Object>) values[0];
                    accept.accept(upstream);
                    accept.accept(required);
                    return null;
                });
        Object sources = Array.newInstance(sourceType, 1);
        Array.set(sources, 0, repositorySource);
        Class<?> repositoryType = type("net.minecraft.server.packs.repository.PackRepository");
        Object repository = repositoryType.getConstructor(sources.getClass()).newInstance(sources);
        repositoryType.getMethod("m_10506_").invoke(repository);
        // Both native fresh selection and an old saved mod:* selection omit the new builtin ID.
        for (List<String> selected : List.of(List.<String>of(), List.of("mod:upstream"))) {
            repositoryType.getMethod("m_10509_", Collection.class).invoke(repository, selected);
            List<?> packs = new ArrayList<>((Collection<?>) repositoryType.getMethod("m_10524_").invoke(repository));
            require(!packs.isEmpty(), "selected packs exist");
            require(packType.getMethod("m_10446_").invoke(packs.get(packs.size() - 1))
                    .equals(RussianDisplayPack.PACK_ID), "required pack added last at native TOP");
            Class<?> fallbackType = type("net.minecraft.server.packs.resources.FallbackResourceManager");
            Object manager = fallbackType.getConstructor(resourceType, String.class).newInstance(serverData, "nova_structures");
            List<Object> opened = new ArrayList<>();
            try {
                for (Object pack : packs) {
                    Object resources = packType.getMethod("m_10445_").invoke(pack);
                    opened.add(resources);
                    fallbackType.getMethod("m_215377_", type("net.minecraft.server.packs.PackResources"))
                            .invoke(manager, resources);
                }
                Object location = type("net.minecraft.resources.ResourceLocation").getConstructor(String.class)
                        .newInstance("nova_structures:advancements/adventure/tavern_quest.json");
                Object resource = ((Optional<?>) fallbackType.getMethod("m_213713_", location.getClass())
                        .invoke(manager, location)).orElseThrow();
                require(type("net.minecraft.server.packs.resources.Resource").getMethod("m_215506_")
                        .invoke(resource).equals(RussianDisplayPack.PACK_ID), "native resource winner is builtin pack");
            } finally {
                for (Object resources : opened) type("net.minecraft.server.packs.PackResources")
                        .getMethod("close").invoke(resources);
            }
        }

        Path metadataMissing = Files.createTempDirectory(evidence, "missing-metadata-");
        Files.createDirectories(metadataMissing.resolve(DISPLAY).getParent());
        Files.copy(root.resolve(DISPLAY), metadataMissing.resolve(DISPLAY));
        requireRejected(metadataMissing, "missing pack.mcmeta");
        Path displayMissing = Files.createTempDirectory(evidence, "missing-display-");
        Files.copy(root.resolve("pack.mcmeta"), displayMissing.resolve("pack.mcmeta"));
        requireRejected(displayMissing, "missing literal display override");

        JsonObject report = new JsonObject();
        report.addProperty("minecraft", "1.20.1");
        report.addProperty("forge", "47.3.7");
        report.addProperty("packId", RussianDisplayPack.PACK_ID);
        report.addProperty("requiredTop", true);
        report.addProperty("autoNew", true);
        report.addProperty("autoOld", true);
        report.addProperty("resourceWinner", RussianDisplayPack.PACK_ID);
        report.addProperty("metadataMissingRejected", true);
        report.addProperty("displayMissingRejected", true);
        report.addProperty("serializerEnvironment", "native Minecraft1.20.1 + Forge PathPackResources47.3.7");
        report.addProperty("runtimeClientVerified", false);
        report.addProperty("runtimeEventDispatchVerified", false);
        Files.writeString(evidence.resolve("native-display-pack-proof.json"), report + "\n", StandardCharsets.UTF_8);
        System.out.println("NativeDisplayPackTest PASS: native required TOP, new/old selections, resource priority, missing metadata/display refused. Full client/event dispatch not asserted.");
    }

    private static void requireRejected(Path root, String label) throws Exception {
        boolean rejected = false;
        try { RussianDisplayPack.createPack(root); }
        catch (IllegalStateException expected) { rejected = true; }
        require(rejected, label + " must fail");
    }
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    private static Class<?> type(String name) throws ClassNotFoundException { return Class.forName(name); }
    private static ClassLoader loader() { return NativeDisplayPackTest.class.getClassLoader(); }
    private static Object objectMethod(Object proxy, Method method, Object[] values) {
        return switch (method.getName()) {
            case "hashCode" -> System.identityHashCode(proxy);
            case "equals" -> proxy == values[0];
            case "toString" -> "native-priority-proof";
            default -> throw new AssertionError(method);
        };
    }
}
