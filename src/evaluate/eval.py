import jsonlines
import json
import os
import openai
from openai import OpenAI
import re
from tqdm import tqdm
import time
import concurrent
import random


class Evaluator:
    def __init__(self, args):
        openai_api_key = getattr(args, "openai_api_key", None)
        openai_api_key = openai_api_key if openai_api_key is not None else os.environ.get('OPENAI_API_KEY')
        assert openai_api_key is not None
        openai_api_base = getattr(args, "openai_api_base", None)
        openai_api_base = openai_api_base if openai_api_base is not None else os.environ.get('OPENAI_API_BASE')

        self.system_message = \
            "你是资深的医学专家。" + \
            "请你根据专家诊疗结果中的现病史、辅助检查、诊断结果、诊断依据和治疗方案，来判断实习医生诊疗结果的质量。\n\n" + \
            "请参考下面的细则进行评价。\n" + \
                "1. 病人症状的掌握情况\n(A) 全面掌握\n(B) 相当部分掌握\n(C) 小部分掌握\n(D) 绝大部分不掌握\n" + \
                "2. 医学检查项目的完整性\n(A) 非常完整\n(B) 相当部分完整\n(C) 小部分完整\n(D) 绝大部分不完整\n" + \
                "3. 诊断结果的一致性\n(A) 完全一致，诊断正确\n(B) 相当部分一致，诊断基本正确\n(C) 小部分一致，诊断存在错误\n(D) 完全不一致，诊断完全错误\n" + \
                "4. 诊断依据的一致性\n(A) 完全一致\n(B) 相当部分一致\n(C) 小部分一致\n(D) 完全不一致\n" + \
                "5. 治疗方案的一致性\n(A) 完全一致\n(B) 相当部分一致\n(C) 小部分一致\n(D) 完全不一致\n\n" + \
            "通过下面的方式来呈现结果\n" + \
                "# 症状\n## 分析\n<根据专家记录的病人病史，分析实习医生对病人病情的掌握情况>\n## 选项<根据症状分析做出选择>\n" + \
                "# 医学检查项目\n## 分析\n<基于专家所做的医学检查项目，全面分析实习医生所做的医学检查项目的完整性>\n## 选项<根据分析得到的完整性做出选择>\n" + \
                "# 诊断结果\n## 分析\n<基于专家做出的诊断结果，结合你的医学常识，分析实习医生诊断结果与专家的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n" + \
                "# 诊断依据\n## 分析\n<对比专家的诊断依据，分析实习医生的治疗方案与其的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n" + \
                "# 治疗方案\n## 分析\n<对比专家的治疗方案，分析实习医生的治疗方案与其的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n\n" + \
            "(1) 请侧重医学答案的事实内容，不需关注风格、语法、标点和无关医学的内容。\n" + \
            "(2) 请你充分利用医学知识，分析并判断每个点的重要性，再做评价。\n" + \
            "(3) 注意诊断结果、诊断依据和治疗方案三者之间的承接关系。例如，如果诊断错误，那么后面两部分与专家的一致性就必然很低。" 
                
        self.model_name = args.model_name # "gpt-4-1106-preview"
        # self.model_name = "gpt-3.5-turbo"
        self.temperature = 0.0
        self.max_tokens = 4096
        self.doctor_names = args.doctor_names
        self.max_workers = args.max_workers # 5
        self.delay_between_tasks = args.delay_between_tasks
        self.eval_save_filepath = args.eval_save_filepath
        self.reference_diagnosis_filepath = args.reference_diagnosis_filepath

        if openai_api_base is not None:
            self.client = OpenAI(
                api_key=openai_api_key,
                base_url=openai_api_base
            )
        else:
            self.client = OpenAI(
                api_key=openai_api_key,
            )
    
    def load_reference_diagnosis(self, reference_diagnosis_filepath):
        
        with open(reference_diagnosis_filepath, 'r') as f:
            data = json.load(f)
        f.close()
        patient_id_to_reference_diagnosis = {}
        for item in data:
            medical_record = item["medical_record"]
            diagnosis = medical_record.get("诊断结果") if medical_record.get("诊断结果") is not None else medical_record.get("初步诊断")
            basis = medical_record.get("诊断依据")
            treatment = medical_record.get("诊治经过")
            patient_id_to_reference_diagnosis[item["id"]] = {
                    "patient_id": item["id"],
                    "symptom": medical_record.get("现病史"),
                    "medical_test": medical_record.get("辅助检查"),
                    "diagnosis": diagnosis,
                    "basis": basis,
                    "treatment": treatment
                }
        return patient_id_to_reference_diagnosis

    def build_onestep_platform(self):
        self.reference_diagnosis = self.load_reference_diagnosis(self.reference_diagnosis_filepath)
        self.patient_ids = list(self.reference_diagnosis.keys())

        self.doctor_name_to_diagnosis = {}
        for doctor_name, doctor_diagnosis_filepath in [
            # ("GPT-4-1106-Preview", "../outputs/onestep_gpt4_1106_preview.jsonl"),
            ("GPT-4", "../outputs/onestep_iiyi/onestep_gpt4_iiyi_patients.jsonl"),
                ]:
            self.doctor_name_to_diagnosis[doctor_name] = self.load_doctor_onestep_diagnosis(doctor_diagnosis_filepath)

    def load_doctor_onestep_diagnosis(self, doctor_diagnosis_filepath):
        patient_id_to_doctor_diagnosis = {}
        with jsonlines.open(doctor_diagnosis_filepath, "r") as reader:
            for obj in reader:
                patient_id_to_doctor_diagnosis[obj["patient_id"]] = {
                    "patient_id": obj["patient_id"],
                    "diagnosis": obj["diagnosis"],
                }
        reader.close()
        return patient_id_to_doctor_diagnosis

    def build_dialog_platform(self):
        self.reference_diagnosis = self.load_reference_diagnosis(self.reference_diagnosis_filepath)
        self.patient_ids = list(self.reference_diagnosis.keys())
        print("[build_dialog_platform][patient_ids: {}]".format(len(self.patient_ids)))

        self.doctor_name_to_diagnosis = {}
        for doctor_name, doctor_diagnosis_filepath in [
                ("GPT-3.5-Turbo", "../outputs/dialog_history_iiyi/dialog_history_gpt3.jsonl"),
                ("WenXin4", "../outputs/dialog_history_iiyi/dialog_history_wenxin.jsonl"),
                ("QwenMax", "../outputs/dialog_history_iiyi/dialog_history_qwen_max.jsonl"),
                ("GPT-4", "../outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl"),
            ]:
            self.doctor_name_to_diagnosis[doctor_name] = self.load_doctor_diagnosis(doctor_diagnosis_filepath)

    def load_doctor_diagnosis(self, doctor_diagnosis_filepath):
        patient_id_to_doctor_diagnosis = {}

        with jsonlines.open(doctor_diagnosis_filepath, "r") as reader:
            for obj in reader:
                if "dialog_history" in obj:
                    dialog = obj["dialog_history"]
                    turn, role, content = dialog[-1]["turn"], dialog[-1]["role"], dialog[-1]["content"]
                    assert role == "Doctor"

                    patient_id_to_doctor_diagnosis[obj["patient_id"]] = {
                        "patient_id": obj["patient_id"],
                        "turn": turn,
                        "diagnosis": content,
                    }
                elif "diagnosis" in obj:
                    patient_id_to_doctor_diagnosis[obj["patient_id"]] = {
                        "patient_id": obj["patient_id"],
                        "diagnosis": obj["diagnosis"],
                    }
                else:
                    raise Exception
        reader.close()
        return patient_id_to_doctor_diagnosis

    def build_collaborative_discussion_platform(self):
        self.reference_diagnosis = self.load_reference_diagnosis(self.reference_diagnosis_filepath)
        self.patient_ids = list(self.reference_diagnosis.keys())

        self.doctor_name_to_diagnosis = {}
        for doctor_name, doctor_diagnosis_filepath in [
                ("2_Agent_GPT3_GPT4_Critique", "../outputs/collaboration_history_iiyi/doctors_2_agent_gpt3_gpt4_parallel_with_critique_discussion_history.jsonl"),
            ]:
            self.doctor_name_to_diagnosis[doctor_name] = self.load_collaborative_discussion_diagnosis(doctor_diagnosis_filepath)

    def load_collaborative_discussion_diagnosis(self, doctor_diagnosis_filepath):
        patient_id_to_diagnosis = {}
        with jsonlines.open(doctor_diagnosis_filepath, "r") as reader:
            for obj in reader:
                patient_id_to_diagnosis[obj["patient_id"]] = {
                    "patient_id": obj["patient_id"],
                    "diagnosis": obj["diagnosis"],
                }
        reader.close()
        return patient_id_to_diagnosis

    def parallel_evaluate(self):
        # determine whether the patient has been processed
        doctor_name_to_processed_patient_ids = {}
        if os.path.exists(self.eval_save_filepath):
            with jsonlines.open(self.eval_save_filepath, "r") as fr:
                for obj in fr:
                    doctor_name = obj["doctor_name"]
                    if doctor_name not in doctor_name_to_processed_patient_ids:
                        doctor_name_to_processed_patient_ids[doctor_name] = {}
                    doctor_name_to_processed_patient_ids[doctor_name][obj["patient_id"]] = 1

        evaluate_inputs = []
        for doctor_name in self.doctor_names:
            patient_id_to_doctor_diagnosis = self.doctor_name_to_diagnosis.get(doctor_name)
            for patient_id in tqdm(self.patient_ids):
                if doctor_name_to_processed_patient_ids.get(doctor_name) is not None and doctor_name_to_processed_patient_ids.get(doctor_name).get(patient_id) is not None:
                    continue    
                reference_diagnosis = self.reference_diagnosis.get(patient_id)
                doctor_diagnosis = patient_id_to_doctor_diagnosis.get(patient_id)
                evaluate_args = {
                    "doctor_name": doctor_name,
                    "patient_id": patient_id,
                    "model_name": self.model_name,
                    "reference_diagnosis": reference_diagnosis,
                    "doctor_diagnosis": doctor_diagnosis,
                }
                evaluate_inputs.append(evaluate_args)

        print("Parallel Evaluation Start")
        evaluate_inputs = evaluate_inputs
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 使用 map 来简化提交任务和获取结果的过程
            futures = [executor.submit(self.evaluate_one, single_evaluate_inputs) for single_evaluate_inputs in evaluate_inputs]
            for _ in tqdm(concurrent.futures.as_completed(futures), total=len(evaluate_inputs)):
                pass

    def evaluate(self):
        # determine whether the patient has been processed
        doctor_name_to_processed_patient_ids = {}
        if os.path.exists(self.eval_save_filepath):
            with jsonlines.open(self.eval_save_filepath, "r") as fr:
                for obj in fr:
                    doctor_name = obj["doctor_name"]
                    if doctor_name not in doctor_name_to_processed_patient_ids:
                        doctor_name_to_processed_patient_ids[doctor_name] = {}
                    doctor_name_to_processed_patient_ids[doctor_name][obj["patient_id"]] = 1

        for doctor_name in self.doctor_names:
            patient_id_to_doctor_diagnosis = self.doctor_name_to_diagnosis.get(doctor_name)
            random.shuffle(self.patient_ids)
            for patient_id in tqdm(self.patient_ids):
                if doctor_name_to_processed_patient_ids.get(doctor_name) is not None and doctor_name_to_processed_patient_ids.get(doctor_name).get(patient_id) is not None:
                    continue                        
                # load reference diagnosis
                reference_diagnosis = self.reference_diagnosis.get(patient_id)
                doctor_diagnosis = patient_id_to_doctor_diagnosis.get(patient_id)
                if doctor_diagnosis is None:
                    continue
                result = {
                    "doctor_name": doctor_name,
                    "patient_id": patient_id,
                    "model_name": self.model_name,
                    "reference_diagnosis": reference_diagnosis,
                    "doctor_diagnosis": doctor_diagnosis,
                }
                result = self.evaluate_one(result)

    def evaluate_one(self, evaluate_args):
        reference_diagnosis, doctor_diagnosis = evaluate_args.get("reference_diagnosis"), evaluate_args.get("doctor_diagnosis")

        statement = "# 专家诊疗结果\n" + \
            "## 现病史\n" + \
            "{}\n".format(reference_diagnosis.get("symptom")) + \
            "## 辅助检查\n" + \
            "{}\n".format(reference_diagnosis.get("medical_test")) + \
            "## 诊断结果\n" + \
            "{}\n".format(reference_diagnosis.get("diagnosis")) + \
            "## 诊断依据\n" + \
            "{}\n".format(reference_diagnosis.get("basis")) + \
            "## 治疗方案\n" + \
            "{}\n\n".format(reference_diagnosis.get("treatment")) + \
            "# 实习医生诊疗结果\n" + \
            "{}".format(doctor_diagnosis["diagnosis"])
        
        messages = self.get_messages(statement)
        response = self.get_response(messages)
        struct_result = self.parse_response(response)
        evaluate_args.update(struct_result)
        with jsonlines.open(self.eval_save_filepath, "a") as writer:
            writer.write(evaluate_args)
        writer.close()
        
    @staticmethod
    def parse_response(response):

        characters = ["A", "B", "C", "D"]

        def identify_character(string):
            # Check each character in the list
            for char in characters:
                if char in string:
                    return char

        struct_result = {
            "evaluation_result": response
        }
        response = (response + "\n\n\n\n\n").replace("\n# ", "\n\n\n\n# ").replace("\n## ", "\n\n## ")
        
        sympton_part = re.findall(r"\# 症状\n(.*?)\n\n\n\n", response, re.S)
        if len(sympton_part) > 0:
            sympton_part = sympton_part[0].strip() + "\n\n\n"
            sympton_analyis = re.findall("\#\# {}\n(.*?)\n\n".format("分析"), sympton_part, re.S)
            if len(sympton_analyis) > 0:
                struct_result["sympton_analyis"] = sympton_analyis[0].strip()
            sympton_choice = re.findall("\#\# {}\n(.*?)\n\n".format("选项"), sympton_part, re.S)
            if len(sympton_choice) > 0:
                struct_result["sympton_choice"] = identify_character(sympton_choice[0].strip())
        
        test_part = re.findall(r"\# 医学检查项目\n(.*?)\n\n\n\n", response, re.S)
        if len(test_part) > 0:
            test_part = test_part[0].strip() + "\n\n\n"
            test_analyis = re.findall("\#\# {}\n(.*?)\n\n".format("分析"), test_part, re.S)
            if len(test_analyis) > 0:
                struct_result["test_analyis"] = test_analyis[0].strip()
            test_choice = re.findall("\#\# {}\n(.*?)\n\n".format("选项"), test_part, re.S)
            if len(test_choice) > 0:
                struct_result["test_choice"] = identify_character(test_choice[0].strip())

        diagnosis_part = re.findall(r"\# 诊断结果\n(.*?)\n\n\n\n", response, re.S)
        if len(diagnosis_part) > 0:
            diagnosis_part = diagnosis_part[0].strip() + "\n\n\n"
            diagnosis_analyis = re.findall("\#\# {}\n(.*?)\n\n".format("分析"), diagnosis_part, re.S)
            if len(diagnosis_analyis) > 0:
                struct_result["diagnosis_analyis"] = diagnosis_analyis[0].strip()
            diagnosis_choice = re.findall("\#\# {}\n(.*?)\n\n".format("选项"), diagnosis_part, re.S)
            if len(diagnosis_choice) > 0:
                struct_result["diagnosis_choice"] = identify_character(diagnosis_choice[0].strip())

        basis_part = re.findall("\# {}\n(.*?)\n\n\n\n".format("诊断依据"), response, re.S)
        if len(basis_part) > 0:
            basis_part = basis_part[0].strip() + "\n\n\n"
            basis_analyis = re.findall("\#\# {}\n(.*?)\n\n".format("分析"), basis_part, re.S)
            if len(basis_analyis) > 0:
                struct_result["basis_analyis"] = basis_analyis[0].strip()
            basis_choice = re.findall("\#\# {}\n(.*?)\n\n".format("选项"), basis_part, re.S)
            if len(basis_choice) > 0:
                struct_result["basis_choice"] = identify_character(basis_choice[0].strip())

        treatment_part = re.findall("\# {}\n(.*?)\n\n\n\n".format("治疗方案"), response, re.S)
        if len(treatment_part) > 0:
            treatment_part = treatment_part[0].strip() + "\n\n\n\n"
            treatment_analyis = re.findall("\#\# {}\n(.*?)\n\n".format("分析"), treatment_part, re.S)
            if len(treatment_analyis) > 0:
                struct_result["treatment_analyis"] = treatment_analyis[0].strip()
            treatment_choice = re.findall("\#\# {}\n(.*?)\n\n".format("选项"), treatment_part, re.S)
            if len(treatment_choice) > 0:
                struct_result["treatment_choice"] = identify_character(treatment_choice[0].strip())

        return struct_result

    def get_messages(self, message):
        messages=[
            {
            "role": "system",
            "content": "{}".format(self.system_message)
            },
            {
            "role": "user",
            "content": "{}".format(message) 
            }
        ]
        return messages

    def get_response(self, messages):
        model_name = self.model_name
        i = 0
        while i < 3:
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                break
            except openai.BadRequestError:
                if model_name == "gpt-3.5-turbo":
                    model_name = "gpt-3.5-turbo-16k"
                i += 1
            except openai.RateLimitError:
                time.sleep(10)
            else:
                i += 1
        return response.choices[0].message.content


