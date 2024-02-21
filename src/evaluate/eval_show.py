import jsonlines
import numpy as np
import bootstrapped.bootstrap as bs
import bootstrapped.stats_functions as bs_stats
import json


class EvalDemo:
    def __init__(self, args):        
        if args.onestep_evaluation_result_path is not None:
            self.onestep_doctor_name_to_scores = \
                    self.load_doctor_name_to_scores(
                args.onestep_evaluation_result_path, load_diagnosis=False)
            self.onestep_gpt4_scores = self.onestep_doctor_name_to_scores.get("GPT-4")

        if args.interactive_evaluation_result_path is not None:
            self.interactive_doctor_name_to_scores, \
                self.interactive_doctor_name_to_patient_diagnosis = \
                    self.load_doctor_name_to_scores(
                args.interactive_evaluation_result_path, load_diagnosis=True)
            self.interactive_doctor_names = list(self.interactive_doctor_name_to_scores.keys())

    def load_doctor_name_to_scores(self, evaluation_result_path, load_diagnosis=False):
        char_to_score = {
            "A": 4,
            "B": 3,
            "C": 2,
            "D": 1
        }
        
        doctor_name_to_scores = {}
        if load_diagnosis:
            doctor_name_to_patient_diagnosis = {}

        with jsonlines.open(evaluation_result_path, "r") as reader:
            for obj in reader:
                print(list(obj.keys()))
                doctor_name = obj["doctor_name"]
                # print(obj["patient_id"], type(obj["patient_id"]))
                if isinstance(obj["patient_id"], str):
                    patient_id = eval(obj["patient_id"])
                else:
                    patient_id = obj["patient_id"]
                assert isinstance(patient_id, int)

                sympton_choice, test_choice = obj.get("sympton_choice"), obj.get("test_choice")
                sympton_score, test_score = char_to_score.get(sympton_choice), char_to_score.get(test_choice)
                sympton_score = sympton_score if sympton_score is not None else 1
                test_score = test_score if test_score is not None else 1

                diagnosis_choice, basis_choice, treatment_choice = obj.get("diagnosis_choice"), obj.get("basis_choice"), obj.get("treatment_choice")
                diagnosis_score, basis_score, treatment_score = char_to_score.get(diagnosis_choice), char_to_score.get(basis_choice), char_to_score.get(treatment_choice)
                diagnosis_score = diagnosis_score if diagnosis_score is not None else 1
                basis_score = basis_score if basis_score is not None else 1
                treatment_score = treatment_score if treatment_score is not None else 1
                if doctor_name not in doctor_name_to_scores:
                    doctor_name_to_scores[doctor_name] = [[patient_id, diagnosis_score, basis_score, treatment_score, sympton_score, test_score]]
                    if load_diagnosis:
                        doctor_name_to_patient_diagnosis[doctor_name] = {
                                patient_id: {
                                    "diagnosis": obj["doctor_diagnosis"]["diagnosis"]
                                    }
                            }
                else:
                    doctor_name_to_scores[doctor_name].append([patient_id, diagnosis_score, basis_score, treatment_score, sympton_score, test_score])
                    if load_diagnosis:
                        doctor_name_to_patient_diagnosis[doctor_name][patient_id] = {
                                "diagnosis": obj["doctor_diagnosis"]["diagnosis"]
                            }
        reader.close()

        if load_diagnosis:
            return doctor_name_to_scores, doctor_name_to_patient_diagnosis
        else:
            return doctor_name_to_scores

    def show_onestep_result(self):
        scores = np.array(self.onestep_gpt4_scores)
        filter_scores = []
        for each_scores in scores:
            patient_id = each_scores[0]
            filter_scores.append(each_scores[1:])
        scores = np.array(filter_scores)

        for i in range(5):
            results = bs.bootstrap(
                scores[:,i], stat_func=bs_stats.mean, num_iterations=10000)
            b = results.upper_bound - results.value
            print("mean: {:.3f}, ci: ({:.3f}, {:.3f}), range: {:.3f}".format(
                results.value, results.lower_bound, results.upper_bound, b))
        print("="*60)

    def show_result(self):
        doctor_name_to_scores = self.interactive_doctor_name_to_scores

        idx_to_part = {
            0: "diagnosis",
            1: "basis",
            2: "treatment", 
            3: "sympton",
            4: "test"
        }

        for doctor_name, scores in doctor_name_to_scores.items():
            scores = np.array(scores)
            print('scores: ', scores.shape)
            print("{}: {}".format(doctor_name, len(scores)))
            total_mean_range = []
            for i in [4, 5, 1, 2, 3]:
                results = bs.bootstrap(
                    scores[:,i], stat_func=bs_stats.mean, num_iterations=10000)
                b = results.upper_bound - results.value

                print("{}: mean: {:.3f}, ci: ({:.3f}, {:.3f}), range: {:.3f}".format(
                    idx_to_part.get(i), results.value, results.lower_bound, results.upper_bound, b))
                
                total_mean_range.append([results.value, b])
            print("="*60)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive_evaluation_result_path", type=str, default="../outputs/evaluation/evaluation_iiyi_gpt4_5part.jsonl")
    parser.add_argument("--onestep_evaluation_result_path", type=str, default="../outputs/evaluation/evaluation_iiyi_gpt4_onestep.jsonl")
    args = parser.parse_args()

    eval_demo = EvalDemo(args)
    if args.interactive_evaluation_result_path is not None:
        eval_demo.show_result()
    if args.onestep_evaluation_result_path is not None:
        eval_demo.show_onestep_result()


if __name__ == "__main__":
    main()