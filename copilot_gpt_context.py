import json
import openai
import re
import yaml
from json import JSONDecodeError
from logging_util import get_logger
from jinja2 import Template

from copilotsetting import CopilotSetting

logger = get_logger()


class CopilotGPTContext:
    def __init__(self,
                 copilot_instruction_template: Template,
                 rewrite_user_input_template: Template,
                 refine_python_code_template: Template,
                 find_python_package_template: Template,
                 summarize_flow_name_template: Template,
                 understand_flow_template: Template,
                 json_string_fixer_template: Template,
                 yaml_string_fixer_template: Template,
                 function_call_instruction_template: Template,
                 copilot_setting: CopilotSetting) -> None:
        self.copilot_setting = copilot_setting

        self.copilot_instruction_template = copilot_instruction_template
        self.rewrite_user_input_template = rewrite_user_input_template
        self.refine_python_code_template = refine_python_code_template
        self.find_python_package_template = find_python_package_template
        self.summarize_flow_name_template = summarize_flow_name_template
        self.understand_flow_template = understand_flow_template
        self.json_string_fixer_template = json_string_fixer_template
        self.yaml_string_fixer_template = yaml_string_fixer_template
        self.function_call_instruction_template = function_call_instruction_template

        self.system_instruction = self.copilot_instruction_template.render()
    

    def check_env(self):
        if self.copilot_setting.use_aoai:
            aoai_setting = self.copilot_setting.aoai_setting
            if not aoai_setting.aoai_key or not aoai_setting.aoai_deployment or not aoai_setting.aoai_api_base:
                return False, "You configured to use AOAI, but one or more of the following environment variables were not set: AOAI_API_KEY, AOAI_DEPLOYMENT, AOAI_API_BASE"
            else:
                openai.api_key = aoai_setting.aoai_key
                openai.api_type = "azure"
                openai.api_base = aoai_setting.aoai_api_base
                openai.api_version = "2023-07-01-preview"
                return True, ""
        else:
            openai_setting = self.copilot_setting.openai_setting
            if not openai_setting.openai_key or not openai_setting.openai_model:
                return False, "You configured to use OPENAI, but one or more of the following environment variables were not set: OPENAI_API_KEY, OPENAI_API_KEY"
            else:
                openai.api_key = openai_setting.openai_key
                return True, ""


    async def _ask_openai_async(self, messages=[], functions=None, function_call=None, stream=False):
        request_args_dict = {
            "messages": messages,
            "stream": stream,
            "temperature": 0
        }

        if functions:
            request_args_dict['functions'] = functions

        if functions and function_call:
            request_args_dict['function_call'] = function_call

        if self.copilot_setting.use_aoai:
            request_args_dict['engine'] = self.copilot_setting.aoai_setting.aoai_deployment
        else:
            request_args_dict['model'] = self.copilot_setting.openai_setting.openai_model

        response = await openai.ChatCompletion.acreate(**request_args_dict)

        if not stream:
            response_ms = response.response_ms
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            logger.info(f'Get response from ChatGPT in {response_ms} ms!')
            logger.info(f'total tokens:{total_tokens}\tprompt tokens:{prompt_tokens}\tcompletion tokens:{completion_tokens}')

        return response

    # this function is for calling gpt with stream output in the flow.
    # since we use the python tool, the result of tool should be JSON serializable and may not be async_generator, so we cannot use async function.
    def _ask_openai(self, messages=[], functions=None, function_call=None, stream=False):
        request_args_dict = {
            "messages": messages,
            "stream": stream,
            "temperature": 0
        }

        if functions:
            request_args_dict['functions'] = functions

        if functions and function_call:
            request_args_dict['function_call'] = function_call

        if self.copilot_setting.use_aoai:
            request_args_dict['engine'] = self.copilot_setting.aoai_setting.aoai_deployment
        else:
            request_args_dict['model'] = self.copilot_setting.openai_setting.openai_model

        response = openai.ChatCompletion.create(**request_args_dict)
        return response

    async def _safe_load_flow_yaml(self, yaml_str):
        try:
            parsed_flow_yaml = await self._smart_yaml_loads(yaml_str)
            if 'nodes' in parsed_flow_yaml:
                for node in parsed_flow_yaml['nodes']:
                    if 'type' in node and node['type'] == 'llm':
                        if 'inputs' in node and 'prompt' in node['inputs']:
                            del node['inputs']['prompt']
            if 'node_variants' in parsed_flow_yaml:
                for _, v in parsed_flow_yaml['node_variants'].items():
                    for _, variant in v['variants'].items():
                        if 'inputs' in variant['node'] and 'prompt' in variant['node']['inputs']:
                            del variant['node']['inputs']['prompt']
            self.flow_yaml = yaml.dump(parsed_flow_yaml, allow_unicode=True, sort_keys=False, indent=2)
            return parsed_flow_yaml
        except Exception as ex:
            logger.error(ex)
            raise ex

    async def _rewrite_user_input(self, user_input, messages):
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
        response = await self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        logger.info(f"rewrite_user_input: {message}")
        return message

    async def _refine_python_code(self, python_code):
        refine_python_code_instruction = self.refine_python_code_template.render()
        chat_message = [
            {'role':'system', 'content': refine_python_code_instruction},
            {'role':'user', 'content': python_code}
        ]

        response = await self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        return message

    async def _find_dependent_python_packages(self, python_code):
        find_dependent_python_packages_instruction = self.find_python_package_template.render()
        chat_message = [
            {'role':'system', 'content': find_dependent_python_packages_instruction},
            {'role':'user', 'content': python_code}
        ]

        response = await self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "").replace(' ', '')
        packages = []
        for p in message.split(','):
            if p != 'None':
                packages.append(p)
        return packages

    async def _summarize_flow_name(self, flow_description):
        summarize_flow_name_instruction = self.summarize_flow_name_template.render()
        chat_message = [
            {'role':'system', 'content': summarize_flow_name_instruction},
            {'role':'user', 'content': flow_description}
        ]

        response = await self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        return message

    async def _fix_json_string_and_loads(self, json_string, error, max_retry=3):
        try:
            fix_json_string_instruction = self.json_string_fixer_template.render(original_string=json_string, error_message=error)
            chat_message = [
                {'role':'system', 'content': fix_json_string_instruction},
            ]
            response = await self._ask_openai_async(messages=chat_message)
            message = getattr(response.choices[0].message, "content", "")
            return json.loads(message)
        except JSONDecodeError as ex:
            logger.error(f'Failed to fix json string {json_string} with error {error}')
            if max_retry > 0 and message != json_string:
                return await self._fix_json_string_and_loads(message, str(ex), max_retry=max_retry-1)
            raise ex

    async def _fix_yaml_string_and_loads(self, yaml_string, error, max_retry=3):
        try:
            fix_yaml_string_instruction = self.yaml_string_fixer_template.render(original_string=yaml_string, error_message=error)
            chat_message = [
                {'role':'system', 'content': fix_yaml_string_instruction},
            ]
            response = await self._ask_openai_async(messages=chat_message)
            message = getattr(response.choices[0].message, "content", "")
            return yaml.safe_load(message)
        except yaml.MarkedYAMLError as ex:
            logger.error(f'Failed to fix yaml string {yaml_string} with error {error}')
            if max_retry > 0 and message != yaml_string:
                return await self._fix_yaml_string_and_loads(message, str(ex), max_retry=max_retry-1)
            raise ex

    async def _smart_yaml_loads(self, yaml_string):
        try:
            return yaml.safe_load(yaml_string)
        except yaml.MarkedYAMLError as ex:
            return await self._fix_yaml_string_and_loads(yaml_string, str(ex))

    async def _smart_json_loads(self, json_string):
        try:
            return json.loads(json_string)
        except JSONDecodeError as ex:
            pattern = r'\\\n'
            updated_function_call = re.sub(pattern, r'\\n', str(json_string))
            if updated_function_call == json_string:
                logger.error(f'Failed to load json string {json_string}')
                return await self._fix_json_string_and_loads(json_string, str(ex))
            else:
                return await self._smart_json_loads(updated_function_call)