import os
import json
import asyncio

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
from copilot_gpt_context import CopilotGPTContext
from copilotsetting import AOAISetting, CopilotSetting
from jinja2 import Template



# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def copilot_flow(data: str,
                 aoai_connection: AzureOpenAIConnection,
                 aoai_deployment: str,
                 reason: str,
                 copilot_instruction_template: str,
                 rewrite_user_input_template: str,
                 refine_python_code_template: str,
                 find_python_package_template: str,
                 summarize_flow_name_template: str,
                 understand_flow_template: str,
                 json_string_fixer_template: str,
                 yaml_string_fixer_template: str,
                 function_call_instruction_template: str):
     aoai_setting = AOAISetting(aoai_connection.aoai_key, aoai_connection.aoai_api_base, aoai_deployment)
     copilot_setting = CopilotSetting(True, aoai_setting, None, True, None)
     copilot_gpt_context = CopilotGPTContext(Template(copilot_instruction_template),
                                             Template(rewrite_user_input_template),
                                             Template(refine_python_code_template),
                                             Template(find_python_package_template),
                                             Template(summarize_flow_name_template),
                                             Template(understand_flow_template),
                                             Template(json_string_fixer_template),
                                             Template(yaml_string_fixer_template),
                                             Template(function_call_instruction_template),
                                             copilot_setting)
     copilot_gpt_context.check_env()
     result = None
     json_body = json.loads(data)
     loop = asyncio.get_event_loop()

     if reason == 'ask_openai_async':
        result = loop.run_until_complete(copilot_gpt_context._ask_openai_async(json_body['messages'], json_body['functions'], json_body['function_call']))
     elif reason == 'get_understand_flow_system_message':
        result = copilot_gpt_context.understand_flow_template.render(flow_directory=json_body['flow_folder'], flow_yaml_path=os.path.join(json_body['flow_folder'], 'flow.dag.yaml'), flow_yaml=json_body['flow_yaml'], flow_description=json_body['flow_description'])
     elif reason == 'get_system_instruction':
        result = copilot_gpt_context.system_instruction
     elif reason == 'get_function_call_instruction':
        result = copilot_gpt_context.function_call_instruction_template.render(functions=','.join([f['name'] for f in json_body['function_calls']]))
     elif reason == 'rewrite_user_input':
        result = loop.run_until_complete(copilot_gpt_context._rewrite_user_input(json_body['content'], json_body['messages']))
     elif reason == 'summarize_flow_name':
        result = loop.run_until_complete(copilot_gpt_context._summarize_flow_name(json_body['explaination']))
     elif reason == 'safe_load_flow_yaml':
        result = loop.run_until_complete(copilot_gpt_context._safe_load_flow_yaml(json_body['flow_yaml']))
     elif reason == 'refine_python_code':
        result = loop.run_until_complete(copilot_gpt_context._refine_python_code(json_body['python_code']))
     elif reason == 'find_dependent_python_packages':
        result = loop.run_until_complete(copilot_gpt_context._find_dependent_python_packages(json_body['refined_code']))
     elif reason == 'smart_json_loads':
        result = loop.run_until_complete(copilot_gpt_context._smart_json_loads(json_body['yaml_string']))
     elif reason == 'fix_json_string_and_loads':
        result = loop.run_until_complete(copilot_gpt_context._fix_json_string_and_loads(json_body['json_string'], json_body['error'], json_body['max_retry']))
     elif reason == 'fix_yaml_string_and_loads':
        result = loop.run_until_complete(copilot_gpt_context._fix_yaml_string_and_loads(json_body['yaml_string'], json_body['error'], json_body['max_retry']))
     elif reason == 'smart_yaml_loads':
        result = loop.run_until_complete(copilot_gpt_context._smart_yaml_loads(json_body['yaml_string']))
     else:
        print('Invalid reason! Please provide a valid reason.')
  
     return result