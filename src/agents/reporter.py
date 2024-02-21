import re
from .base_agent import Agent
from utils.register import register_class, registry


@register_class(alias="Agent.Reporter.GPT")
class Reporter(Agent):
    def __init__(self, args, reporter_info=None):
        engine = registry.get_class("Engine.GPT")(
            openai_api_key=args.reporter_openai_api_key, 
            openai_api_base=args.reporter_openai_api_base,
            openai_model_name=args.reporter_openai_model_name, 
            temperature=args.reporter_temperature, 
            max_tokens=args.reporter_max_tokens,
            top_p=args.reporter_top_p,
            frequency_penalty=args.reporter_frequency_penalty,
            presence_penalty=args.reporter_presence_penalty
        )

        self.edit_query = True
        if reporter_info is None:
            self.system_message = \
                "你是医院的数据库管理员，负责收集、汇总和整理病人的病史和检查数据。\n"
        else: self.system_message = reporter_info
        
        super(Reporter, self).__init__(engine)

    @staticmethod
    def add_parser_args(parser):
        # group = parser.add_argument_group('Agent.Reporter.GPT Arguments')
        parser.add_argument('--reporter_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--reporter_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--reporter_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--reporter_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--reporter_max_tokens', type=int, default=2048, help='max tokens')
        parser.add_argument('--reporter_top_p', type=float, default=1, help='top p')
        parser.add_argument('--reporter_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--reporter_presence_penalty', type=float, default=0, help='presence penalty')

    def speak(self, medical_records, content, save_to_memory=False):
        system_message = self.system_message + '\n\n' + \
            "这是你收到的病人的检查结果。\n" + \
            f"#查体#\n{medical_records['查体'].strip()}\n" + \
            f"#辅助检查#\n{medical_records['辅助检查'].strip()}\n\n" + \
            "下面会有病人或者医生来查询，你要忠实地按照收到的检查结果，找到对应的项目，并按照下面的格式来回复。\n\n" + \
            "#检查项目#\n- xxx: xxx\n- xxx: xxx\n#xx检查#\n- xxx: xxx\n- xxx: xxx\n\n" + \
            "如果无法查询到对应的检查项目则回复：\n" + \
            "- xxx: 无异常"
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": "您好，我需要做基因组测序，能否告诉我这些检查结果？"},
            {"role": "assistant", "content": "#检查项目#\n- 基因组测序"},
            {"role": "user", "content": content}
        ]
        
        responese = self.engine.get_response(messages)
        return responese
    
    @staticmethod
    def parse_content(response):
        if "#检查项目#" not in response:
            return False
        response = re.findall(r"检查项目\#(.+?)\n\n", response, re.S)
        return response.strip()


