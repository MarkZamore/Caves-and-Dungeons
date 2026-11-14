package dev.lanminecraft.cadlock.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Pseudo
@Mixin(targets = "net.mcreator.bunkerdown.procedures.StartWorldProcedure", remap = false)
public abstract class BunkerWorldLoadMixin {
    @Inject(method = "onWorldLoad(Lnet/minecraftforge/event/level/LevelEvent$Load;)V",
            at = @At("HEAD"), cancellable = true)
    private static void cad$waitForPreparedWorld(CallbackInfo callback) {
        callback.cancel();
    }
}
