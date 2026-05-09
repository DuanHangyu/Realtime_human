using HumanVoice_Backstage.Communication.DisponseData.Struct;
using HumanVoice_Backstage.Config;
using HumanVoice_Backstage.TTS;
using NAudio.Wave;
using System.Buffers;
using System.Collections.Concurrent;
using System.Net.Sockets;
using System.Net.WebSockets;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.RegularExpressions;

namespace HumanVoice_Backstage.Communication.DisponseData
{
    internal class WebSocketClientDisponseData
    {
        const string pattern = @"[^。.！!？?…,，；;、：;]*[。.！!？?…,，；;、：;]";
        string PunctuationPattern = @"[。.！!？?…,，；;、：;]";

        /// <summary>
        /// 缓冲区的大小
        /// </summary>
        private const int ContentSize = 65535 / 2;

        /// <summary>
        /// 关闭连接回调
        /// 参数一：那个Socket，参数二：那一组，参数三：那个ID
        /// </summary>
        public event Action<WebSocketClientDisponseData> CloseConnectCallback;


        ConcurrentQueue<Task<DataStructRoot>> taskQueue = new ConcurrentQueue<Task<DataStructRoot>>();

        internal WebSocket client;

        internal ClientWebSocket funasr;


        int sampleRate;

        /// <summary>
        /// 缓冲区
        /// </summary>
        private byte[] buffer;
        private byte[] fuansrBuffer;

        LLM.LLM openAi;
        TTS.TTS tts;


        public const string SendConfig = "{\"chunk_size\":[5,10,5],\"wav_name\":\"h5\",\"is_speaking\":true,\"chunk_interval\":10,\"itn\":false,\"mode\":\"offline\",\"hotwords\":\"{\\\"你好\\\":20,\\\"小卿\\\":100,\\\"hello world\\\":40}\"}";
        static string url => AppConfig.FunasrUrl;
        public WebSocketClientDisponseData()
        {
            buffer = new byte[ContentSize];
            fuansrBuffer = new byte[ContentSize];


        }

        ~WebSocketClientDisponseData()
        {
            client?.Dispose();
            client = null;

            CloseConnectCallback = null;
        }

        /// <summary>
        /// 初始化
        /// </summary>
        /// <param name="socket">socket引用</param>
        public async void Initialized(WebSocket socket, bool isSendConfig,TTSType type)
        {
            string voiceType = null, systemMessage = null;
            try
            {
                if (isSendConfig)
                {
                    var p = await socket.ReceiveAsync(new ArraySegment<byte>(buffer, 0, buffer.Length), default);
                    var content = Encoding.UTF8.GetString(buffer, 0, p.Count);
                    var tjson = Newtonsoft.Json.Linq.JToken.Parse(content);
                    voiceType = tjson["voiceType"].ToString();
                    systemMessage = tjson["systemMessage"].ToString();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"接受配置信息报错：{ex}");
                CloseConnectCallback?.Invoke(this);
            }

            openAi = new LLM.LLM(systemMessage);
            tts = new TTS.TTS(voiceType, type);

            client = socket;
             
            ReceiveData();

            ConnectFunasr();
        }

        async void ConnectFunasr()
        {

            if (funasr != null)
            {
                if (funasr.State == WebSocketState.Open)
                {
                    await funasr.CloseAsync(WebSocketCloseStatus.Empty, "", default);
                }
            }
            funasr = new ClientWebSocket();
            await funasr.ConnectAsync(new Uri(url), default);
            await funasr.SendAsync(Encoding.UTF8.GetBytes(SendConfig), WebSocketMessageType.Text, true, default);
            ReceiveFunasrData();

        }

        public static float[] ReadWavFileAsFloatArray(string filePath)
        {
            using (var reader = new AudioFileReader(filePath))
            {
                // 创建 float[] 缓冲区，大小为文件的长度
                var totalSamples = (int)(reader.Length / sizeof(float));
                var floatBuffer = new float[totalSamples];

                int samplesRead = reader.Read(floatBuffer, 0, totalSamples);

                // 如果实际读取的样本少于缓冲区大小，截断数组
                if (samplesRead < totalSamples)
                {
                    Array.Resize(ref floatBuffer, samplesRead);
                }

                return floatBuffer;
            }
        }

        public void SendData(string text)
        {
            byte[] by = ArrayPool<byte>.Shared.Rent(text.Length * 3);
            try
            {
                int count = Encoding.UTF8.GetBytes(text, 0, text.Length, by, 0);

                SendData(by, 0, count, WebSocketMessageType.Text);
            }
            finally
            {
                ArrayPool<byte>.Shared.Return(by);
            }
        }

        void SendData(byte[] data, int offset, int dataCount, WebSocketMessageType messageType = WebSocketMessageType.Binary)
        {
            try
            {
                lock (client)
                {
                    client.SendAsync(new ReadOnlyMemory<byte>(data, offset, dataCount), messageType, true, default);

                }
            }
            catch
            {
                CloseConnectCallback?.Invoke(this);
            }
        }

