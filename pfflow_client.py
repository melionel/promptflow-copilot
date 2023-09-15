import json
import urllib.request

class PfFlowClient:
    def __init__(self, url, api_key, azureml_model_deployment) -> None:
        self.url = url
        self.api_key = api_key
        self.azureml_model_deployment = azureml_model_deployment       
       

    def get_understand_flow_system_message(self, flow_folder, flow_yaml, flow_description):
        function_input = {
            "flow_folder": flow_folder,
            "flow_yaml": flow_yaml,
            "flow_description": flow_description
        }
        
        result = self.consume_endpoint(function_input, "get_understand_flow_system_message")
        return result
    
    def get_system_instruction(self):
        function_input = {}
        
        result = self.consume_endpoint(function_input, "get_system_instruction")
        return result
    
    def get_function_call_instruction(self, function_calls):
        function_input = {
            "function_calls": function_calls
        }
        
        result = self.consume_endpoint(function_input, "get_function_call_instruction")
        return result


    def rewrite_user_input(self, content, messages):
        function_input = {
            "content": content,
            "messages": messages
        }

        result = self.consume_endpoint(function_input, "rewrite_user_input")
        return result

    def summarize_flow_name(self, explaination):
        function_input = {
            "explaination": explaination
        }
        
        result = self.consume_endpoint(function_input, "summarize_flow_name")
        return result
    
    def safe_load_flow_yaml(self, flow_yaml):
        function_input = {
            "flow_yaml": flow_yaml
        }

        result = self.consume_endpoint(function_input, "safe_load_flow_yaml")
        return result
    
    def refine_python_code(self, python_code):
        function_input = {
            "python_code": python_code
        }

        result = self.consume_endpoint(function_input, "refine_python_code")
        return result
    
    def find_dependent_python_packages(self, refined_code):
        function_input = {
            "refined_code": refined_code
        }

        result = self.consume_endpoint(function_input, "refined_code")
        return result
    
    def smart_json_loads(self, yaml_string):
        function_input = {
            "yaml_string": yaml_string
        }

        result = self.consume_endpoint(function_input, "smart_json_loads")
        return result
    
    def fix_json_string_and_loads(self, json_string, error, max_retry):
        function_input = {
            "json_string": json_string,
            "error": error,
            "max_retry": max_retry
        }

        result = self.consume_endpoint(function_input, "fix_json_string_and_loads")
        return result
    
    def fix_yaml_string_and_loads(self, yaml_string, error, max_retry):
        function_input = {
            "yaml_string": yaml_string,
            "error": error,
            "max_retry": max_retry
        }

        result = self.consume_endpoint(function_input, "fix_yaml_string_and_loads")
        return result
    
    def smart_yaml_loads(self, yaml_string):
        function_input = {
            "yaml_string": yaml_string
        }

        result = self.consume_endpoint(function_input, "smart_yaml_loads")
        return result
    
    def ask_openai_async(self, messages, functions, function_call):
        function_input = {
            "messages": messages,
            "functions": functions,
            "function_call": function_call
            }
        
        result = self.consume_endpoint(function_input, "ask_openai_async")
        return result
   
    def consume_endpoint(self, function_input, reason):
        data = {
            "data": json.dumps(function_input),
            "reason": reason
        }

        body = str.encode(json.dumps(data))
        if not self.api_key:
            raise Exception("A key should be provided to invoke the endpoint")
        
        headers = {'Content-Type':'application/json', 'Authorization':('Bearer '+ self.api_key), 'azureml-model-deployment': self.azureml_model_deployment }
        req = urllib.request.Request(self.url, body, headers)
        
        try:
            response = urllib.request.urlopen(req)
            result = response.read().decode('utf-8')
            return json.loads(result)["answer"]
        except urllib.error.HTTPError as error:
            print("The request failed with status code: " + str(error.code))
            print(error.info())
            print(error.read().decode("utf8", 'ignore'))