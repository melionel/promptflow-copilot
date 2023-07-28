# Promptflow Copilot

An intelligent copilot designed for promptflow

## Objective

The promptflow copilot is aimed build an intellegent copilot on top of ChatGPT that can interactively help promptflow users to:

- Automatically create promptflow to accomplish the given goal [Done]
- Understand user's existing code and turned it into promptflow [Done]
- Help user to generate bulktest input data [Done]
- Help user to generate evaluation flow [Done]
- Parse and improve an existing promptflow [TODO]

## How to use

- From root folder, install the requirements using
```bash
pip install -r requrements.txt
```

- Create a pfcopilot.env file in root folder, reference my_pfcopilot.env to set the corresponding environment variables in your own pfcopilot.env file.

- From the root folder, run
```bash
python main.py
```

- chat with promptflow copilot

for example:

1. Ask copilot to create a promptflow to achieve your goal:
```
my goal: check if there are gramma mistakes in a github repo's files, the file may be written with python, c, go or any programming language; if found gramma mistakes, create a pull request to fix the gramma mistakes
```

2. Ask copilot to create promptflow based on your own python application
```
I have a python program in my_app.py, please convert it into a flow
```
or
```
I have a python program in the folder C:\LangchainTests\chat_with_pdf, can you understand it and help to convert it into a flow
```

3. Ask copilot to generate bulktest input data
```
geneate bulktest inputs data for the flow
```

4. Ask copilot to generate evaluation flow
```
generate evaluation flow for the flow
```


## Known issue

- Sometimes, pfcopilot may not automatically dump the generated flow into local folder. If that happens, please tell pfcopilot to do that explicitlly.
- Sometimes, the generated flow may lack some python files when the flow is converted from local file(s). Please give pfcopilot furthur instructions to let it generate the missing files for you.
