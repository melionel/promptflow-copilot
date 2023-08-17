from typing import Union

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from pf_copilot import PfCopilot

@tool
def ask_copilot(
    connection: Union[AzureOpenAIConnection, OpenAIConnection],
    functions: list,
    system_prompt: str, 
    built_in_tools_prompt: str,
    llm_tool_prompt: str,
    python_tool_prompt: str,
    instruction_prompt: str,
    user_prompt: str,
    model_or_deployment_name: str):

    copilot = PfCopilot(
        connection=connection,
        functions_def=functions,
        functions_imp=[],
        system_prompt=system_prompt,
        built_in_tools_prompt=built_in_tools_prompt,
        llm_tool_prompt=llm_tool_prompt,
        python_tool_prompt=python_tool_prompt,
        instruction_prompt=instruction_prompt,
        user_prompt=user_prompt,
        model_or_deployment_name=model_or_deployment_name
    )

    response = copilot.ask_ai()
    
    message = getattr(response, "content", "")

    if "function_call" in response:
        finish_reason = "function_call"
        function_name = response["function_call"]["name"]
        function_args = response["function_call"]["arguments"]
    else:
        finish_reason = "stop"
        function_name = "NA"
        function_args = "NA"

    result = {
        'finish_reason': finish_reason,
        'message': message,
        'function_name': function_name,
        'function_args': function_args
    }

    return result["function_name"]