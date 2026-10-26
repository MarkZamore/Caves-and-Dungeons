package dev.lanminecraft.cadqa;
import com.sun.tools.attach.VirtualMachine;
import java.nio.file.Path;
public final class AttachNativeStop {
    public static void main(String[] a) throws Exception {
        if (a.length != 3 || Long.parseLong(a[0]) <= 0) throw new IllegalArgumentException("PID stop.jar owned-game-directory required");
        VirtualMachine vm = VirtualMachine.attach(a[0]);
        try { vm.loadAgent(Path.of(a[1]).toRealPath().toString(), Path.of(a[2]).toRealPath().toString()); }
        finally { vm.detach(); }
    }
}
