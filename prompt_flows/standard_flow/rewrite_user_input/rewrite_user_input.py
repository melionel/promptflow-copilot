from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
from jinja2 import Environment
import openai

def _ask_openai(messages=[], functions=None, function_call=None, stream=False, connection=None, deployment_name=None):
    openai.api_key = connection.api_key
    openai.api_type = "azure"
    openai.api_base = connection.api_base
    openai.api_version = "2023-07-01-preview"

    request_args_dict = {
        "messages": messages,
        "stream": stream,
        "temperature": 0
    }
    if functions:
        request_args_dict['functions'] = functions
    if functions and function_call:
        request_args_dict['function_call'] = function_call
    request_args_dict['engine'] = deployment_name

    response = openai.ChatCompletion.create(**request_args_dict)
    return response

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(messages: list, user_input: str, max_history_len: int, prompt: str, connection: AzureOpenAIConnection, deployment_name: str) -> str:
  conversation_message_array = messages[-max_history_len:]
  conversation_message = '\n'.join(conversation_message_array)

  jinja_env = Environment(variable_start_string='[[', variable_end_string=']]')
  rewrite_user_input_template = jinja_env.from_string(prompt)
  rewrite_user_input_instruction = rewrite_user_input_template.render(conversation=conversation_message)
  chat_message = [
      {'role':'system', 'content': rewrite_user_input_instruction},
      {'role':'user', 'content': user_input}
  ]
  response = _ask_openai(messages=chat_message, connection=connection, deployment_name=deployment_name)
  message = getattr(response.choices[0].message, "content", "")
  return message