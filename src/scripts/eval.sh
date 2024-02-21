# OpenAI
export OPENAI_API_KEY=""
export OPENAI_API_BASE=""

cd evaluate

python eval.py \
    --model_name gpt-4 \
    --openai_api_key $OPENAI_API_KEY \
    --openai_api_base $OPENAI_API_BASE \
    --evaluation_platform dialog \
    --eval_save_filepath ../outputs/evaluation/evaluation_iiyi_gpt4_5part.jsonl \
    --reference_diagnosis_filepath ../data/patients.json \
    --doctor_names GPT-4

python eval_show.py \
    --interactive_evaluation_result_path ../outputs/evaluation/evaluation_iiyi_gpt4_5part.jsonl \
    --onestep_evaluation_result_path ../outputs/evaluation/evaluation_iiyi_gpt4_onestep.jsonl

cd ..