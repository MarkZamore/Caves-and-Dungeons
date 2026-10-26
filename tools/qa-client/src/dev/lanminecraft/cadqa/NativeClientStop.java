package dev.lanminecraft.cadqa;
import java.lang.instrument.Instrumentation;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.concurrent.Executor;
/** Stops only a designated QA client which has no loaded level or server. */
public final class NativeClientStop {
    public static void agentmain(String directory, Instrumentation instrumentation) throws Exception {
        Path expected = Path.of(directory).toRealPath();
        if (!expected.toString().toLowerCase().contains("artifacts")) throw new IllegalArgumentException("Not an artifacts fixture");
        Class<?> c = Arrays.stream(instrumentation.getAllLoadedClasses()).filter(t -> t.getName().equals("net.minecraft.client.Minecraft")).findFirst().orElseThrow();
        Object mc = c.getMethod("m_91087_").invoke(null);
        if (!expected.equals(((java.io.File)c.getField("f_91069_").get(mc)).toPath().toRealPath())) throw new IllegalArgumentException("Different fixture");
        ((Executor)mc).execute(() -> {
            try {
                if (c.getField("f_91073_").get(mc) != null || c.getMethod("m_91092_").invoke(mc) != null)
                    throw new IllegalStateException("Refusing title-only stop with loaded world");
                c.getMethod("m_91395_").invoke(mc);
            } catch (ReflectiveOperationException e) { throw new IllegalStateException(e); }
        });
    }
}
