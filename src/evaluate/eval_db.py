import argparse
import json
import os
import re
from tqdm import tqdm
import time
import xlrd
from fuzzywuzzy import process
import openai
from openai import OpenAI
import random
from collections import defaultdict
from prettytable import PrettyTable
import concurrent
import jsonlines


class DBEvaluator:
    def __init__(self, args):
        self.args = args
        self.max_workers = args.max_workers

        openai_api_key = getattr(args, "openai_api_key", None)
        openai_api_key = openai_api_key if openai_api_key is not None else os.environ.get('OPENAI_API_KEY')
        assert openai_api_key is not None
        openai_api_base = getattr(args, "openai_api_base", None)
        openai_api_base = openai_api_base if openai_api_base is not None else os.environ.get('OPENAI_API_BASE')

        self.temperature = 0.0
        self.max_tokens = 2048
        self.model_name = args.model_name
        if openai_api_base is not None:
            self.client = OpenAI(
                api_key=openai_api_key,
                base_url=openai_api_base
            )
        else:
            self.client = OpenAI(
                api_key=openai_api_key,
            )

        self.doctors = [
            ("GPT-3.5-Turbo", "../outputs/dialog_history_iiyi/dialog_history_gpt3.jsonl"), 
            ("GPT-4", "../outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl"), 
            ("WenXin4", "../outputs/dialog_history_iiyi/dialog_history_wenxin.jsonl"), 
            ("QwenMax", "../outputs/dialog_history_iiyi/dialog_history_qwen_max.jsonl"),
            ("2_Agent_GPT3_GPT4_Critique", "../outputs/collaboration_history_iiyi/doctors_2_agent_gpt3_gpt4_parallel_with_critique_discussion_history.jsonl"),
            ("GPT-4-OneStep", "../outputs/onestep_iiyi/onestep_gpt4_iiyi_patients.jsonl"),
        ]

        # self.doctors = args.doctors
        self.eval_save_filepath = args.eval_save_filepath
        self.reference_diagnosis_filepath = args.reference_diagnosis_filepath
        self.top_n = args.top_n

        self.database = args.database
        xls = xlrd.open_workbook(self.database)
        sheet = xls.sheet_by_index(0)
        disease_ids = sheet.col_values(colx = 0, start_rowx = 1)
        disease_names = sheet.col_values(colx = 1, start_rowx = 1)
        self.disease = {}
        for disease_id, disease_name in zip(disease_ids, disease_names): 
            self.disease[disease_name] = disease_id
        
        self.reference_diagnosis = self.load_reference_diagnosis(self.reference_diagnosis_filepath)
        # self.patient_ids = list(self.reference_diagnosis.keys())
        self.patient_ids = {patient_id: 1 for patient_id in json.load(open("../data/iiyi/keep_patient_ids_v101.json", "r"))}

        self.doctor_name_to_diagnosis = {}
        for doctor_name, doctor_diagnosis_filepath in self.doctors:
            self.doctor_name_to_diagnosis[doctor_name] = self.load_doctor_diagnosis(doctor_diagnosis_filepath)
        self.doctor_names = list(self.doctor_name_to_diagnosis.keys())

    def parse_diagnosis(self):

        processed_doctor_name_w_patient_id = {}
        if os.path.exists(self.eval_save_filepath):
            with open(self.eval_save_filepath, "r") as inputfile:
                for line in inputfile:
                    line = json.loads(line)
                    doctor_name, patient_id = line["doctor_name"], line["patient_id"]
                    processed_doctor_name_w_patient_id[(doctor_name, patient_id)] = 1
            inputfile.close()

        total_data = []
        for doctor_name in self.doctor_names:
            patient_id_to_doctor_diagnosis = self.doctor_name_to_diagnosis.get(doctor_name)
            print("parse: ", doctor_name, len(patient_id_to_doctor_diagnosis))
            for patient_id in tqdm(self.patient_ids):
                if processed_doctor_name_w_patient_id.get((doctor_name, patient_id)) is not None:
                    continue
                
                reference_diagnosis = self.reference_diagnosis.get(patient_id)
                doctor_diagnosis = patient_id_to_doctor_diagnosis.get(patient_id)
                if doctor_diagnosis is None or '#诊断结果#' not in doctor_diagnosis['diagnosis'] or '#诊断依据#' not in doctor_diagnosis['diagnosis']:
                    continue
            
                data = {
                    "doctor_name": doctor_name,
                    "patient_id": patient_id,
                    "reference_diagnosis": reference_diagnosis,
                    "doctor_diagnosis": doctor_diagnosis
                }
                total_data.append(data)
        
        if self.args.parallel:
            print("Parallel Parse Start")
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 使用 map 来简化提交任务和获取结果的过程
                futures = [executor.submit(self.execute_match, data) for data in total_data]
                for _ in tqdm(concurrent.futures.as_completed(futures), total=len(total_data)):
                    pass
        else:
            for data in tqdm(total_data):
                self.execute_match(data)

    def execute_match(self, data):
        reference_diagnosis = data["reference_diagnosis"]
        doctor_diagnosis = data["doctor_diagnosis"]

        reference_diagnosis = reference_diagnosis['diagnosis'].strip()
        reference_response = self.get_response(self.get_messages(reference_diagnosis)).split('##')
        reference_diagnosis_match = [process.extract(r, self.disease.keys(), limit=self.top_n) for r in reference_response]
        reference_diagnosis_match = [[(r[0], self.disease[r[0]], r[1]) for r in rr] for rr in reference_diagnosis_match]

        doctor_diagnosis = doctor_diagnosis['diagnosis'][doctor_diagnosis['diagnosis'].index('诊断结果')+4:doctor_diagnosis['diagnosis'].index('诊断依据')].strip("# \n")
        doctor_response = self.get_response(self.get_messages(doctor_diagnosis)).split('##')
        doctor_diagnosis_match = [process.extract(r, self.disease.keys(), limit=self.top_n) for r in doctor_response]
        doctor_diagnosis_match = [[(d[0], self.disease[d[0]], d[1]) for d in dd] for dd in doctor_diagnosis_match]
        
        result = {
            "doctor_name": data["doctor_name"],
            "patient_id": data["patient_id"],
            "reference_diagnosis": reference_diagnosis,
            "reference_response": reference_response,
            "reference_diagnosis_match": reference_diagnosis_match,
            "doctor_diagnosis": doctor_diagnosis,
            "doctor_response": doctor_response,
            "doctor_diagnosis_match": doctor_diagnosis_match
        }
        with open(self.eval_save_filepath, 'a') as outfile:
            outfile.write(json.dumps(result, ensure_ascii=False)+'\n')
        outfile.close()

    def evaluate(self):

        # eval
        def set_match(pred, refs, matched):
            pred_set = [p[0] for p in pred]
            return_idx = None
            for idx, ref in enumerate(refs):
                ref_set = [r[0] for r in ref]
                for p in pred_set:
                    for r in ref_set:
                        if p == r and matched[idx] == 0:
                            return_idx = idx
            return return_idx
                
        results = defaultdict(list)
        with open(self.eval_save_filepath) as inputfile:
            for line in inputfile:
                line = json.loads(line)
                results[line['doctor_name']].append(line)
        inputfile.close()
        
        table = PrettyTable(['模型','评测病人数量','平均预测疾病数量','Set Recall','Set Precision','Set F1'])
        for model in results.keys():
            # Like Span-level F1
            patient_num = 0
            disease_num = 0

            true_positive = 0.00001 # smooth
            false_positive = 0
            false_negitative = 0

            for data in results[model]:
                if data["patient_id"] not in self.patient_ids:
                    continue
                patient_num += 1
                refs = [[n for n in m if n[2] >= args.threshold] for m in data['reference_diagnosis_match']]
                preds = [[n for n in m if n[2] >= args.threshold] for m in data['doctor_diagnosis_match']]
                set_matched = [0] * len(refs)
                for pred in preds:
                    set_match_idx = set_match(pred, refs, set_matched)
                    if set_match_idx is None: false_positive += 1 # do not match
                    elif set_matched[set_match_idx] == 1: false_positive += 1 # can not match more than one times
                    else: set_matched[set_match_idx] = 1 # first match

                disease_num += len(preds)
                true_positive += sum(set_matched)
                false_negitative += (len(refs) - sum(set_matched))

            set_recall = true_positive / (true_positive + false_negitative)
            set_precision = true_positive / (true_positive + false_positive)
            set_f1 = set_precision * set_recall * 2 / (set_recall + set_precision)

            table.add_row([
                model, patient_num, 
                "{:.2f}".format(disease_num/patient_num),
                "{:.2f}".format(set_recall*100), 
                "{:.2f}".format(set_precision*100), 
                "{:.2f}".format(set_f1*100),
            ])
                
        print(table)

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
                    "diagnosis": diagnosis,
                    "basis": basis,
                    "treatment": treatment
                }
        return patient_id_to_reference_diagnosis
        
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
                    raise Exception("Exception: {}".format(list(obj.keys())))
        reader.close()
        return patient_id_to_doctor_diagnosis
    
    def get_messages(self, message):
        # with 3-shot examples
        messages=[
            {
                "role": "system",
                "content": "你是资深的医学专家。擅长把口语化的诊断转化为标准化的疾病术语（参考国际疾病分类ICD-10标准），并按照如下格式输出：疾病名##疾病名##疾病名"
            },
            {
                "role": "user",
                "content": "早孕哺乳期核对孕周疤痕子宫两次"
            },
            {
                "role": "assistant",
                "content": "瘢痕子宫##妊娠状态"
            },
            {
                "role": "user",
                "content": "颈椎病；胸背肌筋膜炎"
            },
            {
                "role": "assistant",
                "content": "颈椎病##筋膜炎"
            },
            {
                "role": "user",
                "content": "根据您的症状和检查结果，初步诊断为缺铁缺锌铅较高腹部淋巴肿大"
            },
            {
                "role": "assistant",
                "content": "铁缺乏##锌缺乏##铅中毒##淋巴结肿大"
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--openai_api_key", type=str, default=None, help="openai api key")
    parser.add_argument("--openai_api_base", type=str, default=None, help="openai api base")
    parser.add_argument("--model_name", type=str, default="gpt-3.5-turbo", help="model name of openai to act as reference for evaluation")
    parser.add_argument("--database", type=str, default="./国际疾病分类ICD-10北京临床版v601.xls", help="database")
    parser.add_argument("--eval_save_filepath", type=str, default="../outputs/evaluation/evaluation_db_iiyi.json", help="save path for evaluation results")
    parser.add_argument("--reference_diagnosis_filepath", type=str, default="../data/patients.json", help="reference diagnosis filepath") 
    parser.add_argument("--doctors", type=str, nargs="+", default=[], help="doctor results for evaluation")
    parser.add_argument("--top_n", type=int, default=10, help="search top n")
    parser.add_argument("--threshold", type=int, default=50, help="search threshold")
    parser.add_argument("--max_workers", type=int, default=5, help="max worker for parallel evaluation")
    parser.add_argument("--parallel", default=False, action="store_true", help="parallel diagnosis")
    parser.add_argument("--no_parse", default=False, action="store_true", help="Parse the diagnosis")

    args = parser.parse_args()
    return args
   
   
if __name__ == "__main__":
    args = get_args()
    evaluator = DBEvaluator(args)
    if not args.no_parse:
        evaluator.parse_diagnosis()
    evaluator.evaluate()