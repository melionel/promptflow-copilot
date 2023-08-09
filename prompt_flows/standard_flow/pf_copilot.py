import time
from openai.error import RateLimitError
from promptflow.tools.aoai import chat as aoai_chat
from promptflow.tools.openai import chat as openai_chat
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection

def construct_prompt(current_context):
    update_current_context = []
    for item in current_context:
        role = item.get("role", None)
        content = item.get("content", None)
        name = item.get("name", None)

        if name is not None:
            update_current_context.append(":\n".join([role, "name", name]) + "\n" + ":\n".join(["content", content]))
        else:
            update_current_context.append(":\n".join([role, content]))
    update_current_context = "\n".join(update_current_context)
    return update_current_context

class PfCopilot:
    def __init__(
        self,
        connection,
        functions_def,
        functions_imp,
        system_prompt,
        built_in_tools_prompt,
        llm_tool_prompt,
        python_tool_prompt,
        instruction_prompt,
        user_prompt,
        model_or_deployment_name
    ):
        self.connection = connection
        self.functions_def = functions_def
        self.functions_imp = functions_imp
        self.system_prompt = system_prompt
        self.built_in_tools_prompt = built_in_tools_prompt
        self.llm_tool_prompt = llm_tool_prompt
        self.python_tool_prompt = python_tool_prompt
        self.instruction_prompt = instruction_prompt
        self.user_prompt = user_prompt
        self.model_or_deployment_name = model_or_deployment_name

    def construct_prompt(self):
        system_message = self.system_prompt + "\n" + self.built_in_tools_prompt + "\n" + self.llm_tool_prompt + "\n" + \
                            self.python_tool_prompt + "\n" + self.instruction_prompt
        user_message = self.user_prompt
        chat_message = [
            {'role':'system', 'content': system_message},
            {'role':'user', 'content': user_message}
        ]

        return construct_prompt(chat_message)

    def ask_ai(self):
        current_context = self.construct_prompt()
        if isinstance(self.connection, AzureOpenAIConnection):
            try:
                response = aoai_chat(
                    connection=self.connection,
                    prompt=current_context,
                    deployment_name=self.model_or_deployment_name,
                    functions=self.functions_def)
            except Exception as e:
                if "The API deployment for this resource does not exist" in e.exc_msg:
                    raise Exception(
                        "Please fill in the deployment name of your Azure OpenAI resoure gpt-4 model.")

        elif isinstance(self.connection, OpenAIConnection):
            response = openai_chat(
                connection=self.connection,
                prompt=current_context,
                model=self.model_or_deployment_name,
                functions=self.functions_def)
        else:
            raise ValueError("Connection must be an instance of AzureOpenAIConnection or OpenAIConnection")
        
        return response
