package dev.lanminecraft.cadlock;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Consumer;

/** Forge 47.3.7 lifecycle bridge for the two pinned author procedures. */
public final class WorldGenerationHooks {
    private static final Map<Object, Map<UUID, PendingMiner>> MINERS = new IdentityHashMap<>();
    private record PendingMiner(Object cart, double x, double y, double z) { }

    private WorldGenerationHooks() { }

    static void register() {
        Api.listen("net.minecraftforge.event.server.ServerStartedEvent", WorldGenerationHooks::startBunker);
        Api.listen("net.minecraftforge.event.TickEvent$LevelTickEvent", WorldGenerationHooks::tickLevel);
        Api.listen("net.minecraftforge.event.level.LevelEvent$Unload", WorldGenerationHooks::unloadLevel);
    }

    private static final class RuntimeApi { static final Api INSTANCE = new Api(); }

    public static void deferMiner(Object event) {
        Api api = RuntimeApi.INSTANCE;
        Object level = invoke(api.entityLevel, event);
        Object cart = invoke(api.eventEntity, event);
        if (!api.serverLevel.isInstance(level) || !api.minecart.isInstance(cart)) return;

        UUID id = (UUID) invoke(api.entityId, cart);
        PendingMiner pending = new PendingMiner(cart, (double) invoke(api.x, cart),
                (double) invoke(api.y, cart), (double) invoke(api.z, cart));
        synchronized (MINERS) {
            MINERS.computeIfAbsent(level, ignored -> new LinkedHashMap<>()).putIfAbsent(id, pending);
        }
    }

    private static void startBunker(Object event) {
        Api api = RuntimeApi.INSTANCE;
        // ServerStarted follows vanilla's initial chunk preparation and precedes
        // processing player logins. Bunker Down still owns gamerules, placement,
        // its saved first-start marker and the player spawn procedure.
        if (api.bunker == null) return;
        Object server = invoke(api.eventServer, event);
        invoke(api.bunker, null, invoke(api.overworld, server));
    }

    private static void tickLevel(Object event) {
        Api api = RuntimeApi.INSTANCE;
        if (Api.read(api.phase, event) != api.end) return;
        Object level = Api.read(api.tickLevel, event);
        var ready = new ArrayList<PendingMiner>();
        synchronized (MINERS) {
            Map<UUID, PendingMiner> pending = MINERS.get(level);
            if (pending == null) return;
            Object chunks = invoke(api.chunks, level);
            for (Iterator<Map.Entry<UUID, PendingMiner>> it = pending.entrySet().iterator(); it.hasNext();) {
                var entry = it.next();
                PendingMiner request = entry.getValue();
                // Only an accepted, live cart can summon. Later reloads raise a
                // fresh join event. A canceled join must never create a miner.
                if (invoke(api.findEntity, level, entry.getKey()) != request.cart()
                        || Boolean.TRUE.equals(invoke(api.removed, request.cart()))) {
                    it.remove();
                    continue;
                }
                int chunkX = (int) Math.floor(request.x()) >> 4;
                int chunkZ = (int) Math.floor(request.z()) >> 4;
                if (invoke(api.chunkNow, chunks, chunkX, chunkZ) != null) {
                    ready.add(request);
                    it.remove();
                }
            }
            if (pending.isEmpty()) MINERS.remove(level);
        }
        // The original block predicate and spawn sequence now run after the
        // cart has been indexed, with its original coordinates and a FULL chunk.
        for (PendingMiner request : ready)
            invoke(api.miner, null, level, request.x(), request.y(), request.z(), request.cart());
    }

    private static void unloadLevel(Object event) {
        synchronized (MINERS) { MINERS.remove(invoke(RuntimeApi.INSTANCE.levelEventLevel, event)); }
    }

    private static Object invoke(Method method, Object target, Object... args) {
        try {
            return method.invoke(target, args);
        } catch (InvocationTargetException failure) {
            if (failure.getCause() instanceof Error error) throw error;
            if (failure.getCause() instanceof RuntimeException runtime) throw runtime;
            throw new IllegalStateException(method.toString(), failure.getCause());
        } catch (ReflectiveOperationException failure) {
            throw new IllegalStateException(method.toString(), failure);
        }
    }

