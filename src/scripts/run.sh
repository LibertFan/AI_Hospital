
# GPT-4
echo "GPT-4"
export OPENAI_API_KEY=""
export OPENAI_API_BASE=""
python run.py --patient_database ./data/patients.json \
    --doctor Agent.Doctor.GPT --doctor_openai_model_name gpt-4 \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-3.5-turbo \
    --save_path outputs/dialog_history_iiyi/dialog_history_gpt4_0222.jsonl \
    --max_conversation_turn 10 # --max_workers 8 --parallel

# GPT-3.5-Turbo
# echo "GPT-3.5-Turbo"
export OPENAI_API_KEY=""
export OPENAI_API_BASE=""
python run.py --patient_database ./data/iiyi/patients.json \
    --doctor Agent.Doctor.GPT --doctor_openai_model_name gpt-3.5-turbo \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-3.5-turbo \
    --save_path outputs/dialog_history_iiyi/dialog_history_gpt3_0222.jsonl \
    --max_conversation_turn 10 # --max_workers 8 --parallel

# WenXin
echo "WenXin"
export WENXIN_API_KEY=""	
export WENXIN_SECRET_KEY=""
python run.py --patient_database ./data/patients.json \
    --doctor Agent.Doctor.WenXin \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-3.5-turbo \
    --save_path outputs/dialog_history_iiyi/dialog_history_wenxin_0222.jsonl \
    --max_conversation_turn 10 # --max_workers 2  --parallel

# Qwen: qwen-max
echo Qwen: qwen-max
export DASHSCOPE_API_KEY=""
python run.py --patient_database ./data/patients.json \
    --doctor Agent.Doctor.Qwen --doctor_qwen_model_name qwen-max \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-3.5-turbo \
    --save_path outputs/dialog_history_iiyi/dialog_history_qwen_max.jsonl \
    --max_conversation_turn 10 # --max_workers 2 --parallel 

# BaiChuan: baichuan2-13b-chat-v1 (13B)
export DASHSCOPE_API_KEY=""
python run.py --patient_database ./data/patients.json \
    --doctor Agent.Doctor.Qwen --doctor_qwen_model_name baichuan2-13b-chat-v1 \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-3.5-turbo \
    --save_path outputs/dialog_history_iiyi/dialog_history_baichuan2_13b_chat_v1_0222.jsonl \
    --max_conversation_turn 10 # --max_workers 4 --parallel 

# HuatuoGPT: 34B
export HUATUOGPT_MODEL=""
python run.py --patient_database ./data/patients.json \
    --doctor Agent.Doctor.HuatuoGPT --doctor_huatuogpt_model_name_or_path ${HUATUOGPT_MODEL} \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo  \
    --reporter Agent.Reporter.GPTV2 --reporter_openai_model_name gpt-3.5-turbo \
    --save_path outputs/dialog_history_iiyi/dialog_history_huatuogpt2_34b_0222.jsonl \
    --max_conversation_turn 10 --ff_print 