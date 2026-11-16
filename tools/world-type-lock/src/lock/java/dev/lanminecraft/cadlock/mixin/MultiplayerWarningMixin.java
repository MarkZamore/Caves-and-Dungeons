package dev.lanminecraft.cadlock.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(targets = "net.minecraft.client.gui.screens.TitleScreen", remap = false)
public abstract class MultiplayerWarningMixin {
    // Use the native "don't show again" branch only inside the accepted
    // Multiplayer button action. Leave the actual Options value untouched.
    @Redirect(method = "m_210871_(Lnet/minecraft/client/gui/components/Button;)V",
            at = @At(value = "FIELD", target = "Lnet/minecraft/client/Options;f_92083_:Z"),
            require = 1, allow = 1)
    private boolean cad$skipThirdPartyServerWarning(@Coerce Object options) {
        return true;
    }
}
