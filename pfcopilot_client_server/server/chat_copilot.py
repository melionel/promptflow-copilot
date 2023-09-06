import os
import json
import openai
import re
import yaml
from json import JSONDecodeError
from jinja2 import Template
from promptflow import tool
from promptflow.connections import AzureOpenAIConnection



# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def chat_copilot(data: str,
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
  copilot_context = CopilotContext(aoai_connection,
                                   aoai_deployment,
                                   copilot_instruction_template,
                                   rewrite_user_input_template,
                                   refine_python_code_template,
                                   find_python_package_template,
                                   summarize_flow_name_template,
                                   understand_flow_template,
                                   json_string_fixer_template,
                                   yaml_string_fixer_template,
                                   function_call_instruction_template)

  copilot_context.check_env()
  result = None
  json_body = json.loads(data)

  if reason == 'ask_gpt':
      result = copilot_context._ask_openai_async(json_body['messages'], json_body['functions'], json_body['function_call'])
  elif reason == 'get_understand_flow_system_message':
      result = copilot_context.understand_flow_template.render(flow_directory=json_body['flow_folder'], flow_yaml_path=os.path.join(json_body['flow_folder'], 'flow.dag.yaml'), flow_yaml=json_body['flow_yaml'], flow_description=json_body['flow_description'])
  elif reason == 'get_system_instruction':
      result = copilot_context.system_instruction
  elif reason == 'get_function_call_instruction':
      result = copilot_context.function_call_instruction_template.render(functions=','.join([f['name'] for f in json_body['function_calls']]))
  elif reason == 'rewrite_user_input':
      result = copilot_context._rewrite_user_input(json_body['content'], json_body['messages'])
  elif reason == 'summarize_flow_name':
      result = copilot_context._summarize_flow_name(json_body['explaination'])
  elif reason == 'safe_load_flow_yaml':
      result = copilot_context._safe_load_flow_yaml(json_body['flow_yaml'])
  elif reason == 'refine_python_code':
      result = copilot_context._refine_python_code(json_body['python_code'])
  elif reason == 'find_dependent_python_packages':
      result = copilot_context._find_dependent_python_packages(json_body['refined_code'])
  elif reason == 'smart_json_loads':
      result = copilot_context._smart_json_loads(json_body['yaml_string'])
  else:
      print('Invalid reason! Please provide a valid reason.')
  
  return result