def get_args():
    # add args for running
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default="gpt-4", help="model name of openai to act as reference for evaluation")
    parser.add_argument("--openai_api_key", type=str, default=None, help="openai api key")
    parser.add_argument("--openai_api_base", type=str, default=None, help="openai api base")
    parser.add_argument("--evaluation_platform", type=str, choices=["onestep", "dialog", "collaborative_discussion"], help="platform for evaluation")
    parser.add_argument("--eval_save_filepath", type=str, default="../outputs/evaluation/evaluation_iiyi_5part.jsonl", help="save path for evaluation results")
    parser.add_argument("--reference_diagnosis_filepath", type=str, default="../data/patients.json", help="reference diagnosis filepath") 
    parser.add_argument("--max_workers", type=int, default=5, help="max worker for parallel evaluation")
    parser.add_argument("--delay_between_tasks", type=int, default=5, help="delay between tasks for parallel evaluation")
    parser.add_argument("--doctor_names", type=str, nargs="+", default=["GPT-4"], help="doctor names for evaluation")
    parser.add_argument("--parallel", default=False, action="store_true", help="parallel diagnosis")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = get_args()
    evaluator = Evaluator(args)

    if args.evaluation_platform == "collaborative_discussion":
        evaluator.build_collaborative_discussion_platform()
    elif args.evaluation_platform == "dialog":
        evaluator.build_dialog_platform()
    else:
        evaluator.build_onestep_platform()

    if not args.parallel:
        evaluator.evaluate()
    else:
        evaluator.parallel_evaluate()

                