dump_flow = {
    'name': 'dump_flow',
    'description': 'dump flow to local disk',
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
        },
        'required': ['flow_yaml', 'explaination', 'python_functions', 'prompts']
    }
}

read_local_file = {
    'name': 'read_local_file',
    'description': 'read file content from local disk',
    'parameters': {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'path to local file'
            }
        },
        'required': ['path']
    }
}

read_local_folder = {
    'name': 'read_local_folder',
    'description': 'read all files content from local folder',
    'parameters': {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'path to local folder'
            }
        },
        'required': ['path']
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
            }
        },
        'required': ['path']
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
            }
        },
        'required': ['path']
    }
}

dump_sample_inputs = {
    'name': 'dump_sample_inputs',
    'description': 'dump generate sample inputs into local file',
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
        },
        'required': ['sample_inputs']
    }
}

dump_evaluation_flow ={
    'name': 'dump_evaluation_flow',
    'description': 'create evaluation flow',
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
        },
        'required': ['sample_inputs', 'flow_outputs_schema']
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
            }
        },
        'required': ['flow_yaml', 'description']
    }
}