class CopilotContext:
    def __init__(
        self,
        aoai_connection,
        aoai_deployment,
        copilot_instruction_template,
        rewrite_user_input_template,
        refine_python_code_template,
        find_python_package_template,
        summarize_flow_name_template,
        understand_flow_template,
        json_string_fixer_template,
        yaml_string_fixer_template,
        function_call_instruction_template
        ) -> None:
        self.aoai_key = aoai_connection.api_key
        self.aoai_api_base = aoai_connection.api_base
        self.aoai_deployment = aoai_deployment

        self.copilot_instruction_template = Template(copilot_instruction_template)
        self.rewrite_user_input_template = Template(rewrite_user_input_template)
        self.refine_python_code_template = Template(refine_python_code_template)
        self.find_python_package_template = Template(find_python_package_template)
        self.summarize_flow_name_template = Template(summarize_flow_name_template)
        self.understand_flow_template = Template(understand_flow_template)
        self.json_string_fixer_template = Template(json_string_fixer_template)
        self.yaml_string_fixer_template = Template(yaml_string_fixer_template)
        self.function_call_instruction_template = Template(function_call_instruction_template)

        self.system_instruction = self.copilot_instruction_template.render()
        self.messages = []


    def check_env(self):
        if not self.aoai_key or not self.aoai_deployment or not self.aoai_api_base:
            return False, "You configured to use AOAI, but one or more of the following environment variables were not set: AOAI_API_KEY, AOAI_DEPLOYMENT, AOAI_API_BASE"
        else:
            openai.api_key = self.aoai_key
            openai.api_type = "azure"
            openai.api_base = self.aoai_api_base
            openai.api_version = "2023-07-01-preview"
            return True, ""
    
    def _ask_openai_async(self, messages=[], functions=None, function_call=None):
        request_args_dict = self._format_request_dict(messages, functions, function_call)
        response = openai.ChatCompletion.create(**request_args_dict)

        response_ms = response.response_ms
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        print(f'Get response from ChatGPT in {response_ms} ms!')
        print(f'total tokens:{total_tokens}\tprompt tokens:{prompt_tokens}\tcompletion tokens:{completion_tokens}')

        return response


    def _format_request_dict(self, messages=[], functions=None, function_call=None):
        request_args_dict = {
            "messages": messages,
            "stream": False,
            "temperature": 0
        }

        if functions:
            request_args_dict['functions'] = functions

        if functions and function_call:
            request_args_dict['function_call'] = function_call

        request_args_dict['engine'] = self.aoai_deployment

        return request_args_dict 

    def _safe_load_flow_yaml(self, yaml_str):
        try:
            parsed_flow_yaml = self._smart_yaml_loads(yaml_str)
            for node in parsed_flow_yaml['nodes']:
                if node['type'] == 'llm':
                    if 'prompt' in node['inputs']:
                        del node['inputs']['prompt']
            if 'node_variants' in parsed_flow_yaml:
                for _, v in parsed_flow_yaml['node_variants'].items():
                    for _, variant in v['variants']:
                        if 'prompt' in variant['node']['inputs']:
                            del variant['node']['inputs']['prompt']
            self.flow_yaml = yaml.dump(parsed_flow_yaml, allow_unicode=True, sort_keys=False, indent=2)
            return parsed_flow_yaml
        except Exception as ex:
            print(ex)
            raise ex

    def _rewrite_user_input(self, user_input, messages):
        # construct conversation message, only keep the last four messages for user and assistant
        cur_len = 0
        conversation_message_array = []
        for message in reversed(messages):
            role = message['role']
            if role != 'system' and role != 'function' and cur_len < 4:
                cur_len += 1
                if role == 'user':
                    conversation_message_array.append(f'User: {message["content"]}')
                else:
                    conversation_message_array.append(f'PF copilot: {message["content"]}')
        conversation_message_array.reverse()
        conversation_message = '\n'.join(conversation_message_array)

        rewrite_user_input_instruction = self.rewrite_user_input_template.render(conversation=conversation_message)
        chat_message = [
            {'role':'system', 'content': rewrite_user_input_instruction},
            {'role':'user', 'content': user_input}
        ]
        response = self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        print(f"rewrite_user_input: {message}")
        return message
    
    def _refine_python_code(self, python_code):
        refine_python_code_instruction = self.refine_python_code_template.render()
        chat_message = [
            {'role':'system', 'content': refine_python_code_instruction},
            {'role':'user', 'content': python_code}
        ]

        response = self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        return message
    
    def _find_dependent_python_packages(self, python_code):
        find_dependent_python_packages_instruction = self.find_python_package_template.render()
        chat_message = [
            {'role':'system', 'content': find_dependent_python_packages_instruction},
            {'role':'user', 'content': python_code}
        ]

        response = self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "").replace(' ', '')
        packages = []
        for p in message.split(','):
            if p != 'None':
                packages.append(p)
        return packages
    
    def _summarize_flow_name(self, flow_description):
        summarize_flow_name_instruction = self.summarize_flow_name_template.render()
        chat_message = [
            {'role':'system', 'content': summarize_flow_name_instruction},
            {'role':'user', 'content': flow_description}
        ]

        response = self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        return message

    def _fix_json_string_and_loads(self, json_string, error, max_retry=3):
        try:
            fix_json_string_instruction = self.json_string_fixer_template.render(original_string=json_string, error_message=error)
            chat_message = [
                {'role':'system', 'content': fix_json_string_instruction},
            ]
            response = self._ask_openai_async(messages=chat_message)
            message = getattr(response.choices[0].message, "content", "")
            return json.loads(message)
        except JSONDecodeError as ex:
            print(f'Failed to fix json string {json_string} with error {error}')
            if max_retry > 0 and message != json_string:
                return self._fix_json_string_and_loads(message, str(ex), max_retry=max_retry-1)
            raise ex

    def _fix_yaml_string_and_loads(self, yaml_string, error, max_retry=3):
        try:
            fix_yaml_string_instruction = self.yaml_string_fixer_template.render(original_string=yaml_string, error_message=error)
            chat_message = [
                {'role':'system', 'content': fix_yaml_string_instruction},
            ]
            response = self._ask_openai_async(messages=chat_message)
            message = getattr(response.choices[0].message, "content", "")
            return yaml.safe_load(message)
        except yaml.MarkedYAMLError as ex:
            print(f'Failed to fix yaml string {yaml_string} with error {error}')
            if max_retry > 0 and message != yaml_string:
                return self._fix_yaml_string_and_loads(message, str(ex), max_retry=max_retry-1)
            raise ex

    def _smart_yaml_loads(self, yaml_string):
        try:
            return yaml.safe_load(yaml_string)
        except yaml.MarkedYAMLError as ex:
            return self._fix_yaml_string_and_loads(yaml_string, str(ex))

    def _smart_json_loads(self, json_string):
        try:
            return json.loads(json_string)
        except JSONDecodeError as ex:
            pattern = r'\\\n'
            updated_function_call = re.sub(pattern, r'\\n', str(json_string))
            if updated_function_call == json_string:
                print(f'Failed to load json string {json_string}')
                return self._fix_json_string_and_loads(json_string, str(ex))
            else:
                return self._smart_json_loads(updated_function_call)