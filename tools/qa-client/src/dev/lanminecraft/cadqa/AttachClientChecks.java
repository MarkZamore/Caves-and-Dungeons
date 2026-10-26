package dev.lanminecraft.cadqa;

import com.sun.tools.attach.VirtualMachine;
import java.nio.file.Files;
import java.nio.file.Path;

public final class AttachClientChecks {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("PID agent.jar qa.properties required");
        long pid = Long.parseLong(args[0]);
        if (pid <= 0 || pid == ProcessHandle.current().pid()) throw new IllegalArgumentException("Invalid target PID");
        Path jar = Path.of(args[1]).toRealPath();
        Path spec = Path.of(args[2]).toRealPath();
        if (!Files.isRegularFile(jar) || !Files.isRegularFile(spec)) throw new IllegalArgumentException("Missing QA inputs");
        VirtualMachine vm = VirtualMachine.attach(Long.toString(pid));
        try { vm.loadAgent(jar.toString(), spec.toString()); }
        finally { vm.detach(); }
        System.out.println("Native client checks attached to designated PID " + pid);
    }
}
