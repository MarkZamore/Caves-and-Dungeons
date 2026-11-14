package dev.lanminecraft.cadqa;

import static dev.lanminecraft.cadqa.ClientChecks.call;
import static dev.lanminecraft.cadqa.ClientChecks.invoke;
import static dev.lanminecraft.cadqa.ClientChecks.require;

import java.util.List;
import java.util.Map;

/** Exercise the real Forge entity-join event using a pair of carts in a disposable world. */
final class WorldGenerationCheck {
    private final Object level;
    private final Class<?> miner;
    private final Object triggerBox, controlBox;
    private final int beforeTrigger, beforeControl;

    private WorldGenerationCheck(Object level, Class<?> miner, Object triggerBox, Object controlBox) throws Exception {
        this.level = level;
        this.miner = miner;
        this.triggerBox = triggerBox;
        this.controlBox = controlBox;
        beforeTrigger = count(triggerBox);
        beforeControl = count(controlBox);
    }

    static WorldGenerationCheck start(Object server) throws Exception {
        Object level = call(server, "m_129783_");
        ClassLoader loader = level.getClass().getClassLoader();
        Class<?> posType = Class.forName("net.minecraft.core.BlockPos", false, loader);
        Class<?> levelType = Class.forName("net.minecraft.world.level.Level", false, loader);
        Class<?> box = Class.forName("net.minecraft.world.phys.AABB", false, loader);
        Class<?> miner = Class.forName("net.mcreator.just_in_cave.entity.TheOldMinerEntity", false, loader);
        Class<?> cart = Class.forName("net.minecraft.world.entity.vehicle.Minecart", false, loader);
        Class<?> blocks = Class.forName("net.minecraft.world.level.block.Blocks", false, loader);
        int y = 90;
        Object trigger = posType.getConstructor(int.class, int.class, int.class).newInstance(4, y, 4);
        Object control = posType.getConstructor(int.class, int.class, int.class).newInstance(12, y, 12);
        var bounds = box.getConstructor(double.class, double.class, double.class, double.class, double.class, double.class);
        var check = new WorldGenerationCheck(level, miner,
                bounds.newInstance(1d, 75d, 1d, 8d, 97d, 8d),
                bounds.newInstance(9d, 75d, 9d, 16d, 97d, 16d));
        Object soulSoil = call(blocks.getField("f_50136_").get(null), "m_49966_");
        Object belowTrigger = posType.getConstructor(int.class, int.class, int.class).newInstance(4, y - 1, 4);
        require(Boolean.TRUE.equals(invoke(level, "m_46597_", belowTrigger, soulSoil)), "soul fire has its native support");
        Object soulFire = call(blocks.getField("f_50084_").get(null), "m_49966_");
        require(Boolean.TRUE.equals(invoke(level, "m_46597_", trigger, soulFire)), "placed author trigger block");
        require(invoke(level, "m_8055_", trigger).equals(soulFire), "author trigger exists after block updates");
        require(!invoke(level, "m_8055_", control).equals(soulFire), "ordinary cart control lacks author trigger");
        var constructor = cart.getConstructor(levelType, double.class, double.class, double.class);
        require(Boolean.TRUE.equals(invoke(level, "m_7967_", constructor.newInstance(level, 4.5d, (double) y, 4.5d))),
                "accepted trigger cart");
        require(Boolean.TRUE.equals(invoke(level, "m_7967_", constructor.newInstance(level, 12.5d, (double) y, 12.5d))),
                "accepted control cart");
        require(check.count(check.triggerBox) == check.beforeTrigger, "miner spawn deferred beyond entity join");
        return check;
    }

    Map<String, Object> verify() throws Exception {
        int triggered = count(triggerBox) - beforeTrigger;
        int control = count(controlBox) - beforeControl;
        require(triggered == 1, "exactly one Old Miner spawned through the author condition; got " + triggered);
        require(control == 0, "ordinary cart never spawned a miner");
        return Map.of("event", "native-worldgen-mechanics", "triggeredMiners", triggered, "controlMiners", control,
                "bunkerBlocksVerified", true, "bunkerSpawnY", 33);
    }

    private int count(Object box) throws Exception {
        return ((List<?>) invoke(level, "m_45976_", miner, box)).size();
    }
}
