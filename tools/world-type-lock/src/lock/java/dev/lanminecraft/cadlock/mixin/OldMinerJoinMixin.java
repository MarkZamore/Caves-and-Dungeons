package dev.lanminecraft.cadlock.mixin;

import dev.lanminecraft.cadlock.WorldGenerationHooks;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Pseudo
@Mixin(targets = "net.mcreator.just_in_cave.procedures.TheOldMinerSummonProcedure", remap = false)
public abstract class OldMinerJoinMixin {
    @Inject(method = "onEntitySpawned(Lnet/minecraftforge/event/entity/EntityJoinLevelEvent;)V",
            at = @At("HEAD"), cancellable = true)
    private static void cad$waitForFullChunk(@Coerce Object event, CallbackInfo callback) {
        WorldGenerationHooks.deferMiner(event);
        callback.cancel();
    }
}
