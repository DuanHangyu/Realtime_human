using HumanVoice_Backstage.Communication;
using HumanVoice_Backstage.Config;
using HumanVoice_Backstage.TTS;
using Microsoft.Extensions.Configuration;
using NAudio.Lame;
using System.Net;

namespace HumanVoice_Backstage
{
    internal class Program
    {
        static HttpListener httpListener;

        static async Task Main(string[] args)
        {
            var config = new ConfigurationBuilder()
                .SetBasePath(AppDomain.CurrentDomain.BaseDirectory)
                .AddJsonFile("appsettings.json", optional: false, reloadOnChange: false)
                .AddEnvironmentVariables()
                .Build();
            AppConfig.Initialize(config);

            try
            {
                LameDLL.LoadNativeDLL(AppDomain.CurrentDomain.BaseDirectory);
            }
            catch
            {

            }
            new SocketCommunication().ReceiveData();

        }
    }
}
// dotnet run --project HumanVoice_BG