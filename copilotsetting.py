class CopilotSetting:
    def __init__(self, use_aoai, aoai_setting, openai_setting, use_endpoint, pfflowclient_setting):
        self.use_aoai = use_aoai
        self.aoai_setting = aoai_setting
        self.openai_setting = openai_setting
        self.use_endpoint = use_endpoint
        self.pfflowclient_setting = pfflowclient_setting


class AOAISetting:
    def __init__(self, aoai_key, aoai_api_base, aoai_deployment) -> None:
        self.aoai_key = aoai_key
        self.aoai_api_base = aoai_api_base
        self.aoai_deployment = aoai_deployment

class OpenAISetting:
    def __init__(self, openai_key, openai_model) -> None:
        self.openai_key = openai_key
        self.openai_model = openai_model

class PfFlowClientSetting:
    def __init__(self, url, api_key, azureml_model_deployment) -> None:
        self.url = url
        self.api_key = api_key
        self.azureml_model_deployment = azureml_model_deployment
