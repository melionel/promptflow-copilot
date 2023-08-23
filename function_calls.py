dump_flow = {
    'name': 'dump_flow',
    'description': 'dump the generated/converted/modified flow to local disk for user and return the path',
    'parameters': {
        'type': 'object',
        'properties': {
            'flow_yaml': {
                'type': 'string',
                'description': 'flow yaml string'
            },
            'explaination': {
                'type': 'string',
                'description': 'explanation about how the flow works'
            },
            'python_functions': {
                'type': 'array',
                'description': 'python function implementations',
                'items': {
                    'type': 'string'
                }
            },
            'prompts': {
                'type': 'array',
                'description': 'prompts',
                'items': {
                    'type': 'string'
                }
            },
            'flow_inputs_schema': {
                'type': 'array',
                'description': 'flow inputs schemas',
                'items': {
                    'type': 'string'
                }
            },
            'flow_outputs_schema': {
                'type': 'array',
                'description': 'flow outputs schemas',
                'items': {
                    'type': 'string'
                }
            },
            'reasoning': {
                'type': 'string',
                'description': 'reasoning about why this function is called'
            }
        },
        'required': ['flow_yaml', 'explaination', 'python_functions', 'prompts', 'reasoning']
    }
}

read_local_file = {
    'name': 'read_local_file',
    'description': 'read file content from local disk and return the content in string format',
    'parameters': {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'path to local file'
            },
            'reasoning': {
                'type': 'string',
                'description': 'reasoning about why this function is called'
            }
        },
        'required': ['path', 'reasoning']
    }
}

read_local_folder = {
    'name': 'read_local_folder',
    'description': 'read all files content from local folder and return a dictionary of file name and file content',
    'parameters': {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'path to local folder'
            },
            'reasoning': {
                'type': 'string',
                'description': 'reasoning about why this function is called'
            }
        },
        'required': ['path', 'reasoning']
    }
}

read_flow_from_local_file = {
    'name': 'read_flow_from_local_file',
    'description': 'read existing flow from a local file',
    'parameters': {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'path to local file'
            },
            'reasoning': {
                'type': 'string',
                'description': 'reasoning about why this function is called'
            }
        },
        'required': ['path', 'reasoning']
    }
}

read_flow_from_local_folder ={
    'name': 'read_flow_from_local_folder',
    'description': 'read existing flow from local folder',
    'parameters': {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'path to local folder'
            },
            'reasoning': {
                'type': 'string',
                'description': 'reasoning about why this function is called'
            }
        },
        'required': ['path', 'reasoning']
    }
}

dump_sample_inputs = {
    'name': 'dump_sample_inputs',
    'description': 'generate sample inputs for the flow and dump the generated sample inputs into local file for user and return the file path',
    'parameters': {
        'type': 'object',
        'properties': {
            'sample_inputs': {
                'type': 'array',
                'description': 'generated sample inputs',
                'items': {
                    'type': 'string'
                },
            'reasoning': {
                'type': 'string',
                'description': 'reasoning about why this function is called'
            }
            },
        },
        'required': ['sample_inputs', 'reasoning']
    }
}

dump_evaluation_flow ={
    'name': 'dump_evaluation_flow',
    'description': 'create evaluation flow for the flow and dump the generated evaluation flow into local file for user and return the path',
    'parameters': {
        'type': 'object',
        'properties': {
            'sample_inputs': {
                'type': 'array',
                'description': 'generated sample inputs',
                'items': {
                    'type': 'string'
                }
            },
            'flow_outputs_schema': {
                'type': 'array',
                'description': 'flow outputs schemas',
                'items': {
                    'type': 'string'
                }
            },
            'reasoning': {
                'type': 'string',
                'description': 'reasoning about why this function is called'
            }
        },
        'required': ['sample_inputs', 'flow_outputs_schema', 'reasoning']
    }
}

dump_flow_definition_and_description = {
    'name': 'dump_flow_definition_and_description',
    'description': 'dump flow yaml and description to local disk',
    'parameters': {
        'type': 'object',
        'properties': {
            'flow_yaml': {
                'type': 'string',
                'description': 'flow yaml string'
            },
            'description': {
                'type': 'string',
                'description': 'description about how the flow works'
            },
            'reasoning': {
                'type': 'string',
                'description': 'reasoning about why this function is called'
            }
        },
        'required': ['flow_yaml', 'description', 'reasoning']
    }
}