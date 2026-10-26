package dev.lanminecraft.cadlock.mixin;

import dev.lanminecraft.cadlock.WorldTypePolicy;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(targets = "net.minecraft.client.gui.screens.worldselection.WorldCreationUiState$WorldTypeEntry", remap = false)
public abstract class WorldTypeEntryMixin {
    @Inject(method = "m_267572_", at = @At("HEAD"), cancellable = true, require = 1, remap = false)
    private void cad$describeUnavailable(CallbackInfoReturnable<Object> callback) {
        Object label = WorldTypePolicy.unavailableLabel(this);
        if (label != null) callback.setReturnValue(label);
    }
}