    private static final class Api {
        final Class<?> serverLevel = type("net.minecraft.server.level.ServerLevel");
        final Class<?> minecart = type("net.minecraft.world.entity.vehicle.Minecart");
        final Class<?> entity = type("net.minecraft.world.entity.Entity");
        final Class<?> levelAccessor = type("net.minecraft.world.level.LevelAccessor");
        final Method eventServer = method(type("net.minecraftforge.event.server.ServerLifecycleEvent"), "getServer");
        final Method overworld = method(type("net.minecraft.server.MinecraftServer"), "m_129783_");
        final Class<?> entityJoin = type("net.minecraftforge.event.entity.EntityJoinLevelEvent");
        final Method entityLevel = method(entityJoin, "getLevel");
        final Method eventEntity = method(entityJoin, "getEntity");
        final Method entityId = method(entity, "m_20148_");
        final Method removed = method(entity, "m_213877_");
        final Method x = method(entity, "m_20185_");
        final Method y = method(entity, "m_20186_");
        final Method z = method(entity, "m_20189_");
        final Method chunks = method(serverLevel, "m_7726_");
        final Method findEntity = method(serverLevel, "m_8791_", UUID.class);
        final Method chunkNow = method(type("net.minecraft.server.level.ServerChunkCache"), "m_7131_", int.class, int.class);
        final Class<?> tickEvent = type("net.minecraftforge.event.TickEvent");
        final Field phase = field(tickEvent, "phase");
        final Object end = read(field(type("net.minecraftforge.event.TickEvent$Phase"), "END"), null);
        final Field tickLevel = field(type("net.minecraftforge.event.TickEvent$LevelTickEvent"), "level");
        final Method levelEventLevel = method(type("net.minecraftforge.event.level.LevelEvent"), "getLevel");
        final Method bunker = procedure("net.mcreator.bunkerdown.procedures.StartWorldProcedure", levelAccessor);
        final Method miner = procedure("net.mcreator.just_in_cave.procedures.TheOldMinerSummonProcedure",
                levelAccessor, double.class, double.class, double.class, entity);

        static void listen(String event, Consumer<Object> callback) {
            Class<?> priorityType = type("net.minecraftforge.eventbus.api.EventPriority");
            Object bus = read(field(type("net.minecraftforge.common.MinecraftForge"), "EVENT_BUS"), null);
            Method add = method(type("net.minecraftforge.eventbus.api.IEventBus"), "addListener",
                    priorityType, boolean.class, Class.class, Consumer.class);
            invoke(add, bus, read(field(priorityType, "NORMAL"), null), false, type(event), callback);
        }

        private static Method procedure(String name, Class<?>... args) {
            try {
                Class<?> owner = Class.forName(name, false, WorldGenerationHooks.class.getClassLoader());
                return method(owner, "execute", args);
            } catch (ClassNotFoundException absent) {
                // The helper is also used alone by the dedicated preset QA.
                return null;
            }
        }

        private static Class<?> type(String name) {
            try {
                return Class.forName(name, false, WorldGenerationHooks.class.getClassLoader());
            } catch (ClassNotFoundException failure) {
                throw new IllegalStateException(name, failure);
            }
        }

        private static Method method(Class<?> owner, String name, Class<?>... args) {
            try {
                return owner.getMethod(name, args);
            } catch (NoSuchMethodException failure) {
                throw new IllegalStateException(owner.getName() + "." + name, failure);
            }
        }

        private static Field field(Class<?> owner, String name) {
            try {
                return owner.getField(name);
            } catch (NoSuchFieldException failure) {
                throw new IllegalStateException(owner.getName() + "." + name, failure);
            }
        }

        private static Object read(Field field, Object target) {
            try {
                return field.get(target);
            } catch (IllegalAccessException failure) {
                throw new IllegalStateException(field.toString(), failure);
            }
        }
    }
}
