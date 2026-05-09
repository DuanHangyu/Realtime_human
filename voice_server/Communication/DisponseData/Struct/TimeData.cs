using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace HumanVoice_Backstage.Communication.DisponseData.Struct
{
    internal class TimeData
    {
        [JsonIgnore]
        const string TimeFormat = "HH.mm.ss.fff";

        public string Time;

        public string DescriptionTime;


        public static TimeData CreateRequestLLMTime()
        {
            return new TimeData()
            {
                DescriptionTime = "用户数据提交大模型时间",
                Time = DateTime.Now.ToString(TimeFormat)
            };
        }
        public static TimeData CreateLLMResponseTime()
        {
            return new TimeData()
            {
                DescriptionTime = "调用大模型第一次响应时间",
                Time = DateTime.Now.ToString(TimeFormat)
            };
        }
         
        public static TimeData CreateTTSGenerateTime(string content)
        {
            return new TimeData()
            {
                DescriptionTime = "提交TTS合成时间,内容是：" + content,
                Time = DateTime.Now.ToString(TimeFormat)
            };
        }

        public static TimeData CreateTTSGenerateFinishTime(string content)
        {
            return new TimeData()
            {
                DescriptionTime = "TTS合成完成时间,内容是：" + content,
                Time = DateTime.Now.ToString(TimeFormat)
            };
        }
    }
}
