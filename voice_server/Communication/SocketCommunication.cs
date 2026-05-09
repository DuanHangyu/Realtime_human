using System.Collections.Concurrent;
using System.Net;
using System.Net.WebSockets;
using HumanVoice_Backstage.Communication.DisponseData;
using HumanVoice_Backstage.Config;
using HumanVoice_Backstage.TTS;

namespace HumanVoice_Backstage.Communication
{
    internal class SocketCommunication
    {
        private readonly ConcurrentDictionary<WebSocket, WebSocketClientDisponseData> clientDataSave_Dic = new ConcurrentDictionary<WebSocket, WebSocketClientDisponseData>();


        HttpListener httpListener;


        public SocketCommunication()
        {
            httpListener = new HttpListener();
            httpListener.Prefixes.Add(AppConfig.ListenerPrefix);
            httpListener.Start();

        }


        public void ReceiveData()
        {
            while (true)
            {
                try
                {
                    HttpListenerContext context = httpListener.GetContext();

                    var request = context.Request;
                    var ads = request.Url.AbsolutePath;
                    switch (ads)
                    {

                        case "/recognition":
                            {
                                if (request.IsWebSocketRequest)
                                {
                                    ProcessRecognitionWebSocketRequest(context);
                                }
                                else
                                {
                                    context.Response.StatusCode = 400;
                                    context.Response.Close();
                                }
                            }
                            break;

                    }

                }
                catch (Exception ex)
                {
                    Console.WriteLine(ex);
                }
            }
        }

        private async void ProcessRecognitionWebSocketRequest(HttpListenerContext context)
        {
            await Task.Run(async() =>
             { 
                 try
                 {
                     HttpListenerWebSocketContext webSocketContext = await context.AcceptWebSocketAsync(subProtocol: null);
                     var webSocket = webSocketContext.WebSocket;

                     bool isSendConfig = context.Request.QueryString["isSendConfig"] == "true";
                     bool isKeLong = context.Request.QueryString["isKeLong"] == "true";
                     bool isLLMVoice = context.Request.QueryString["isLLMVoice"] == "true";

                     WebSocketClientDisponseData websocketClient = new WebSocketClientDisponseData();

                     websocketClient.CloseConnectCallback += this.CloseClientConnected;

                     TTSType type = TTSType.HuoShan;

                     if(isKeLong)
                         type= TTSType.keLong;
                     else if(isLLMVoice)
                         type = TTSType.Coze;


                     websocketClient.Initialized(webSocket, isSendConfig, type);
                     clientDataSave_Dic.TryAdd(webSocket, websocketClient);


                 }
                 catch (Exception ex)
                 {
                     Console.WriteLine(ex);
                 }

             });
        }

        private void CloseClientConnected(WebSocketClientDisponseData data)
        {
            try
            {
                clientDataSave_Dic.Remove(data.client, out _);
            }
            catch
            {
            }

        }
    }
}
