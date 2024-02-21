import argparse
import os
import json
from typing import List
import jsonlines
from tqdm import tqdm
import time
import random
import concurrent
import copy
from utils.register import registry, register_class


@register_class(alias="Scenario.CollaborativeConsultation")
class CollaborativeConsultation:
    def __init__(self, args):
        patient_database = json.load(open(args.patient_database))
        self.args = args

        # Load Different Doctor Agents
        int_to_char = {i: chr(i+65) for i in range(26)}
        self.doctors = []
        for i, doctor_args in enumerate(args.doctors_args[:args.number_of_doctors]):
            doctor = registry.get_class(doctor_args.doctor_name)(
                doctor_args,
                name=int_to_char[i]
            )
            doctor.load_diagnosis(
                diagnosis_filepath=doctor_args.diagnosis_filepath, 
                evaluation_filepath=doctor_args.evaluation_filepath,
                doctor_key=doctor_args.doctor_key
            )
            self.doctors.append(doctor)

        # Load Different Patient Agents
        self.patients = []
        for patient_profile in patient_database:
            patient = registry.get_class(args.patient)(
                args,
                patient_profile=patient_profile["profile"],
                medical_records=patient_profile["medical_record"],
                patient_id=patient_profile["id"],
            )
            self.patients.append(patient)
    
        self.reporter = registry.get_class(args.reporter)(args)
        self.host = registry.get_class(args.host)(args)

        self.discussion_mode = args.discussion_mode
        self.max_discussion_turn = args.max_discussion_turn
        self.max_conversation_turn = args.max_conversation_turn
        self.delay_between_tasks = args.delay_between_tasks
        self.max_workers = args.max_workers
        self.save_path = args.save_path
        self.ff_print = args.ff_print
        self.start_time = time.strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def add_parser_args(parser: argparse.ArgumentParser):
        parser.add_argument("--patient_database", default="patients.json", type=str)
        parser.add_argument("--doctor_database", default="doctor.json", type=str)
        parser.add_argument("--number_of_doctors", default=2, type=int, help="number of doctors in the consultation collaboration")
        parser.add_argument("--max_discussion_turn", default=4, type=int, help="max discussion turn between doctors")
        parser.add_argument("--max_conversation_turn", default=10, type=int, help="max conversation turn between doctor and patient")
        parser.add_argument("--max_workers", default=4, type=int, help="max workers for parallel diagnosis")
        parser.add_argument("--delay_between_tasks", default=10, type=int, help="delay between tasks")
        parser.add_argument("--save_path", default="dialog_history.jsonl", help="save path for dialog history")

        parser.add_argument("--patient", default="Agent.Patient.GPT", help="registry name of patient agent")
        parser.add_argument("--reporter", default="Agent.Reporter.GPT", help="registry name of reporter agent")
        parser.add_argument("--host", default="Agent.Host.GPT", help="registry name of host agent")
        parser.add_argument("--ff_print", default=False, action="store_true", help="print dialog history")
        parser.add_argument("--parallel", default=False, action="store_true", help="parallel diagnosis")
        parser.add_argument("--discussion_mode", default="Parallel", choices=["Parallel", "Parallel_with_Critique"], help="discussion mode")


    def run(self):
        self.remove_processed_patients()
        for patient in tqdm(self.patients):
            self._run(patient)
    
    def parallel_run(self):
        self.remove_processed_patients()
        st = time.time()
        print("Parallel Run Start")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 使用 map 来简化提交任务和获取结果的过程
            # executor.map(self._diagnosis, self.patients)
            futures = [executor.submit(self._run, patient) for patient in self.patients]
            # 使用 tqdm 来创建一个进度条
            for _ in tqdm(concurrent.futures.as_completed(futures), total=len(self.patients)):
                pass
        print("duration: ", time.time() - st)
    
    def _run(self, patient):
        # host summarizes the symptom and examination from different doctors
        # and asks patient and reporter to verify and correct the symptom and examination
        symptom_and_examination = self.host.summarize_symptom_and_examination(
            self.doctors, patient, self.reporter)
        if self.ff_print:
            print("symptom_and_examination: {}".format(symptom_and_examination))
        # revise the diagnosis
        diagnosis_in_discussion = []
        diagnosis_in_turn = []
        for i, doctor in enumerate(self.doctors):
            doctor.revise_diagnosis_by_symptom_and_examination(
                patient, symptom_and_examination)
            diagnosis_in_turn.append({
                "doctor_id": i,
                "doctor_engine_name": doctor.engine.model_name,
                "diagnosis": doctor.get_diagnosis_by_patient_id(patient.id)
            })
            if self.ff_print:
                print(doctor.engine.model_name, doctor.get_diagnosis_by_patient_id(patient.id, "诊断结果"))

        if self.ff_print:
            print("-"*100)
        # doctor revise the diagnosis based on the discussion with other doctors
        host_measurement = self.host.measure_agreement(self.doctors, patient, discussion_mode=self.discussion_mode)
        diagnosis_in_discussion.append({
            "turn": 0,
            "diagnosis_in_turn": diagnosis_in_turn,
            "host_critique": host_measurement
        })
        if host_measurement != '#结束#':
            for k in range(self.max_discussion_turn):
                if self.ff_print:
                    print(k, "host", host_measurement)
                diagnosis_in_turn = []
                for i, doctor in enumerate(self.doctors):
                    left_doctors = self.doctors[:i] + self.doctors[i+1:]
                    doctor.revise_diagnosis_by_others(
                        patient, left_doctors, host_measurement, discussion_mode=self.discussion_mode)
                    diagnosis_in_turn.append({
                        "doctor_id": i,
                        "doctor_engine_name": doctor.engine.model_name,
                        "diagnosis": doctor.get_diagnosis_by_patient_id(patient.id)
                    })
                    if self.ff_print:
                        print(k, i, doctor.name, doctor.get_diagnosis_by_patient_id(patient.id, "诊断结果"))
                host_measurement = self.host.measure_agreement(self.doctors, patient)
                diagnosis_in_discussion.append({
                    "turn": k+1,
                    "diagnosis_in_turn": diagnosis_in_turn,
                    "host_critique": host_measurement
                })
                if self.ff_print:
                    print("host: {}".format(host_measurement))
                    print("-"*100)
                if host_measurement == '#结束#':
                    break
        else:
            k = -1
        
        final_diagnosis = self.host.summarize_diagnosis(self.doctors, patient)
        if self.ff_print:
            print("host final diagnosis: {}".format(final_diagnosis))
            print("="*100)
        diagnosis_info = {
            "patient_id": patient.id, "final_turn": k+1, "diagnosis": final_diagnosis,
            "symptom_and_examination": symptom_and_examination,
            "doctor_database": self.args.doctor_database, "doctor_ids": [doctor.id for doctor in self.doctors], 
            "doctor_engine_names": [doctor.engine.model_name for doctor in self.doctors],
            "host": self.args.host, "host_engine_name": self.host.engine.model_name,
            "patient": self.args.patient, "patient_engine_name": patient.engine.model_name,
            "reporter": self.args.reporter, "reporter_engine_name": self.reporter.engine.model_name,
            "time": self.start_time,
        }
        self.save_info(diagnosis_info)

    def remove_processed_patients(self):
        processed_patient_ids = {}
        if os.path.exists(self.save_path):
            with jsonlines.open(self.save_path, "r") as f:
                for obj in f:
                    processed_patient_ids[obj["patient_id"]] = 1
            f.close()

        patient_num = len(self.patients)
        for i, patient in enumerate(self.patients[::-1]):
            if processed_patient_ids.get(patient.id) is not None:
                self.patients.pop((patient_num-(i+1)))
        
        random.shuffle(self.patients)
        self.patients = self.patients
        print("To-be-diagnosed Patient Number: ", len(self.patients))
        
    def save_info(self, dialog_info):
        with jsonlines.open(self.save_path, "a") as f:
            f.write(dialog_info)
        f.close()
