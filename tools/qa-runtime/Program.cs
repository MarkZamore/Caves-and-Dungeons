using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using CmlLib.Core;
using CmlLib.Core.Auth;
using CmlLib.Core.ProcessBuilder;
using Minecraft;

if (args.Length < 3 || args[0] is not ("prepare" or "client" or "catalog" or "install"))
    throw new ArgumentException("Usage: prepare|client|catalog|install <isolated-artifacts-root> <pack-folder> [label]");
var root = Path.GetFullPath(args[1]);
if (!root.Contains(Path.DirectorySeparatorChar + "artifacts" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
    throw new IOException("QA root must be inside artifacts.");
var paths = new AppPaths(root);
paths.Ensure();
var logger = new Logger(paths.LogFile);
var json = new JsonSerializerOptions { WriteIndented = true };
if (args[0] is "catalog" or "install")
{
    var catalog = new PackCatalogService(paths, logger);
    await catalog.RefreshOnceAsync();
    var entry = catalog.Find(args[2]) ?? throw new IOException("Published pack absent from startup catalog.");
    Console.WriteLine(JsonSerializer.Serialize(new { entry.Name, sources = catalog.Sources.Count }, json));
    if (args[0] == "install")
    {
        var sync = new PortablePackSyncService(paths, logger) { Catalog = catalog };
        using var downloadTimeout = new CancellationTokenSource(TimeSpan.FromMinutes(30));
        var installed = await sync.SyncAsync(args[2], null, downloadTimeout.Token);
        Console.WriteLine(JsonSerializer.Serialize(installed, json));
        if (installed.Outcome is not (PackSyncOutcome.Installed or PackSyncOutcome.Updated or PackSyncOutcome.UpToDate))
            throw new IOException("Published pack was not installed by the production synchronizer.");
    }
    return;
}
using var runtimes = new PackRuntimeService(paths, logger);
using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(30));
string? last = null;
var progress = new Progress<RuntimePreparationProgress>(p =>
{
    var text = p.Stage + ": " + p.Message;
    if (text != last) { last = text; Console.WriteLine(text); }
});
var runtime = await runtimes.PrepareAsync(args[2], progress, timeout.Token);
var evidence = Path.Combine(root, "evidence");
Directory.CreateDirectory(evidence);
File.WriteAllText(Path.Combine(evidence, "runtime.json"), JsonSerializer.Serialize(runtime, json));
Console.WriteLine($"PREPARED {runtime.Descriptor.MinecraftVersion} {runtime.Descriptor.Loader.Type} {runtime.Descriptor.Loader.Version}");
if (args[0] == "prepare") return;
var label = args.Length > 3 ? args[3] : "baseline";
if (!System.Text.RegularExpressions.Regex.IsMatch(label, "^[A-Za-z0-9_-]{1,64}$")) throw new ArgumentException("Invalid label.");
using var instances = new PackInstanceService(paths, logger);
var instance = await instances.PrepareAsync(args[2], timeout.Token);
var launcher = runtimes.CreateLocalLauncher(runtime);
var profile = await launcher.GetVersionAsync(runtime.ProfileId, timeout.Token);
var gamePath = new MinecraftPath(instance.GameDirectory)
{
    Library = launcher.MinecraftPath.Library, Versions = launcher.MinecraftPath.Versions,
    Assets = launcher.MinecraftPath.Assets, Resource = launcher.MinecraftPath.Resource, Runtime = launcher.MinecraftPath.Runtime
};
var home = Path.Combine(root, "java-home");
var tmp = Path.Combine(root, "java-temp");
Directory.CreateDirectory(home); Directory.CreateDirectory(tmp);
var player = "CavesAudit";
var session = MSession.CreateOfflineSession(player);
var uuid = MD5.HashData(Encoding.UTF8.GetBytes("OfflinePlayer:" + player));
uuid[6] = (byte)((uuid[6] & 15) | 48); uuid[8] = (byte)((uuid[8] & 63) | 128);
session.UUID = new Guid(uuid, bigEndian: true).ToString("N");
var options = new MLaunchOption
{
    Path = gamePath, JavaPath = runtime.JavaPath, Session = session,
    MaximumRamMb = 6144, MinimumRamMb = 1024, GameLauncherName = "CavesIsolatedQA", GameLauncherVersion = "1",
    VersionType = "Forge", FullScreen = false, ScreenWidth = 1120, ScreenHeight = 720,
    ExtraJvmArguments = new List<MArgument>
    {
        new("-Dfile.encoding=UTF-8"), new("-Duser.home=" + home), new("-Djava.io.tmpdir=" + tmp),
        new("-XX:ErrorFile=" + Path.Combine(evidence, "hs_err_pid%p.log"))
    }
};
using var process = launcher.BuildProcess(profile, options);
process.StartInfo.WorkingDirectory = instance.GameDirectory;
process.StartInfo.UseShellExecute = false; process.StartInfo.CreateNoWindow = true;
process.StartInfo.WindowStyle = ProcessWindowStyle.Hidden;
process.StartInfo.RedirectStandardOutput = true; process.StartInfo.RedirectStandardError = true;
process.StartInfo.StandardOutputEncoding = Encoding.UTF8; process.StartInfo.StandardErrorEncoding = Encoding.UTF8;
foreach (var pair in new Dictionary<string, string>
{
    ["TEMP"] = tmp, ["TMP"] = tmp, ["APPDATA"] = Path.Combine(home, "AppData", "Roaming"),
    ["LOCALAPPDATA"] = Path.Combine(home, "AppData", "Local")
}) { Directory.CreateDirectory(pair.Value); process.StartInfo.Environment[pair.Key] = pair.Value; }
var console = Path.Combine(evidence, label + "-console.log");
if (File.Exists(console)) throw new IOException("Use a fresh evidence label.");
using var output = new StreamWriter(console, false, new UTF8Encoding(false)) { AutoFlush = true };
var gate = new object();
void Record(string? line) { if (line is not null) lock (gate) output.WriteLine(line); }
process.OutputDataReceived += (_, e) => Record(e.Data); process.ErrorDataReceived += (_, e) => Record(e.Data);
process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine();
File.WriteAllText(Path.Combine(evidence, label + "-process.json"), JsonSerializer.Serialize(new
{
    processId = process.Id, utc = DateTimeOffset.UtcNow, gameDirectory = instance.GameDirectory,
    loader = runtime.Descriptor.Loader, javaPath = runtime.JavaPath, label
}, json));
Console.WriteLine($"CLIENT_STARTED pid={process.Id} log={console}");
await process.WaitForExitAsync();
File.WriteAllText(Path.Combine(evidence, label + "-exit.json"), JsonSerializer.Serialize(new
{ processId = process.Id, exitCode = process.ExitCode, utc = DateTimeOffset.UtcNow }, json));
Console.WriteLine("CLIENT_EXIT " + process.ExitCode);
Environment.ExitCode = process.ExitCode;
