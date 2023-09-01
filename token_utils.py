import tiktoken
from logging_util import get_logger

logger = get_logger()

def num_tokens_from_messages(messages):
    """Return the number of tokens used by a list of messages."""
    try:
        # we only support a few models for now, and they all use the same encoding
        model = "gpt-3.5-turbo-0613"
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
    tokens_per_name = -1  # if there's a name, the role is omitted

    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

def num_tokens_from_functions(functions):
        """Return the number of tokens used by a list of functions."""
        try:
            # we only support a few models for now, and they all use the same encoding
            model = "gpt-3.5-turbo-0613"
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")
        
        num_tokens = 0
        for function in functions:
            function_tokens = len(encoding.encode(function['name']))
            function_tokens += len(encoding.encode(function['description']))
            
            if 'parameters' in function:
                parameters = function['parameters']
                if 'properties' in parameters:
                    for propertiesKey in parameters['properties']:
                        function_tokens += len(encoding.encode(propertiesKey))
                        v = parameters['properties'][propertiesKey]
                        for field in v:
                            if field == 'type':
                                function_tokens += 2
                                function_tokens += len(encoding.encode(v['type']))
                            elif field == 'description':
                                function_tokens += 2
                                function_tokens += len(encoding.encode(v['description']))
                            elif field == 'items':
                                function_tokens -= 3
                                for _, o in v['items'].items():
                                    function_tokens += 2
                                    if isinstance(o, str):
                                        function_tokens += len(encoding.encode(o))
                                    elif isinstance(o, dict):
                                        for _, oo in o.items():
                                            function_tokens += 2
                                            function_tokens += len(encoding.encode(oo))
                            else:
                                logger.warning(f"Warning: not supported field {field}")
                    function_tokens += 11

            num_tokens += function_tokens

        num_tokens += 12 
        return num_tokens

def num_tokens_from_completions(completion_text):
    """Return the number of tokens used by a list of functions."""
    try:
        # we only support a few models for now, and they all use the same encoding
        model = "gpt-3.5-turbo-0613"
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    
    if not completion_text:
        return 0

    num_tokens = len(encoding.encode(completion_text))
    return num_tokens