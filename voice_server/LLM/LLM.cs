using HumanVoice_Backstage.Config;
using Newtonsoft.Json.Linq;
using System.Net;
using System.Text;
using static System.Runtime.InteropServices.JavaScript.JSType;

namespace HumanVoice_Backstage.LLM
{
    internal sealed class LLM
    {
        public class UserDataStruct
        {
            public string model;
            public List<Message> messages;


            /// <summary>
            /// 是否流式
            /// </summary>
            public bool stream;

            /// <summary>
            /// 采样温度，控制输出的随机性，必须为正数
            /// 取值范围是：(0.0,1.0]，不能等于 0，默认值为 0.95,值越大，会使输出更随机，更具创造性；值越小，输出会更加稳定或确定
            /// 建议您根据应用场景调整 top_p 或 temperature 参数，但不要同时调整两个参数
            /// </summary>
            public float temperature;

            /// <summary>
            /// 用温度取样的另一种方法，称为核取样
            /// 取值范围是：(0.0, 1.0) 开区间，不能等于 0 或 1，默认值为 0.7
            /// 模型考虑具有 top_p 概率质量tokens的结果
            /// 例如：0.1 意味着模型解码器只考虑从前 10% 的概率的候选集中取tokens
            /// 建议您根据应用场景调整 top_p 或 temperature 参数，但不要同时调整两个参数
            /// </summary>
            public float top_p;

            public float top_k;
            public float max_prompt_tokens;
            public float max_new_tokens;
        }

        public class Message
        {
            private Message() { }

            public string role { get; set; }
            public string content { get; set; }

            public static Message CreateSystemMessage(string content)
            {
                return new Message() { role = "system", content = content };
            }

            public static Message CreateUserMessage(string content)
            {
                return new Message() { role = "user", content = content };
            }

            public static Message CreateAssistantMessage(string content)
            {
                return new Message() { role = "assistant", content = content };
            }
        }



        string systemMessage = "角色设定：";


        UserDataStruct dataStruct;
//dify fasegpt coze 
        static string model => AppConfig.LlmModel;
        static string token => AppConfig.LlmToken;
        public LLM(string systemMessage = null)
        {
          //  System.Console.WriteLine(systemMessage);
            if (!string.IsNullOrWhiteSpace(systemMessage))
            {
                this.systemMessage = systemMessage;
            }

            dataStruct = new UserDataStruct()
            {
                model = model,
                stream = true,
                messages = new List<Message>(),
                temperature = 1,
                top_p = 0.7f,
            };

            dataStruct.messages.Add(Message.CreateSystemMessage(this.systemMessage));
        }

        public async void RequestGPT(string prompt, Action<string, bool> callback)
        {

            try
            {
                var userMessage = Message.CreateUserMessage(prompt);
                dataStruct.messages.Add(userMessage);


                var requestKimiJson = Newtonsoft.Json.JsonConvert.SerializeObject
                   (dataStruct);

                HttpWebRequest httpWebRequest = HttpWebRequest.Create(AppConfig.LlmApiEndpoint) as HttpWebRequest;
                httpWebRequest.Method = "POST";
                httpWebRequest.ContentType = "application/json";
                httpWebRequest.Headers.Add("Authorization", "Bearer " + token);

                using (var requestSt = httpWebRequest.GetRequestStream())
                {
                    var buffer = Encoding.UTF8.GetBytes(requestKimiJson);
                    requestSt.Write(buffer, 0, buffer.Length);
                }

                var response = httpWebRequest.GetResponse();
                using var responseSt = response.GetResponseStream();
                using StreamReader resposneSTR = new StreamReader(responseSt);
                string mess = "";
                while (!resposneSTR.EndOfStream)
                {
                    requestKimiJson = resposneSTR.ReadLine();
                    if (requestKimiJson.StartsWith("data:"))
                    {
                        if (requestKimiJson.Contains("[DONE]"))
                            break;
                        var jsonP = JToken.Parse(requestKimiJson.Replace("data:", ""));
                        var item = jsonP["choices"][0];

                        var tt = item["delta"].SelectToken("content")?.ToString();

                        if (!string.IsNullOrEmpty(tt))
                        {

                            callback(tt, false);
                            mess += tt;
                        }
                        var finish = item.SelectToken("finish_reason");

                        if (finish != null && finish.ToString() == "stop")
                        {
                            break;
                        }
                    }
                }

                callback("", true);

                if (!string.IsNullOrEmpty(mess))
                {

                    dataStruct.messages.Add(Message.CreateAssistantMessage(mess));
                }
                else
                {
                    dataStruct.messages.Remove(userMessage);
                }
            }

            catch (Exception ex)
            {
                await Console.Out.WriteLineAsync(ex.ToString());
            }
            UpdateRemoveMessages();
        }


        private void UpdateRemoveMessages()
        {
            while (dataStruct.messages.Count > 10)
            {
                dataStruct.messages.RemoveAt(1);
            }
        }
    }
}
