import os
import json
import re
import streamlit as st
from openai import OpenAI

# Kimi API Configuration
KIMI_CONFIGS = {
    "api_key": __import__("os").environ.get("MOONSHOT_API_KEY", ""),
    "base_url": "https://api.moonshot.cn/v1",
    "model_advanced": "kimi-k2.6",
    "model_basic": "kimi-k2.6"
}

def call_llm(system_msg, user_msg, supplier=None):
    # 如果未提供supplier，则从session_state获取，否则使用默认值
    if supplier is None:
        supplier = getattr(st.session_state, 'current_supplier', 'azure')
    
    # 获取API Key（优先使用sidebar输入的key，否则使用默认配置）
    api_key = getattr(st.session_state, 'api_key', '') or KIMI_CONFIGS["api_key"]
    
    if not api_key:
        raise ValueError("API Key not available. Please configure KIMI API Key.")

    try:
        # ... existing code ...
        client = OpenAI(
            api_key=api_key,
            base_url=KIMI_CONFIGS["base_url"]
        )
        
        # 根据supplier选择模型
        if supplier == "azure":
            model = KIMI_CONFIGS["model_advanced"]  # kimi-k2-0905-preview
        elif supplier == "zhipu":
            model = KIMI_CONFIGS["model_basic"]  # moonshot-v1-8k
        else:
            raise ValueError(f'Invalid LLM supplier: {supplier}')
        
        # 调用Kimi API — K2.6 thinking 模型硬要求 temperature=1.0
        _default_temp = 1.0 if isinstance(model, str) and model.startswith("kimi-k2.") else 0.0
        temperature = getattr(st.session_state, 'temperature', _default_temp)
        if isinstance(model, str) and model.startswith("kimi-k2."):
            temperature = 1.0
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=temperature,
            max_tokens=4096,
            timeout=300,
            extra_body={
                "repetition_penalty": 1.1
            }
        )
        
        output = response.choices[0].message.content
        
        # Clean potential markdown blocks
        clean_output = output.strip()
        if clean_output.startswith("```json"):
            clean_output = clean_output[7:]
        if clean_output.endswith("```"):
            clean_output = clean_output[:-3]
        clean_output = clean_output.strip()

        # Validate JSON format and structure
        data = json.loads(clean_output)
        if not isinstance(data, dict):
            raise ValueError("API response is not a valid JSON object")
        
        if 'nodes' not in data or 'edges' not in data:
            raise ValueError("API response missing required 'nodes' or 'edges' fields")
            
        if not isinstance(data['nodes'], list) or not isinstance(data['edges'], list):
            raise ValueError("'nodes' and 'edges' must be arrays")
            
        if len(data['nodes']) < 3:
            raise ValueError("At least 3 nodes are required")
            
        return clean_output
            
    except json.JSONDecodeError as je:
        st.error(f"Invalid JSON format in API response: {str(je)}")
        return '{"nodes": [], "edges": []}'
    except ValueError as ve:
        st.error(str(ve))
        return '{"nodes": [], "edges": []}'
    except Exception as e:
        st.error(f"API call error: {str(e)}")
        return '{"nodes": [], "edges": []}' 
