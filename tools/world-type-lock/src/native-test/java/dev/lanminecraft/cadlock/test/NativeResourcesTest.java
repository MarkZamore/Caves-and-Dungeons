package dev.lanminecraft.cadlock.test;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.serialization.JsonOps;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import net.minecraft.SharedConstants;
import net.minecraft.core.registries.Registries;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.Bootstrap;
import net.minecraft.server.packs.metadata.pack.PackMetadataSectionSerializer;
import net.minecraft.world.level.levelgen.presets.WorldPreset;
import net.minecraft.world.level.levelgen.presets.WorldPresets;

/** Actual Minecraft serializers and vanilla bootstrap, with no replacement game fixtures. */
public final class NativeResourcesTest {
    private NativeResourcesTest() { }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length < 1 || arguments.length > 2)
            throw new IllegalArgumentException("Usage: NativeResourcesTest RESOURCE_ROOT [REPORT_JSON]");
        Path resources = Path.of(arguments[0]);
        SharedConstants.m_142977_();
        Bootstrap.m_135870_();

        JsonObject metadata = read(resources.resolve("pack.mcmeta")).getAsJsonObject();
        var nativeMetadata = new PackMetadataSectionSerializer().m_6322_(metadata.getAsJsonObject("pack"));
        if (nativeMetadata.m_10374_() != 15)
            throw new AssertionError("Minecraft1.20.1 must parse the shared resource/data pack_format as15");
        if (nativeMetadata.m_10373_().getString().isBlank())
            throw new AssertionError("Minecraft metadata description must not be blank");
        int metadataCount = 0;
        try (var paths = Files.walk(resources)) {
            for (Path path : paths.filter(candidate -> candidate.getFileName().toString().equals("pack.mcmeta")).toList()) {
                var section = new PackMetadataSectionSerializer().m_6322_(read(path).getAsJsonObject().getAsJsonObject("pack"));
                if (section.m_10374_() != 15 || section.m_10373_().getString().isBlank())
                    throw new AssertionError("Every helper/builtin pack must have native format15 and description: " + path);
                metadataCount++;
            }
        }
        if (metadataCount != 2)
            throw new AssertionError("Expected helper plus mandatory Russian-display builtin pack metadata, found " + metadataCount);

        var provider = VanillaRegistries.m_255371_();
        var ops = RegistryOps.m_255058_(JsonOps.INSTANCE, provider);
        JsonElement customResource = read(resources.resolve(
                "data/caves_and_dungeons/worldgen/world_preset/modded_mines.json"));
        WorldPreset custom = WorldPreset.f_226414_.parse(ops, customResource)
                .getOrThrow(false, message -> { throw new AssertionError("Native custom preset decode: " + message); });
        WorldPreset normal = provider.m_255025_(Registries.f_256729_)
                .m_255043_(WorldPresets.f_226437_).m_203334_();
        JsonElement encodedCustom = WorldPreset.f_226414_.encodeStart(ops, custom)
                .getOrThrow(false, message -> { throw new AssertionError("Native custom preset encode: " + message); });
        JsonElement encodedNormal = WorldPreset.f_226414_.encodeStart(ops, normal)
                .getOrThrow(false, message -> { throw new AssertionError("Native normal preset encode: " + message); });
        if (!encodedNormal.equals(encodedCustom))
            throw new AssertionError("Custom preset changes native dimensions. normal=" + encodedNormal
                    + " custom=" + encodedCustom);
        JsonObject dimensions = encodedCustom.getAsJsonObject().getAsJsonObject("dimensions");
        if (dimensions.size() != 3 || !dimensions.has("minecraft:overworld")
                || !dimensions.has("minecraft:the_nether") || !dimensions.has("minecraft:the_end"))
            throw new AssertionError("Expected exactly native Overworld, Nether and End dimensions");
        requireLabel(resources, "ru_ru", "Шахты с Модами");
        requireLabel(resources, "en_us", "Modded Mines");

        JsonObject report = new JsonObject();
        report.addProperty("minecraft", "1.20.1");
        report.addProperty("nativeWorldPresetCodec", true);
        report.addProperty("nativePackMetadataSerializer", true);
        report.addProperty("packFormat", nativeMetadata.m_10374_());
        report.addProperty("nativePackMetadataCount", metadataCount);
        report.addProperty("serializerEnvironment", "unpatched native Minecraft1.20.1");
        report.addProperty("nativeNormalDimensionsEqual", true);
        report.addProperty("dimensionCount", dimensions.size());
        report.addProperty("runtimeClientVerified", false);
        report.add("encodedDimensions", encodedCustom);
        if (arguments.length == 2) {
            Path output = Path.of(arguments[1]);
            Files.createDirectories(output.toAbsolutePath().getParent());
            Files.writeString(output, report + "\n", StandardCharsets.UTF_8);
        }
        System.out.println("NativeResourcesTest PASS: actual Minecraft1.20.1 codec matches all native normal dimensions; both pack metadata format15; RU/EN labels. Runtime client not asserted.");
    }

    private static void requireLabel(Path root, String language, String expected) throws Exception {
        JsonObject values = read(root.resolve("assets/cad_world_type_lock/lang/" + language + ".json")).getAsJsonObject();
        JsonElement label = values.get("generator.caves_and_dungeons.modded_mines");
        if (label == null || !label.getAsString().equals(expected))
            throw new AssertionError("Missing or wrong actual preset label in " + language);
    }

    private static JsonElement read(Path path) throws Exception {
        return JsonParser.parseString(Files.readString(path, StandardCharsets.UTF_8));
    }
}
