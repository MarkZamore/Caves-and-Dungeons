package dev.lanminecraft.cadlock.mixin;

import dev.lanminecraft.cadlock.WorldTypePolicy;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(targets = "net.minecraft.client.gui.screens.worldselection.CreateWorldScreen", remap = false)
public abstract class CreateWorldScreenMixin {
    @Inject(method = "m_100972_()V", at = @At("HEAD"), cancellable = true, require = 1, remap = false)
    private void cad$enforceCreation(CallbackInfo callback) {
        if (!WorldTypePolicy.beforeCreate(this)) callback.cancel();
    }
}