@register_class(alias="Agent.Reporter.GPTV2")
class ReporterV2(Agent):
    def __init__(self, args, reporter_info=None):
        engine = registry.get_class("Engine.GPTV2")(
            openai_api_key=args.reporter_openai_api_key, 
            openai_api_base=args.reporter_openai_api_base,
            openai_model_name=args.reporter_openai_model_name, 
            temperature=args.reporter_temperature, 
            max_tokens=args.reporter_max_tokens,
            top_p=args.reporter_top_p,
            frequency_penalty=args.reporter_frequency_penalty,
            presence_penalty=args.reporter_presence_penalty
        )

        self.edit_query = True
        if reporter_info is None:
            self.system_message = \
                "你是医院的数据库管理员，负责收集、汇总和整理病人的病史和检查数据。\n"
        else: self.system_message = reporter_info
        
        super(Reporter, self).__init__(engine)

    @staticmethod
    def add_parser_args(parser):
        # group = parser.add_argument_group('Agent.Reporter.GPT Arguments')
        parser.add_argument('--reporter_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--reporter_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--reporter_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--reporter_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--reporter_max_tokens', type=int, default=2048, help='max tokens')
        parser.add_argument('--reporter_top_p', type=float, default=1, help='top p')
        parser.add_argument('--reporter_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--reporter_presence_penalty', type=float, default=0, help='presence penalty')

    def speak(self, medical_records, content, save_to_memory=False):
        
        examination_query = self.parse_examination_queries(content)

        system_message = self.system_message + '\n\n' + \
            "这是你收到的病人的检查结果。\n" + \
            f"#查体#\n{medical_records['查体'].strip()}\n" + \
            f"#辅助检查#\n{medical_records['辅助检查'].strip()}\n\n" + \
            "下面会有病人或者医生来查询，你要忠实地按照收到的检查结果，找到对应的项目，并按照下面的格式来回复。\n\n" + \
            "#检查项目#\n- xxx: xxx\n- xxx: xxx\n#xx检查#\n- xxx: xxx\n- xxx: xxx\n\n" + \
            "如果无法查询到对应的检查项目则回复：\n" + \
            "- xxx: 无异常"
        
        messages = [{"role": "system", "content": system_message},
                    {"role": "user", "content": "#检查项目#\n- 基因组测序"},
                    {"role": "assistant", "content": "#检查项目#\n-基因组测序: 无异常"},
                    {"role": "user", "content": examination_query}]
        responese = self.engine.get_response(messages)
        return responese
    
    def parse_examination_queries(self, query):
        system_message = "你是医院负责检查的自动化接待员。请你利用掌握的医学检查的命名实体的知识，从病人的检查申请当中解析出指向明确的专业医学检查项目，方便后面的检查科室进行检查。\n\n请按照下面的格式的输出：\n#检查项目#\n- xxx\n- xxx\n\n如果没有找到具体的医学检查项目，请输出：\n#检查项目#\n- 无"
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": "您好，医生建议我进行以下检查：\n1. 血常规检查\n2. 腹部超声检查\n3. 病毒检测\n\n请问这些检查的具体项目和结果是什么？谢谢！"},
            {"role": "assistant", "content": "#检查项目#\n- 血常规检查\n- 腹部超声检查\n- 病毒检测"}, # 常规需求
            {"role": "user", "content": "您好，医生告诉我根据CT扫描和PET-CT扫描的结果，初步得出以下结论：右肺上叶有一个大小约为2.6*1.9cm的实性结节。双肺下叶也有散在的淡薄浸润影。医生建议我进行进一步的检查，例如活检。谢谢。"},
            {"role": "assistant", "content": "#检查项目#\n- 肺部活检"}, # 检索需求
            {"role": "user", "content": "医生初步诊断为中风（脑卒中），建议我进行急性期治疗、康复治疗和预防措施。请问我需要做哪些急性期治疗？康复治疗包括哪些方面？预防措施有哪些？谢谢！"},
            {"role": "assistant", "content": "#检查项目#\n- 无"}, # 检索
            {"role": "user", "content": "您好，我需要做以下检查：\n1. 脖子肿块的触诊\n2. 脖子淋巴结的检查\n3. 必要时，超声波检查或其他影像学检查\n\n请问这些检查的具体项目和结果是什么？谢谢！"},
            {"role": "assistant", "content": "#检查项目#\n- 脖子肿块的触诊\n- 脖子的超声波检查"}, # 只保留指向明确的检查项目
            {"role": "user", "content": "我需要了解一下我的检查结果。可以告诉我具体的检查项目和结果吗？谢谢！？"},
            {"role": "assistant", "content": "#检查项目#\n- 无"}, # 防止被hack
            {"role": "user", "content": "您好，医生建议我进行医学检查来确认怀孕状态和胎儿的健康状况。请问我需要进行哪些检查？并且能否告诉我这些检查的结果？谢谢。？"},
            {"role": "assistant", "content": "#检查项目#\n- 无"}, # 防止被hack
            {"role": "user", "content": "医生说我的诊断是左胫骨平台骨折、左胫骨上段骨折和左外踝骨折，骨折有明显的移位。需要进行手术治疗，包括内固定术和可能的骨折复位术。术后还需要进行物理治疗恢复关节功能。同时需要使用止痛药来控制疼痛，康复期间可能需要使用拐杖或轮椅来帮助移动。"},
            {"role": "assistant", "content": "#检查项目#\n- 无"}, # 防止被hack
            {"role": "user", "content": "\n- 您好，医生建议我进行血液检查，包括血红蛋白水平、凝血功能和炎症指标等，请问这些检查的具体项目和结果是什么？"},
            {"role": "assistant", "content": "#检查项目#\n- 血常规检查\n - 血红蛋白水平\n - 凝血功能\n - 炎症指标"}, # 结构化的检查项目
            {"role": "user", "content": "\n- 医生说我已经进行了胃镜检查，结果显示可能存在贲门和胃底的癌症嫌疑以及消化道的出血。病理学结果显示存在溃疡和出血，局部腺体数量减少，局部腺体增生。医生建议我进行CT扫描或内窥镜超声（EUS）来评估癌症是否扩散。请问这些检查的结果是什么？谢谢。"},
            {"role": "assistant", "content": "#检查项目#\n- CT扫描\n- 内窥镜超声"}, # 结构化的检查项目
            {"role": "user", "content": "您好，根据医生的建议，我需要进行以下检查：\n1. 重复尿妊娠试验。\n2. 血液测试，测量hCG水平。\n3. 经阴道超声检查，成像子宫和卵巢的情况。\n请告诉我这些检查的结果。谢谢！"},
            {"role": "assistant", "content": "#检查项目#\n- 尿妊娠试验\n- 血常规检查\n- 阴道超声检查"}, # 
            {"role": "user", "content": query},
        ]
        
        response = self.get_response(messages)
        if "#检查项目#" not in response:
            return None
        for message in response.split("\n"):
            if message in ["- 无", "-无"]:
                return None
        simple_examination_queries, examination_queries = [], []
        start = False
        for message in response.split("\n"):
            if start and message.startswith("-"):
                examination_query = message[1:].strip()
                # Using re.sub to replace the matched patterns with an empty string
                examination_queries.append(examination_query)
                # simple_examination_query = re.sub(r'\(.*?\)', '', examination_query)
                # simple_examination_query = re.sub(r'（.*?）', '', simple_examination_query)
                # simple_examination_queries.append(simple_examination_query)
            elif "#检查项目#" in message:
                start = True
            elif message == "":
                start = False
        examination_queries = "\n- ".join(["#检查项目#"] + examination_queries)
        return examination_queries

    @staticmethod
    def parse_content(response):
        if "#检查项目#" not in response:
            return False
        response = re.findall(r"检查项目\#(.+?)\n\n", response, re.S)
        return response.strip()
        # raw_response = response
        # response = response + "\n\n"
        # if "#检查项目#" in response:
        #     response = re.findall(r"检查项目\#(.+?)\n\n", response, re.S)
        #     response = response[0].strip()
        # else:
        #     raise Exception("Response of ReporterAgent must have '#检查项目#', but current repsonse is: {}".format(raw_response))
        # if response.startswith("#检查项目#"):
        #     response = '这是我的检查结果\n' + response.split('\n\n')[0]
        # else:
        #     raise Exception("Response of ReporterAgent must start with '#检查项目#', but current repsonse is: {}".format(response))
        # return response
