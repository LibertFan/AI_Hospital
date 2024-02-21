from .base_agent import Agent
from utils.register import register_class, registry


@register_class(alias="Agent.Patient.GPT")
class Patient(Agent):
    def __init__(self, args, patient_profile, medical_records, patient_id=0):
        engine = registry.get_class("Engine.GPT")(
            openai_api_key=args.patient_openai_api_key, 
            openai_api_base=args.patient_openai_api_base,
            openai_model_name=args.patient_openai_model_name, 
            temperature=args.patient_temperature, 
            max_tokens=args.patient_max_tokens,
            top_p=args.patient_top_p,
            frequency_penalty=args.patient_frequency_penalty,
            presence_penalty=args.patient_presence_penalty
        )
        self.system_message = "你是一个病人。这是你的基本资料。\n" + \
            "{}\n".format(patient_profile)

        if "现病史" in medical_records:
            self.system_message += "<现病史> {}\n".format(medical_records["现病史"].strip())        
        if "既往史" in medical_records:
            self.system_message += "<既往史> {}\n".format(medical_records["既往史"].strip())
        if "个人史" in medical_records:
            self.system_message += "<个人史> {}\n".format(medical_records["个人史"].strip())
        self.system_message += "\n"

        self.system_message += \
            "下面会有<医生>来对你的身体状况进行诊断，你需要：\n" + \
            "(1) 按照病历和基本资料的设定进行对话。\n" + \
            "(2) 在每次对话时，你都要明确对话的对象是<医生>还是<检查员>。当你对医生说话时，你要在句子开头说<对医生讲>；如果对象是<检查员>，你要在句子开头说<对检查员讲>。\n" + \
            "(3) 首先按照主诉进行回复。\n" + \
            "(4) 当<医生>询问你的现病史、既往史、个人史时，要按照相关内容进行回复。\n" + \
            "(5) 当<医生>要求或建议你去做检查时，要立即主动询问<检查员>对应的项目和结果，例如：<对检查员讲> 您好，我需要做XXX检查，能否告诉我这些检查结果？\n" + \
            "(6) 回答要口语化，尽可能短，提供最主要的信息即可。\n" + \
            "(7) 从<检查员>那里收到信息之后，将内容主动复述给<医生>。\n" + \
            "(8) 当医生给出诊断结果、对应的诊断依据和治疗方案后，在对话的末尾加上特殊字符<结束>。"
    
        super(Patient, self).__init__(engine)
        self.id = patient_id
        self.medical_records = medical_records

    @staticmethod
    def add_parser_args(parser):
        # group = parser.add_argument_group('Agent.Patient.GPT Arguments')
        parser.add_argument('--patient_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--patient_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--patient_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--patient_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--patient_max_tokens', type=int, default=2048, help='max tokens')
        parser.add_argument('--patient_top_p', type=float, default=1, help='top p')
        parser.add_argument('--patient_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--patient_presence_penalty', type=float, default=0, help='presence penalty')

    def speak(self, role, content, save_to_memory=True):
        messages = [{"role": memory[0], "content": memory[1]} for memory in self.memories]
        messages.append({"role": "user", "content": f"<{role}> {content}"})

        responese = self.engine.get_response(messages)
        
        if save_to_memory:
            self.memorize(("user", f"<{role}> {content}"))
            self.memorize(("assistant", responese))

        return responese
    
    @staticmethod
    def parse_role_content(responese):
        responese = responese.strip()

        if responese.startswith("<对医生讲>"):
            speak_to = "医生"
        elif responese.startswith("<对检查员讲>"):
            speak_to = "检查员"
        else:
            speak_to = "医生"
            # raise Exception("Response of PatientAgent must start with '<对医生讲>' or '<对检查员讲>', but current repsonse is: {}".format(responese))
        responese = responese.replace("<对医生讲>", "").replace("<对检查员讲>", "").strip()

        return speak_to, responese
