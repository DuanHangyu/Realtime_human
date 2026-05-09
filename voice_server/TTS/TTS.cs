using HumanVoice_Backstage.Config;
using Microsoft.CognitiveServices.Speech;
using Newtonsoft.Json;
using System.IO;
using System.Net;
using System.Xml.Serialization;

namespace HumanVoice_Backstage.TTS
{
    public  enum TTSType
    {
        HuoShan,
        keLong,
        Coze
    }
    internal sealed class TTS
    {
        TTSType type= TTSType.HuoShan;

        string voiceType = AppConfig.DefaultVoiceType;


        public TTS(string voiceType = null, TTSType type=  TTSType.HuoShan)
        {
            this.type = type;
            if (!string.IsNullOrWhiteSpace(voiceType))
            {
                this.voiceType = voiceType;
            }
        }

        public byte[] Generate(string content)
        {
            if (content == "??")
                return null;

            switch (type)
            {
                case TTSType.HuoShan:
                    return Syn(content); 
                case TTSType.keLong:
                    return Syn_Kelong(content); 
                case TTSType.Coze:
                    return Syn_Coze(content);
                default:
                    return null;
            } 
        }

        string appid = AppConfig.TtsHuoShanAppId;
        string token = AppConfig.TtsHuoShanToken;

        static string host = "openspeech.bytedance.com";
        static string apiUrl = $"https://{host}/api/v1/tts";

        public byte[] Syn(string content)
        {
            var requestJson = new
            {
                app = new
                {
                    appid = appid,
                    token = token,
                    cluster = "volcano_tts"
                },
                user = new
                {
                    uid = appid
                },
                audio = new
                {
                    voice_type = voiceType,
                    encoding = "wav",
                    rate = "16000",
                },
                request = new
                {
                    reqid = Guid.NewGuid().ToString(),
                    text = content,
                    text_type = "plain",
                    operation = "query",
                    with_frontend = 1,
                    frontend_type = "unitTson"
                }
            };

            string requestBody = JsonConvert.SerializeObject(requestJson);

            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(apiUrl);
            request.Method = "POST";
            request.ContentType = "application/json";
            request.Headers["Authorization"] = $"Bearer;{token}";

            using (var streamWriter = new StreamWriter(request.GetRequestStream()))
            {
                streamWriter.Write(requestBody);
            }

            try
            {
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                using (var streamReader = new StreamReader(response.GetResponseStream()))
                {
                    string responseBody = streamReader.ReadToEnd();

                    var responseJson = JsonConvert.DeserializeObject<dynamic>(responseBody);
                    if (responseJson.data != null)
                    {
                        byte[] audioData = Convert.FromBase64String((string)responseJson.data);
                        return audioData;
                    }
                }
            }
            catch (WebException ex)
            {
                try
                {
                    using (var streamReader = new StreamReader(ex.Response.GetResponseStream()))
                    {
                        string errorResponse = streamReader.ReadToEnd();
                        Console.WriteLine($"Error response: \n{errorResponse}");
                    }
                }
                catch
                {

                }
            }
            catch (Exception e)
            {
                Console.WriteLine($"Exception caught: {e}");
            }

            return null;
        }









        //克隆
        static string appid_kelong = AppConfig.TtsCloneAppId;
        static string accessToken = AppConfig.TtsCloneToken;
        static string cluster = "volcano_icl";
        static string host_kelong = "openspeech.bytedance.com";
        static string apiUrl_kelong = $"https://{host}/api/v1/tts";
        static string uid = "4334";
        public byte[] Syn_Kelong(string content)
        {
            var requestJson = new
            {
                app = new
                {
                    appid = appid_kelong,
                    token = accessToken,
                    cluster = cluster
                },
                user = new
                {
                    uid = uid
                },
                audio = new
                {
                    voice_type = voiceType,
                    encoding = "wav",
                    rate = "16000",
                    speed_ratio = 1.0,
                    volume_ratio = 1.0,
                    pitch_ratio = 1.0,
                },
                request = new
                {
                    reqid = Guid.NewGuid().ToString(),
                    text = content,
                    text_type = "plain",
                    operation = "query",
                    with_frontend = 1,
                    frontend_type = "unitTson"
                }
            };


            string requestBody = JsonConvert.SerializeObject(requestJson);

            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(apiUrl);
            request.Method = "POST";
            request.ContentType = "application/json";
            request.Headers["Authorization"] = $"Bearer;{accessToken}";

            using (var streamWriter = new StreamWriter(request.GetRequestStream()))
            {
                streamWriter.Write(requestBody);
            }


            try
            {
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                using (var streamReader = new StreamReader(response.GetResponseStream()))
                {
                    string responseBody = streamReader.ReadToEnd();

                    var responseJson = JsonConvert.DeserializeObject<dynamic>(responseBody);
                    if (responseJson.data != null)
                    {
                        byte[] audioData = Convert.FromBase64String((string)responseJson.data);
                        return audioData;

                    }
                }

            }

            catch (Exception e)
            {
                Console.WriteLine($"Exception caught: {e}");
            }

            return null;
        }











        //克隆
        static string cozeKey = AppConfig.TtsCozeKey;
        public byte[] Syn_Coze(string content)
        {
            var requestJson = new
            {
               input=content,
                voice_id= voiceType,
                response_format="wav",
                 sample_rate= 16000,
                 speed= 1.1f
            };


            string requestBody = JsonConvert.SerializeObject(requestJson);

            HttpWebRequest request = (HttpWebRequest)WebRequest.Create("https://api.coze.cn/v1/audio/speech");
            request.Method = "POST";
            request.ContentType = "application/json";
            request.Headers["Authorization"] = $"Bearer {cozeKey}";

            using (var streamWriter = new StreamWriter(request.GetRequestStream()))
            {
                streamWriter.Write(requestBody);
            }


            try
            {
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                {
                    using MemoryStream memoryStream = new MemoryStream();
                    response.GetResponseStream().CopyTo(memoryStream);

                    return memoryStream.ToArray();
                } 
            }

            catch (Exception e)
            {
                Console.WriteLine($"Exception caught: {e}");
            }

            return null;
        }
    }
}
