using Microsoft.Extensions.Configuration;

namespace HumanVoice_Backstage.Config;

/// <summary>
/// Static configuration class. Initialized once at startup from appsettings.json + environment variables.
/// All values are read-only after initialization.
/// </summary>
internal static class AppConfig
{
    public static string LlmModel { get; private set; } = "";
    public static string LlmToken { get; private set; } = "";
    public static string LlmApiEndpoint { get; private set; } = "";

    public static string TtsHuoShanAppId { get; private set; } = "";
    public static string TtsHuoShanToken { get; private set; } = "";
    public static string TtsCloneAppId { get; private set; } = "";
    public static string TtsCloneToken { get; private set; } = "";
    public static string TtsCozeKey { get; private set; } = "";
    public static string DefaultVoiceType { get; private set; } = "";

    public static string FunasrUrl { get; private set; } = "";
    public static string ListenerPrefix { get; private set; } = "";

    public static void Initialize(IConfiguration config)
    {
        LlmModel = GetRequired(config, "LLM:Model");
        LlmToken = GetRequired(config, "LLM:Token");
        LlmApiEndpoint = GetRequired(config, "LLM:ApiEndpoint");

        TtsHuoShanAppId = GetRequired(config, "TTS:HuoShan:AppId");
        TtsHuoShanToken = GetRequired(config, "TTS:HuoShan:Token");
        TtsCloneAppId = GetRequired(config, "TTS:Clone:AppId");
        TtsCloneToken = GetRequired(config, "TTS:Clone:Token");
        TtsCozeKey = config["TTS:Coze:Key"] ?? "";
        DefaultVoiceType = GetRequired(config, "TTS:DefaultVoiceType");

        FunasrUrl = GetRequired(config, "Communication:FunasrUrl");
        ListenerPrefix = GetRequired(config, "Communication:ListenerPrefix");
    }

    private static string GetRequired(IConfiguration config, string key)
    {
        var value = config[key];
        if (string.IsNullOrWhiteSpace(value) || value.StartsWith("YOUR_"))
        {
            throw new InvalidOperationException(
                $"Configuration key '{key}' is missing or not set. " +
                $"Copy appsettings.Example.json to appsettings.json and fill in real values, " +
                $"or set the environment variable '{key.Replace(":", "__")}'.");
        }
        return value;
    }
}
