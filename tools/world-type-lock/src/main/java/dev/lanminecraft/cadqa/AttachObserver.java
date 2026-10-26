package dev.lanminecraft.cadqa;

import com.sun.tools.attach.VirtualMachine;
import java.nio.file.Files;
import java.nio.file.Path;

/** Attaches only to the explicitly supplied client PID. */
public final class AttachObserver {
    private AttachObserver() { }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3 || !arguments[0].matches("[1-9][0-9]*"))
            throw new IllegalArgumentException("Usage: AttachObserver PID ABSOLUTE_AGENT_JAR ABSOLUTE_OUTPUT_JSONL");
        if (Long.parseLong(arguments[0]) == ProcessHandle.current().pid())
            throw new IllegalArgumentException("Self-attach is not supported");
        Path jar = Path.of(arguments[1]).toAbsolutePath().normalize();
        if (!Files.isRegularFile(jar) || !jar.getFileName().toString().endsWith(".jar"))
            throw new IllegalArgumentException("An existing observer jar is required");
        Path output = WorldTypeObserver.artifactPath(arguments[2]);
        VirtualMachine machine = VirtualMachine.attach(arguments[0]);
        try { machine.loadAgent(jar.toString(), output.toString()); }
        finally { machine.detach(); }
        System.out.println("Read-only world type observer attached to the supplied PID.");
    }
}
