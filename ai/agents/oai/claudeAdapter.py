# -*- coding: utf-8 -*-
"""
@ author:
@ info: claude to chatgpt
@ date: 2024/2/1 21:22

pip install boto3
pip install tiktoken
config  .aws/config
        .aws/credentials
"""

import json
import time
import xml.etree.ElementTree as E_T
import re
import copy
try:
    import tiktoken
    import boto3
except:
    raise Exception("Error, need: pip install boto3 tiktoken")

# check function_call Strict mode or not
STRICT_MODE_CHECK_FUNCTION = False
MAX_TOKEN = 10240
# define default model
Claude_AI_MODEL = 'anthropic.claude-3-sonnet-20240229-v1:0'
# define default temperature
Claude_AI_temperature = 0.1
Claude_role_map = {
    # "open ai name: claude name"
    "user": "user",
    "assistant": "assistant",
    "function": "user",
    "system": "assistant"
}

Claude_stop_reason_map = {
    "stop_sequence": "stop",
    "max_tokens": "length",
    "end_turn": "stop",
}


class AWSClaudeClient:

    @classmethod
    def run(cls, apiKey, data, model_name=None, temperature=None, use_url=None):
        model_name = model_name if model_name else Claude_AI_MODEL
        temperature = Claude_AI_temperature if temperature is None else temperature
        if "ApiKey" not in apiKey or apiKey['ApiKey'] is None or "" == apiKey['ApiKey']:
            raise Exception("LLM Claude api key empty,use_model: ", model_name, " need apikey")
        if "ApiSecret" not in apiKey or apiKey['ApiSecret'] is None or "" == apiKey['ApiSecret']:
            raise Exception("LLM Claude apk_secret empty,use_model: ", model_name, " need ApiSecret")

        use_url = use_url if use_url else "us-east-1"

        client_obj = boto3.client(
            service_name='bedrock-runtime',
            region_name=use_url,
            aws_access_key_id=apiKey['ApiKey'],
            aws_secret_access_key=apiKey['ApiSecret']
        )
        messages_copy = copy.deepcopy(data['messages'])
        messages, system = cls.input_to_openai(messages_copy)
        messages = cls.transform_message_role(messages)

        if "functions" in data:
            prompt_begin = cls.functions_to_function_call_string()
            prompt_begin = prompt_begin + cls.functions_to_tools_string(data['functions'])
            if messages[-1]['role'] == 'user':
                messages[-1]['content'] = messages[-1]['content'] + prompt_begin
            else:
                new_message = {
                    "role": "user",
                    "content": prompt_begin
                }
                messages.append(new_message)
            response = client_obj.invoke_model(
                modelId=model_name,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": MAX_TOKEN,
                        "messages": messages,
                        "temperature": temperature,
                        "system": system
                    },
                )
            )
        else:
            response = client_obj.invoke_model(
                modelId=model_name,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": MAX_TOKEN,
                        "messages": messages,
                        "temperature": Claude_AI_temperature,
                        "system": system
                    },
                )
            )
        response_body = json.loads(response.get('body').read())
        return cls.output_to_openai(response_body)
        pass

    @classmethod
    def output_to_openai(cls, data):
        completion = str(data["content"][0]['text'])
        if "usage" in data:
            in_token = data['usage']['input_tokens']
            out_token = data['usage']['output_tokens']
            sum_token = int(in_token) + int(out_token)
        else:
            in_token = out_token = 0
            sum_token = int(cls.num_tokens_from_string(str(data["content"])))
        # check function call
        if STRICT_MODE_CHECK_FUNCTION:
            function_call_flag = completion.strip().startswith("<function_calls>")
        else:
            function_call_flag = completion.strip().startswith("<function_calls>") or\
                all(substring in completion for substring in ("<function_calls>", "<invoke>", "<tool_name>", "</invoke>"))
        # return openai result
        if function_call_flag:
            """
            have function call
            """
            choices = cls.return_to_open_function_call(completion)
        else:
            """ just process as message """
            # replace code
            completion = cls.replace_code_to_python(completion)
            choices = {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": completion,
                },
                "finish_reason": Claude_stop_reason_map[
                    data.get("stop_reason")] if 'stop_reason' in data else None
                if data.get("stop_reason")
                else None,
            }

        return {
            "id": f"chatcmpl-{str(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": Claude_AI_MODEL,
            "usage": {
                "prompt_tokens": in_token,
                "completion_tokens": out_token,
                "total_tokens": sum_token,
            },
            "choices": [choices],
        }
        pass

    @classmethod
    def input_to_openai(cls, messages):
        result = []
        system = None
        for message in messages:
            item = {}
            role = message["role"]
            content = message["content"]
            if role.lower() == "system" and system is None:
                system = content
            else:
                if content is None and 'function_call' in message and message['function_call'] is not None:
                    content = cls.function_call_to_xml(message['function_call'])
                else:
                    content = cls.replace_python_to_code(content)
                item['role'] = Claude_role_map[role]
                item['content'] = content
                result.append(item)
        return result, system

    @classmethod
    def num_tokens_from_string(cls, string: str, encoding_name: str = "cl100k_base") -> int:
        """Returns the number of tokens in a text string."""
        encoding = tiktoken.get_encoding(encoding_name)
        num_tokens = len(encoding.encode(string))
        return num_tokens

    @classmethod
    def functions_to_tools_string(cls, functions):
        """
        trans openai functions to Claude2 tool
        """
        return_str = "Here are the tools available:\n<tools>\n"
        for item in functions:
            return_str = return_str + "<tool_description>\n"
            if "name" in item:
                return_str = return_str + "<tool_name>" + item['name'] + "</tool_name>\n"
            if "description" in item:
                return_str = return_str + "<description>" + item['description'] + "</description>\n"
            # parameters
            if "parameters" in item:
                return_str = return_str + "<parameters>\n"
                parameter_obj = item['parameters']
                if "type" in parameter_obj:
                    return_str = return_str + "<parameter>\n <name>" + parameter_obj['type'] + "</name>\n"
                    return_str = return_str + " <type>" + parameter_obj['type'] + "</type>\n"
                    if "properties" in parameter_obj:
                        return_str = return_str + " <parameters>\n"
                        for k, v in parameter_obj['properties'].items():
                            return_str = return_str + "  <parameter>\n   <name>" + k + "</name>\n"
                            for kk, vv in v.items():
                                return_str = return_str + "   <" + kk + ">" + vv + "</" + kk + ">\n"
                            return_str = return_str + "  </parameter>\n"
                        return_str = return_str + " </parameters>\n"
                if "required" in item['parameters']:
                    return_str = return_str + "<required>" + str(
                        ",".join(item['parameters']['required'])) + "</required>\n"
                return_str = return_str + "</parameter>\n</parameters>\n"
            return_str = return_str + "</tool_description>\n"
        return_str = return_str + "</tools>\n"
        return return_str
        pass

    @classmethod
    def functions_to_function_call_string(cls):
        """
        tell Claude2, function call return
        """
        return_str = """In this environment you have access to a set of tools you can use to answer the user's question.
                        Your answer must be english.You may call them like this.
                        Only invoke one function at a time and wait for the results before invoking another function:\n
                        <function_calls>\n<invoke>\n"""
        return_str = return_str + "<tool_name>$TOOL_NAME</tool_name>\n"
        return_str = return_str + "<parameters>\n"
        return_str = return_str + "<$PARAMETER_NAME>$PARAMETER_VALUE</$PARAMETER_NAME>\n ... \n"
        return_str = return_str + "</parameters>\n</invoke>\n"
        return_str = return_str + "</function_calls>\n"
        return return_str
        pass

    @classmethod
    def function_call_to_xml(cls, data):
        """
        openai message function_call to Claude2 message
        """
        return_str = "<function_calls>\n<invoke>"
        return_str = return_str + "<tool_name>" + data['name'] + "</tool_name>\n"
        return_str = return_str + "<arguments>" + data['arguments'] + "</arguments>\n"
        return_str = return_str + "</invoke>\n</function_calls>\n"
        return return_str
        pass

    @classmethod
    def return_to_open_function_call(cls, data):
        """
        trans Claude2 to openai function call return
        """
        xml_string = data
        match = re.search(r'<invoke>(.*?)</invoke>', xml_string, re.DOTALL)
        result = match.group(1)
        function_xml_str = "<function_calls>\n<invoke>\n" + result.strip() + "</invoke>\n</function_calls>"
        root = E_T.fromstring(function_xml_str)
        invokes = root.findall("invoke")
        function_call = {}

        tool_name = invokes[0].find("tool_name").text
        function_call['name'] = tool_name
        args = invokes[0].find("parameters")
        args_obj = {}
        for item in args:
            if "object" == item.tag:
                args_son = item.findall("./")
                if len(args_son) > 0:
                    for son_item in args_son:
                        arg_name = son_item.tag
                        arg_value = son_item.text
                        args_obj[arg_name] = arg_value
                else:
                    arg_item_obj = json.loads(item.text)
                    for k, v in arg_item_obj.items():
                        args_obj[k] = json.dumps(v)
            else:
                arg_name = item.tag
                arg_value = item.text
                args_obj[arg_name] = arg_value

        return {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "function_call": {
                        "name": tool_name,
                        "arguments": json.dumps(args_obj)
                },
                "logprobs": None,
                "finish_reason": "function_call"
            }
        }
        pass

    @classmethod
    def replace_code_to_python(cls, response_str):
        response_str = response_str.replace("\n<code>\n", "\n```python\n")
        response_str = response_str.replace("\n</code>\n", "\n```\n")
        return response_str

    @classmethod
    def replace_python_to_code(cls, response_str):
        response_str = response_str.replace("\n```python\n", "\n<code>\n")
        response_str = response_str.replace("\n```\n", "\n</code>\n")
        return response_str

    @classmethod
    def transform_message_role(cls, message):
        transformed_message = []
        now_content = ""
        now_role = ""
        system_flag = False
        # change role
        for i, item in enumerate(message):
            content = item.get('content')
            role = item.get("role")
            now_item = {}
            now_item['content'] = content
            if role == "assistant":
                now_item['role'] = "assistant"
            else:
                now_item['role'] = "user"
            transformed_message.append(now_item)

        now_role = ""
        now_content = ""
        result = []
        # update message role
        for i, item in enumerate(transformed_message):
            content = item.get('content')
            role = item.get("role")
            # other not first system
            if now_role != "":
                if role == now_role:
                    now_content = now_content + "\n" + content
                else:
                    now_item = {}
                    now_item['content'] = now_content
                    now_item['role'] = now_role
                    result.append(now_item)
                    now_role = role
                    now_content = content
            else:
                now_role = role
                now_content = content
            if i == len(transformed_message) - 1:
                now_item = {}
                now_item['content'] = now_content
                now_item['role'] = now_role
                result.append(now_item)

        return result
