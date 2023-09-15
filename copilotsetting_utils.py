import os
from dotenv import load_dotenv
from copilotsetting import CopilotSetting, AOAISetting, OpenAISetting, PfFlowClientSetting


def get_copilotsetting():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(script_directory, 'pfcopilot.env'))

    use_aoai = os.environ.get("AOAI_BY_DEFAULT", "true").lower() == "true"
    use_endpoint = os.environ.get("USE_ENDPOINT", "true").lower() == "true"

    # aoai setting
    aoai_key = os.environ.get("AOAI_API_KEY")
    aoai_api_base = os.environ.get("AOAI_API_BASE")
    aoai_deployment = os.environ.get("AOAI_DEPLOYMENT")
    aoai_setting = AOAISetting(aoai_key, aoai_api_base, aoai_deployment)

    # openai setting
    openai_key=os.environ.get("OPENAI_API_KEY")
    openai_model=os.environ.get("OPENAI_MODEL")
    openai_setting = OpenAISetting(openai_key, openai_model)

    # pfflow client setting
    url = os.environ.get("ENDPOINT_URL")
    api_key = os.environ.get("ENDPOINT_API_KEY")
    azureml_model_deployment = os.environ.get("MODEL_DEPLOYMENT")
    pfflowclient_setting = PfFlowClientSetting(url, api_key, azureml_model_deployment)

    # copilot setting
    copilot_setting = CopilotSetting(use_aoai, aoai_setting, openai_setting, use_endpoint, pfflowclient_setting)
    return copilot_setting