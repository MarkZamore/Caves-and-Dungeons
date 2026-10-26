package dev.lanminecraft.cadqa;

import java.lang.instrument.Instrumentation;
import java.lang.reflect.Method;
import java.nio.file.Path;
import java.util.Arrays;

/** Recovery cleanup only: requests the owned fixture server's native halt/save. */
public final class NativeStop {
    public static void agentmain(String gameDirectory, Instrumentation instrumentation) throws Exception {
        Path expected = Path.of(gameDirectory).toRealPath();
        if (!expected.isAbsolute() || !expected.toString().toLowerCase().contains("artifacts"))
            throw new IllegalArgumentException("Owned artifacts game directory required");
        Class<?> c = Arrays.stream(instrumentation.getAllLoadedClasses()).filter(t -> t.getName().equals("net.minecraft.client.Minecraft")).findFirst().orElseThrow();
        Object client = c.getMethod("m_91087_").invoke(null);
        Path actual = ((java.io.File) c.getField("f_91069_").get(client)).toPath().toRealPath();
        if (!actual.equals(expected)) throw new IllegalArgumentException("Different client fixture");
        Class<?> hooks = Class.forName("net.minecraftforge.server.ServerLifecycleHooks", false, c.getClassLoader());
        Object server = hooks.getMethod("getCurrentServer").invoke(null);
        if (server == null) throw new IllegalStateException("No integrated fixture server to stop");
        Object data = server.getClass().getMethod("m_129910_").invoke(server);
        Object settings = data.getClass().getMethod("m_5926_").invoke(data);
        String levelName = String.valueOf(settings.getClass().getMethod("m_46917_").invoke(settings));
        if (!levelName.startsWith("CAD-QA-")) throw new IllegalStateException("Not a designated QA world");
        Method halt = server.getClass().getMethod("m_7570_", boolean.class);
        halt.invoke(server, false);
        System.out.println("[CadNativeClientChecks] Requested native asynchronous halt/save for " + levelName);
    }
}
