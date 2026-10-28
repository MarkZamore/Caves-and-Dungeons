package dev.lanminecraft.cadlock;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.function.Consumer;

/**
 * The one literal upstream advancement needs a real, required top data pack.
 * Its priority cannot depend on a world's saved ordering of mod data packs.
 * All reflected APIs are pinned to Minecraft 1.20.1 / Forge 47.3.7.
 */
public final class RussianDisplayPack {
    public static final String PACK_ID = "cad-russian-display";
    private static final String MOD_ID = "cad_world_type_lock";
    private static final String ADVANCEMENT =
            "data/nova_structures/advancements/adventure/tavern_quest.json";

    private RussianDisplayPack() { }

    public static void register() {
        try {
            Class<?> contextType = type("net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext");
            Object context = contextType.getMethod("get").invoke(null);
            Object bus = contextType.getMethod("getModEventBus").invoke(context);
            Class<?> eventType = type("net.minecraftforge.event.AddPackFindersEvent");
            Class<?> priorityType = type("net.minecraftforge.eventbus.api.EventPriority");
            Object normal = priorityType.getField("NORMAL").get(null);
            type("net.minecraftforge.eventbus.api.IEventBus").getMethod("addListener",
                    priorityType, boolean.class, Class.class, Consumer.class)
                    .invoke(bus, normal, false, eventType, (Consumer<Object>) RussianDisplayPack::findPacks);
        } catch (ReflectiveOperationException | RuntimeException failure) {
            throw new IllegalStateException("Cannot register required Russian advancement data pack", failure);
        }
    }

    private static void findPacks(Object event) {
        try {
            Class<?> eventType = type("net.minecraftforge.event.AddPackFindersEvent");
            Object serverData = type("net.minecraft.server.packs.PackType").getField("SERVER_DATA").get(null);
            if (eventType.getMethod("getPackType").invoke(event) != serverData) return;

            Class<?> modListType = type("net.minecraftforge.fml.ModList");
            Object modList = modListType.getMethod("get").invoke(null);
            Object info = modListType.getMethod("getModFileById", String.class).invoke(modList, MOD_ID);
            if (info == null) throw new IllegalStateException("Required helper is absent from ModList");
            Object file = type("net.minecraftforge.forgespi.language.IModFileInfo")
                    .getMethod("getFile").invoke(info);
            Path path = (Path) type("net.minecraftforge.forgespi.locating.IModFile")
                    .getMethod("findResource", String[].class)
                    .invoke(file, (Object) new String[] { "builtin", "russian-advancements" });
            Object pack = createPack(path);

            Class<?> sourceType = type("net.minecraft.server.packs.repository.RepositorySource");
            Object source = Proxy.newProxyInstance(loader(), new Class<?>[] { sourceType },
                    (proxy, method, args) -> {
                        if (method.getDeclaringClass() == Object.class)
                            return objectMethod(proxy, method, args);
                        if (!method.getName().equals("m_7686_") || args == null || args.length != 1)
                            throw new IllegalStateException("Unexpected repository source API: " + method);
                        @SuppressWarnings("unchecked") Consumer<Object> accept = (Consumer<Object>) args[0];
                        accept.accept(pack);
                        return null;
                    });
            eventType.getMethod("addRepositorySource", sourceType).invoke(event, source);
        } catch (ReflectiveOperationException | RuntimeException failure) {
            throw new IllegalStateException("Required Russian advancement data pack is unavailable", failure);
        }
    }

    /** Shared by native API audits; production passes only the helper's own resource path. */
    public static Object createPack(Path root) throws ReflectiveOperationException {
        if (root == null || !Files.isRegularFile(root.resolve("pack.mcmeta"))
                || !Files.isRegularFile(root.resolve(ADVANCEMENT)))
            throw new IllegalStateException("Required Russian advancement pack metadata or display is missing");

        Class<?> packType = type("net.minecraft.server.packs.repository.Pack");
        Class<?> supplierType = type("net.minecraft.server.packs.repository.Pack$ResourcesSupplier");
        Constructor<?> pathPack = type("net.minecraftforge.resource.PathPackResources")
                .getConstructor(String.class, boolean.class, Path.class);
        Object supplier = Proxy.newProxyInstance(loader(), new Class<?>[] { supplierType },
                (proxy, method, args) -> {
                    if (method.getDeclaringClass() == Object.class)
                        return objectMethod(proxy, method, args);
                    if (!method.getName().equals("m_247679_") || args == null || args.length != 1)
                        throw new IllegalStateException("Unexpected pack resources API: " + method);
                    return pathPack.newInstance((String) args[0], true, root);
                });
        Class<?> componentType = type("net.minecraft.network.chat.Component");
        Object title = componentType.getMethod("m_237113_", String.class)
                .invoke(null, "Caves and Dungeons: advancement display localization");
        Class<?> resourceType = type("net.minecraft.server.packs.PackType");
        Object serverData = resourceType.getField("SERVER_DATA").get(null);
        Class<?> positionType = type("net.minecraft.server.packs.repository.Pack$Position");
        Object top = positionType.getField("TOP").get(null);
        Class<?> sourceType = type("net.minecraft.server.packs.repository.PackSource");
        Object builtIn = sourceType.getField("f_10528_").get(null);
        Object pack = packType.getMethod("m_245429_", String.class, componentType,
                boolean.class, supplierType, resourceType, positionType, sourceType)
                .invoke(null, PACK_ID, title, true, supplier, serverData, top, builtIn);
        if (pack == null) throw new IllegalStateException("Minecraft rejected required Russian advancement pack metadata");
        return pack;
    }

    private static Object objectMethod(Object proxy, Method method, Object[] args) {
        return switch (method.getName()) {
            case "toString" -> PACK_ID;
            case "hashCode" -> System.identityHashCode(proxy);
            case "equals" -> proxy == args[0];
            default -> throw new IllegalStateException("Unexpected proxy Object API: " + method);
        };
    }

    private static ClassLoader loader() { return RussianDisplayPack.class.getClassLoader(); }
    private static Class<?> type(String name) throws ClassNotFoundException {
        return Class.forName(name, false, loader());
    }
}
