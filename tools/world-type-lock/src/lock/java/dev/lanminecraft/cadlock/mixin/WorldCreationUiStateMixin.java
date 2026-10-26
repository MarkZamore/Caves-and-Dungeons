package dev.lanminecraft.cadlock.mixin;

import dev.lanminecraft.cadlock.WorldTypePolicy;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(targets = "net.minecraft.client.gui.screens.worldselection.WorldCreationUiState", remap = false)
public abstract class WorldCreationUiStateMixin {
    @Inject(method = "<init>", at = @At("RETURN"), require = 1, remap = false)
    private void cad$finishInitialization(CallbackInfo callback) {
        WorldTypePolicy.finishInitialization(this);
    }

    @Inject(method = "m_267608_()V", at = @At("RETURN"), require = 1, remap = false)
    private void cad$restrictPresets(CallbackInfo callback) {
        WorldTypePolicy.refresh(this);
    }
}
