using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace HumanVoice_Backstage.Communication.DisponseData.Struct
{
    internal class DataStructRoot
    {
        //数据类型
        // TTS  StartLLM Finish  InvokeTime
        //InvokeTime  这是提示时间信息，调试用的
        public string DataType;

        public string Data;

        public static DataStructRoot CreateTTS(object data)
        {
            return new DataStructRoot()
            {
                DataType = "TTS",
                Data = JsonConvert.SerializeObject(data)
            };
        }

        public static DataStructRoot CreateInvokeTime(object data)
        {
            return new DataStructRoot()
            {
                DataType = "InvokeTime",
                Data = JsonConvert.SerializeObject(data)
            };
        }

        public static DataStructRoot CreateFinish( )
        {
            return new DataStructRoot()
            {
                DataType = "Finish"
            };
        }

        public static DataStructRoot CreateStartLLM(string content)
        {
            return new DataStructRoot()
            {
                DataType = "StartLLM",
                Data = content
            };
        }

        public string  ToJson()
        {
           return   JsonConvert.SerializeObject(this);
        }
    }
}
