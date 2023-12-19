# Distribute flow as executable app
:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

We are going to use the [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification/) as
an example to show how to distribute flow as executable app with [Pyinstaller](https://pyinstaller.org/en/stable/requirements.html#).


Please ensure that you have installed all the required dependencies. You can refer to the "Prerequisites" section in the README of the [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification/) for a comprehensive list of prerequisites and installation instructions. And we recommend you to add a `requirements.txt` to indicate all the required dependencies for each flow. 

[Pyinstaller](https://pyinstaller.org/en/stable/installation.html) is a popular tool used for converting Python applications into standalone executables. It allows you to package your Python scripts into a single executable file, which can be run on a target machine without requiring the Python interpreter to be installed.
[Streamlit](https://docs.streamlit.io/library/get-started) is an open-source Python library used for creating web applications quickly and easily. It's designed for data scientists and engineers who want to turn data scripts into shareable web apps with minimal effort.
We use Pyinstaller to package the flow and Streamlit to create custom web apps. Prior to distributing the workflow, kindly ensure that you have installed them.


## Build a flow as executable format
Note that all dependent connections must be created before building as executable.
```bash
# create connection if not created before
pf connection create --file ../../../examples/connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> --name open_ai_connection
```

Use the command below to build a flow as executable format:
```bash
pf flow build --source <path-to-your-flow-folder> --output <your-output-dir> --format executable
```

## Executable format folder structure

Exported files & its dependencies are located in the same folder. The structure is as below:
- flow: the folder contains all the flow files.
- connections: the folder contains yaml files to create all related connections.
- app.py: the entry file is included as the entry point for the bundled application.
- app.spec: the spec file tells PyInstaller how to process your script.
- main.py: it will start streamlit service and be called by the entry file.
- settings.json: a json file to store the settings of the executable application.
- build: a folder contains various log and working files.
- dist: a folder contains the executable application.
- README.md: Simple introduction of the files.


### A template script of the entry file
PyInstaller reads a spec file or Python script written by you. It analyzes your code to discover every other module and library your script needs in order to execute. Then it collects copies of all those files, including the active Python interpreter, and puts them with your script in a single folder, or optionally in a single executable file. 

We provide a Python entry script named `app.py` as the entry point for the bundled app, which enables you to serve a flow folder as an endpoint.

```python
import os
import sys

from promptflow._cli._pf._connection import create_connection
from streamlit.web import cli as st_cli
from streamlit.runtime import exists

from main import start

def is_yaml_file(file_path):
    _, file_extension = os.path.splitext(file_path)
    return file_extension.lower() in ('.yaml', '.yml')

def create_connections(directory_path) -> None:
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            if is_yaml_file(file_path):
                create_connection(file_path)


if __name__ == "__main__":
    create_connections(os.path.join(os.path.dirname(__file__), "connections"))
    if exists():
        start()
    else:
        main_script = os.path.join(os.path.dirname(__file__), "main.py")
        sys.argv = ["streamlit", "run", main_script, "--global.developmentMode=false"]
        st_cli.main(prog_name="streamlit")

```


### A template script of the spec file
The spec file tells PyInstaller how to process your script. It encodes the script names and most of the options you give to the pyinstaller command. The spec file is actually executable Python code. PyInstaller builds the app by executing the contents of the spec file.

To streamline this process, we offer a `app.spec` spec file that bundles the application into a single file. For additional information on spec files, you can refer to the [Using Spec Files](https://pyinstaller.org/en/stable/spec-files.html). Please replace `streamlit_runtime_interpreter_path` with the path of streamlit runtime interpreter in your environment.

```spec
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata

datas = [('connections', 'connections'), ('flow', 'flow'), ('settings.json', '.'), ('main.py', '.'), ('{{streamlit_runtime_interpreter_path}}', './streamlit/runtime')]
datas += collect_data_files('streamlit')
datas += copy_metadata('streamlit')
datas += collect_data_files('keyrings.alt', include_py_files=True)
datas += copy_metadata('keyrings.alt')
datas += collect_data_files('streamlit_quill')

block_cipher = None


a = Analysis(
    ['app.py', 'main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['bs4'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

### The bundled application using Pyinstaller
Once you've build a flow as executable format following [Build a flow as executable format](#build-a-flow-as-executable-format).
It will create two folders named `build` and `dist` within your specified output directory, denoted as <your-output-dir>. The `build` folder houses various log and working files, while the `dist` folder contains the `app` executable application.

### Connections
If the service involves connections, all related connections will be exported as yaml files and recreated in the executable package.
Secrets in connections won't be exported directly. Instead, we will export them as a reference to environment variables:
```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/OpenAIConnection.schema.json
type: open_ai
name: open_ai_connection
module: promptflow.connections
api_key: ${env:OPEN_AI_CONNECTION_API_KEY} # env reference
```

## Test the endpoint
Finally, You can distribute the bundled application `app` to other people. They can execute your program by double clicking the executable file, e.g. `app.exe` in Windows system or running the binary file, e.g. `app` in Linux system. 

The development server has a built-in web page they can use to test the flow by opening 'http://localhost:8501' in the browser. The expected result is as follows: if the flow served successfully, the process will keep alive until it is killed manually.

To your users, the app is self-contained. They do not need to install any particular version of Python or any modules. They do not need to have Python installed at all.

**Note**: The executable generated is not cross-platform. One platform (e.g. Windows) packaged executable can't run on others (Mac, Linux). 


## Known issues
1. Note that Python 3.10.0 contains a bug making it unsupportable by PyInstaller. PyInstaller will also not work with beta releases of Python 3.13.

## Next steps
- Try the example [here](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy)