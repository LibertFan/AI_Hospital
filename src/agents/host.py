import re
from .base_agent import Agent
from utils.register import register_class, registry


@register_class(alias="Agent.Host.GPT")
class Host(Agent):
    def __init__(self, args, host_info=None):
        engine = registry.get_class("Engine.GPT")(
            openai_api_key=args.host_openai_api_key, 
            openai_api_base=args.host_openai_api_base,
            openai_model_name=args.host_openai_model_name, 
            temperature=args.host_temperature, 
            max_tokens=args.host_max_tokens,
            top_p=args.host_top_p,
            frequency_penalty=args.host_frequency_penalty,
            presence_penalty=args.host_presence_penalty
        )

        if host_info is None:
            self.system_message = \
                "你是医院的数据库管理员，负责收集、汇总和整理病人的病史和检查数据。\n"
        else: self.system_message = host_info

        super(Host, self).__init__(engine)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument('--host_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--host_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--host_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--host_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--host_max_tokens', type=int, default=2048, help='max tokens')
        parser.add_argument('--host_top_p', type=float, default=1, help='top p')
        parser.add_argument('--host_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--host_presence_penalty', type=float, default=0, help='presence penalty')

    def memorize(self, message):
        self.memories.append(message)

    def forget(self):
        self.memories = [("system", self.system_message)]

    def speak(self, content):
        system_message = self.system_message
        
        messages = [{"role": "system", "content": system_message},
                    {"role": "user", "content": "您好，我需要做基因组测序，能否告诉我这些检查结果？"},
                    {"role": "assistant", "content": "#检查项目#\n-基因组测序: 无异常"},
                    {"role": "user", "content": content}]
        responese = self.engine.get_response(messages)
        return responese
    
    def summarize_diagnosis(self, doctors, patient):
        # build query message
        int_to_char = {0: "A", 1: "B", 2: "C", 3: "D", 4: "E", 5: "F"}
        diagnosis_by_different_doctors = ""
        for i, doctor in enumerate(doctors):
            diagnosis_by_different_doctors += \
                "##医生{}##\n\n".format(int_to_char[i]) + \
                "#诊断结果#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="诊断结果")) + \
                "#诊断依据#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="诊断依据")) + \
                "#治疗方案#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="治疗方案")) 
        # build system message
        doctor_names = ["##医生{}##".format(int_to_char.get(i)) for i, _ in enumerate(doctors)]
        if len(doctor_names) > 2:
            doctor_names = "、".join(doctor_names[:-2]) + "、" + doctor_names[-2] + "和" + doctor_names[-1]        
        else: doctor_names = doctor_names[0] + "和" + doctor_names[1]       
        system_message = "你是一个资深的#主任医生#。\n" + \
            "你正在主持一场医生针对患者病情的会诊，参与的医生有{}。\n".format(doctor_names) + \
            "病人的基本情况如下：\n#症状#\n{}\n\n#辅助检查#\n{}\n\n".format(
                doctors[0].get_diagnosis_by_patient_id(patient.id, key="症状"),
                doctors[0].get_diagnosis_by_patient_id(patient.id, key="辅助检查")
            ) + \
            "(1) 你需要听取每个医生的诊断报告，其中包含对病人的#诊断结果#、#诊断依据#和#治疗方案#。\n" + \
            "(2) 你需要汇总每个医生的信息，给出对病人的最终诊断。\n\n" + \
            "(3) 请你按照下面的格式来进行输出。\n" + \
            "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
            "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
            "#治疗方案#\n(1) xxx\n(2) xxx\n"
        # run engine
        messages = [{"role": "system", "content": system_message},
            {"role": "user", "content": diagnosis_by_different_doctors}]
        diagnosis = self.engine.get_response(messages)
        return diagnosis

    def measure_agreement(self, doctors, patient, discussion_mode="Parallel"):
        # revise_mode in ["Parallel_with_Critique", "Parallel"]
        # build query message
        # int_to_char = {0: "A", 1: "B", 2: "C", 3: "D"}
        diagnosis_by_different_doctors = ""
        for i, doctor in enumerate(doctors):
            diagnosis_by_different_doctors += \
                "##医生{}##\n\n".format(doctor.name) + \
                "#诊断结果#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="诊断结果")) + \
                "#诊断依据#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="诊断依据")) + \
                "#治疗方案#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="治疗方案")) 
        # build system message
        doctor_names = ["##医生{}##".format(doctor.name) for i, doctor in enumerate(doctors)]
        if len(doctor_names) > 2:
            doctor_names = "、".join(doctor_names[:-2]) + "、" + doctor_names[-2] + "和" + doctor_names[-1]        
        else: doctor_names = doctor_names[0] + "和" + doctor_names[1] 

        system_message = "你是一个资深的主任医生。\n" + \
            "你正在主持一场医生针对患者病情的会诊，参与的医生有{}。\n".format(doctor_names) + \
            "病人的基本情况如下：\n#症状#\n{}\n\n#辅助检查#\n{}\n\n".format(
                doctors[0].get_diagnosis_by_patient_id(patient.id, key="症状"),
                doctors[0].get_diagnosis_by_patient_id(patient.id, key="辅助检查")
            )
        system_message += "你需要听取每个医生的诊断报告，其中包含对病人的#诊断结果#、#诊断依据#和#治疗方案#。\n\n" + \
            "请你按照下面的格式来进行输出。\n" + \
            "(1) 如果医生之间已经达成一致，请你输出：\n" + \
            "#结束#\n\n" + \
            "(2) 如果医生之间没有达成一致，请你输出：\n" + \
            "#继续#"
        # run engine
        messages = [{"role": "system", "content": system_message},
            {"role": "user", "content": diagnosis_by_different_doctors}]
        judgement = self.engine.get_response(messages)
        # parse response
        if "#结束#" in judgement:
            judgement = "#结束#"
            return judgement
        elif "#继续#" in judgement:
            if discussion_mode == "Parallel":
                judgement = "#继续#"
                return judgement
            elif discussion_mode == "Parallel_with_Critique":
                system_message = "你是一个资深的主任医生。\n" + \
                    "你正在主持一场医生针对患者病情的会诊，参与的医生有{}。\n".format(doctor_names) + \
                    "病人的基本情况如下：\n#症状#\n{}\n\n#辅助检查#\n{}\n\n".format(
                        doctors[0].get_diagnosis_by_patient_id(patient.id, key="症状"),
                        doctors[0].get_diagnosis_by_patient_id(patient.id, key="辅助检查")
                    )
                system_message += "(1) 你需要听取每个医生的诊断报告，其中包含对病人的#诊断结果#、#诊断依据#和#治疗方案#。\n" + \
                    "(2) 请你按照重要性列出最多3个需要讨论的争议点，按照下面的格式输出：\n" + \
                    "(a) xxx\n" + \
                    "(b) xxx\n"
                messages = [{"role": "system", "content": system_message},
                    {"role": "user", "content": diagnosis_by_different_doctors}]
                judgement = self.engine.get_response(messages)
                judgement = re.sub('.*\(a\)', '(a)', judgement, flags=re.DOTALL)
                return judgement
        else: raise Exception("{}".format(judgement))
        
    def summarize_symptom_and_examination(self, doctors, patient, reporter):
        ## host summarizes the symptom and examination from different doctors
        # build query message
        int_to_char = {0: "A", 1: "B", 2: "C", 3: "D"}
        symptom_and_examination_by_diff_doctors = ""
        for i, doctor in enumerate(doctors):
            symptom_and_examination_by_diff_doctors += "##医生{}##\n".format(int_to_char[i])
            for key in ["症状", "辅助检查"]:
                value = doctor.get_diagnosis_by_patient_id(patient.id, key=key)
                if value is not None:
                    symptom_and_examination_by_diff_doctors += "#{}#\n{}\n\n".format(key, value)

        doctor_names = ["##医生{}##".format(int_to_char.get(i)) for i, _ in enumerate(doctors)]
        if len(doctor_names) > 2:
            doctor_names = "、".join(doctor_names[:-2]) + "、" + doctor_names[-2] + "和" + doctor_names[-1]        
        else: doctor_names = doctor_names[0] + "和" + doctor_names[1]   
        messages = [
            {
            "role": "system",
            "content": "你是一个资深的主任医生。\n" + \
                "你正在主持一场医生针对患者病情的会诊，参与的有{}。".format(doctor_names) + \
                "你需要听取每个医生的诊断报告，总结患者的症状并汇总检查结果。\n\n" + \
                    "(1) 每个医生说话时都会以##xx##开始。例如，##医生A##开始讲话时，则会出现##医生A##的字样。每个医生的诊断报告当中都会包含#症状#和#辅助检查#。\n" + \
                    "(2) 请你汇总医生们掌握的#症状#和#辅助检查#的信息，无论是医生们都提及的信息，还是某个医生提及而其他医生遗漏的信息。\n" + \
                    "(3) 如果不同医生提供的信息存在相互矛盾的部分，请按照下面的方式指出来。\n" + \
                        "(3.1) 如果是#症状#上的不一致，请向病人询问，以#询问病人#开头。\n" + \
                        "(3.2) 如果是#辅助检查#，请向检查员询问，以#询问检查员#开头。\n" + \
                        "(3.3) 如果没有问题，则输出“无”。\n\n" + \
                    "请你按照下面的格式来进行输出。\n" + \
                        "#症状#\n(1) xx\n(2) xx\n\n" + \
                        "#询问病人#\n(1) xx\n(2) xx\n\n" + \
                        "#辅助检查#\n(1) xx\n(2) xx\n\n" + \
                        "#询问检查员#\n(1) xx\n(2) xx\n"
            },
            # {
            # "role": "user",
            # "content": "##医生A##\n#症状#\n(1) 发烧，体温时高时低，最高达到39度\n(2) 咳嗽，有痰\n(3) 头痛\n(4) 感到冷\n(5) 晕眩\n(6) 全身乏力\n(7) 食欲不振\n(8) 睡眠不好\n\n#辅助检查#\n(1) 血常规：\n   - 白细胞计数：10.02×10^9/L（升高）\n   - 血小板计数：366×10^9/L（升高）\n   - 红细胞计数：4.98×10^12/L\n   - 血红蛋白：134g/L\n(2) 胸部X光：心肺膈未见异常\n\n##医生B##\n#症状#\n(1)发烧，体温时高时低\n(2)感到冷\n(3)头痛得厉害，有时候会晕\n(4)咳嗽，咳出来的痰很多\n(5)全身没劲儿\n(6)吃不下饭\n(7)睡不好觉\n\n#辅助检查#\n(1)全血细胞计数（CBC）显示白细胞计数10.02×10^9/L（升高），血小板计数366×10^9/L（升高）\n(2)痰液培养无异常\n(3)胸部X光检查心肺膈未见异常"
            # },
            # {
            # "role": "assistant",
            # "content": "#症状#\n(1) 发烧，体温时高时低，最高达到39度\n(2) 咳嗽，有痰\n(3) 头痛\n(4) 感到冷\n(5) 晕眩\n(6) 全身乏力\n(7) 食欲不振\n(8) 睡眠不好\n\n#询问病人#\n无\n\n#辅助检查#\n(1) 血常规：\n   - 白细胞计数：10.02×10^9/L（升高）\n   - 血小板计数：366×10^9/L（升高）\n   - 红细胞计数：4.98×10^12/L\n   - 血红蛋白：134g/L\n(2) 痰液培养无异常\n(3) 胸部X光：心肺膈未见异常\n\n#询问检查员#\n无"
            # },
            {"role": "user", "content": "{}".format(symptom_and_examination_by_diff_doctors)},
        ]
        responese = self.engine.get_response(messages)
        structure_result = self.parse_symptom_and_examination(responese)
        if structure_result.get("query_to_patient") is None and \
                structure_result.get("query_to_reporter") is None:
            return structure_result.get("symptom_and_examination")
        ## host asks patient and reporter to edit the symptom and examination 
        # if some misalignments exist among different doctos
        if structure_result.get("query_to_patient") is not None:
            # role, content, save_to_memory=True
            structure_result["patient_response"] = patient.speak(
                role="医生", content=structure_result.get("query_to_patient"), save_to_memory=False)
        if structure_result.get("query_to_reporter") is not None:
            structure_result["reporter_response"] = reporter.speak(
                patient.medical_records, structure_result.get("query_to_reporter"), save_to_memory=False)
        # edit the symptom and examination accoring to the response from patient and reporter
        symptom_and_examination = self.edit_symptom_and_examination(structure_result)
        return symptom_and_examination
    
    def parse_symptom_and_examination(self, response):
        values = {}
        response = response.strip() + '\n\n'
        for key in ["症状", "辅助检查", "询问病人", "询问检查员"]:
            value = re.findall(r"\#{}\#(.*?)\n\n".format(key), response, re.S)
            if len(value) >= 1:
                value = value[0]
                value = re.sub(r"\#{}\#".format(key), '', value)
                value = re.sub(r"\#", '', value)
                value = value.strip()
                values[key] = value
            else:
                if key in ["症状", "辅助检查"]:
                    raise Exception("{}".format(response))

        symptom_and_examination = "##症状##\n{}\n\n##辅助检查##\n{}".format(
            values.get("症状"), values.get("辅助检查"))        
        query_to_patient = values.get("询问病人")
        query_to_reporter = values.get("询问检查员")

        if query_to_patient is None or len(query_to_patient) < 5:
            query_to_patient = None
        else: query_to_patient = query_to_patient.strip()

        if query_to_reporter is None or len(query_to_reporter) < 5:
            query_to_reporter = None
        else: query_to_reporter = query_to_reporter.strip()

        structure_result = {
            "symptom_and_examination": symptom_and_examination,
            "query_to_patient": query_to_patient,
            "query_to_reporter": query_to_reporter
        }
        return structure_result

    def edit_symptom_and_examination(self, structure_result):
        # build system message for different situations
        if structure_result.get("query_to_patient") is not None and structure_result.get("query_to_doctor") is not None:
            system_message = "你是一个资深的主任医生。\n" + \
                "你现在需要根据##询问病人##中的#问题#与#回答#，来修正病人##症状##中的歧义与错误。" + \
                "然后根据##询问检查员##中的#问题#与#回答#，来修正病人##辅助检查##中的歧义与错误。\n\n" + \
                "请你按照下面的格式来进行输出。\n#症状#\n(1) xx\n(2) xx\n\n#辅助检查#\n(1) xx\n(2) xx\n"
        elif structure_result.get("query_to_patient") is not None:
            system_message = "你是一个资深的主任医生。\n" + \
                "你现在需要根据##询问病人##中的#问题#与#回答#，来修正病人##症状##中的歧义与错误。\n\n" + \
                "请你按照下面的格式来进行输出。\n#症状#\n(1) xx\n(2) xx\n\n#辅助检查#\n(1) xx\n(2) xx\n"
        elif structure_result.get("query_to_reporter") is not None:
            system_message = "你是一个资深的主任医生。\n" + \
                "你现在需要根据##询问检查员##中的#问题#与#回答#，来修正病人##辅助检查##中的歧义与错误。\n\n" + \
                "请你按照下面的格式来进行输出。\n#症状#\n(1) xx\n(2) xx\n\n#辅助检查#\n(1) xx\n(2) xx\n"
        # build content for user in different situations
        content = "{}\n\n".format(structure_result.get("symptom_and_examination").strip())
        if structure_result.get("query_to_patient") is not None:
            content += "##询问病人##\n#问题#\n{}\n#回答#\n{}\n\n".format(
                structure_result.get("query_to_patient"), structure_result["patient_response"])
        if structure_result.get("query_to_reporter") is not None:
            content += "##询问检查员##\n#问题#\n{}\n#回答#\n{}".format(
                structure_result.get("query_to_repoter"), structure_result["reporter_response"])
        # run engine
        messages = [{"role": "system", "content": system_message},
            {"role": "user", "content": content}]
        symptom_and_examination = self.engine.get_response(messages)
        return symptom_and_examination