        private async void ReceiveData()
        {
            int r = 0;
            try
            {
                while (true)
                {
                    var result = await client.ReceiveAsync(new Memory<byte>(buffer, r, buffer.Length - r), default);

                    if (result.EndOfMessage)
                    {
                        int count = r + result.Count;

                        if (result.MessageType == WebSocketMessageType.Text)
                        {
                            var content = Encoding.UTF8.GetString(buffer, 0, count);
                            DisponseTextData(content);
                        }
                        else
                        {
                            DisponseData(buffer, count);
                        }


                        r = 0;
                    }
                    else
                    {
                        r += result.Count;
                    }
                }

            }
            catch (Exception ex)
            {
                CloseConnectCallback?.Invoke(this);
            }
        }


        private async void ReceiveFunasrData()
        {
            int r = 0;
            string pattern = @"^[\p{P}\p{S}]";
            try
            {
                while (true)
                {
                    var result = await funasr.ReceiveAsync(new Memory<byte>(fuansrBuffer, r, fuansrBuffer.Length - r), default);

                    if (result.EndOfMessage)
                    {
                        int count = r + result.Count;

                        var content = Encoding.UTF8.GetString(fuansrBuffer, 0, count);

                        var tjson = Newtonsoft.Json.Linq.JToken.Parse(content);

                        var mode = tjson.SelectToken("mode");
                        if (mode != null)
                        {
                            bool isEnd = mode.ToString() == "2pass-offline";
                            content = tjson["text"].ToString();

                            if (!string.IsNullOrEmpty(content))
                            {
                                content = Regex.Replace(content, pattern, "");
                                DisponseTextData(content);
                            }
                        }

                        r = 0;
                    }
                    else
                    {
                        r += result.Count;
                    }
                }

            }
            catch (Exception ex)
            {
            }
        }

        bool isVoiceRecognize = true;
        string llmContent;
        Task taskQueueTask;

        bool isLLMCallback;


        protected virtual void DisponseTextData(string content)
        {
            if (!isVoiceRecognize)
                return;

            ConnectFunasr();
            if (!string.IsNullOrEmpty(content))
            {
                isVoiceRecognize = false;
                isLLMCallback = false;
                llmContent = string.Empty;

                this.SendInfo(DataStructRoot.CreateStartLLM(content));

                this.openAi.RequestGPT(content, LLMCallback);

                this.SendInfo(DataStructRoot.CreateInvokeTime(TimeData.CreateRequestLLMTime())); //调用大模型请求时间 

            }
        }


        protected virtual void DisponseData(byte[] buffer, int count)
        {
            if (!isVoiceRecognize)
                return;

            funasr.SendAsync(new ArraySegment<byte>(buffer, 0, count), WebSocketMessageType.Binary, true, default);
        }

        private static SemaphoreSlim semaphore = new SemaphoreSlim(3);

        private void LLMCallback(string arg1, bool arg2)
        {
            if (!isLLMCallback)
            {
                this.SendInfo(DataStructRoot.CreateInvokeTime(TimeData.CreateLLMResponseTime())); //返回大模型第一次响应时间
                isLLMCallback = true;
            }

            arg1 = arg1.Replace("*", "");
            arg1 = arg1.Replace("#", "");

            //  Console.WriteLine("arg1:"+arg1);
            llmContent += arg1;

            MatchCollection matches = Regex.Matches(llmContent, pattern);

            foreach (Match match in matches)
            {
                var temp = match.Value;
                llmContent = llmContent.Replace(temp, "");

                this.taskQueue.Enqueue(Task.Run(() => TTSGenerate(temp)));

                if (taskQueueTask == null)
                {
                    taskQueueTask = Task.Run(TaskQueue);
                }
            }

            if (arg2)
            {
                this.taskQueue.Enqueue(Task.Run(() => LLMFinish(llmContent)));
            }
        }

        async Task<DataStructRoot> TTSGenerate(string content)
        {
            await semaphore.WaitAsync();

            this.SendInfo(DataStructRoot.CreateInvokeTime(TimeData.CreateTTSGenerateTime(content))); //通知tts合成时间 
            var result = this.tts.Generate(Regex.Replace(content, PunctuationPattern, ""));

            semaphore.Release();


            string audioData = "";

            if (result != null)
                audioData = Convert.ToBase64String(result);
            this.SendInfo(DataStructRoot.CreateInvokeTime(TimeData.CreateTTSGenerateFinishTime(content))); //通知tts合成时间 
            return DataStructRoot.CreateTTS(new TTSData() { AudioData = audioData, Text = content });

        }

        /// <summary>
        /// 大模型结束
        /// </summary>
        async Task<DataStructRoot> LLMFinish(string content)
        {
            if (!string.IsNullOrEmpty(content))
            {
                var audio = TTSGenerate(content);
                this.SendInfo(audio.Result);
            }
            var data = DataStructRoot.CreateFinish();//返回大模型结束

            isVoiceRecognize = true;

            return data;
        }

        async void TaskQueue()
        {
            while (this.taskQueue.Count > 0 || !isVoiceRecognize)
            {
                if (this.taskQueue.TryDequeue(out var action))
                {
                    this.SendInfo(await action);
                }
                else
                {
                    await Task.Yield();
                }
            }

            this.taskQueueTask = null;
        }



        void SendInfo(DataStructRoot data)
        {
            if (data != null)
                this.SendData(data.ToJson());
        }
    }
}
