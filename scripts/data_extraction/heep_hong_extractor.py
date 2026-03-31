import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

# Try to import google-generativeai, but fail gracefully if not installed
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HeepHongExtractor")

# Ensure .env is loaded if available
try:
    from dotenv import load_dotenv
    load_dotenv("gemini.env")
except ImportError:
    pass

class HeepHongOntologyExtractor:
    """
    Extracts structured knowledge graph data from unstructured 
    Heep Hong Society training guide text.
    """
    
    SYSTEM_PROMPT = """
你是一个顶级的“特殊教育临床数据架构师”和知识图谱构建专家。
你的任务是将提供的《学前儿童训练指南（协康会）》非结构化文本，精准提取并映射为符合严格层级关系（Ontology）的 JSON 数组结构。

【背景与层级定义】
这份资料包含从宏观领域到微观干预剧本的嵌套结构。你必须严格识别并分类为以下 6 个层级（Level）：
- L1 (次范畴/Sub-domain)：如“语言表达”、“语言理解”。
- L2 (学习重点/Focus Area)：L1下的分支，如“发声能力”、“词汇运用”、“语言思考”。
- L3 (项目/目标/Target)：L2下的具体项目，通常带有编号，如“项目一：发出不同的声音”。
- L4 (里程碑/Milestone)：具体的发育指标，通常附带年龄段，如“发出哭声 (0-6个月)”。
- L5 (干预剧本/Intervention Script)：针对L4给出的具体活动建议、操作手法、训练游戏。这是大模型未来指导家长的 Prompt 语料。
- L6 (材料/Material)：执行L5活动所需要的具体教具、玩具或物品。

【提取规则 - 极其重要】
1. 保持父子关系绝对准确：JSON 数组必须扁平化输出，每个节点通过 `parent_name` 字段指向其直接上级节点的 `name`。
2. 缺失层级自动推导：有时文本会跳过某个层级（比如 L3 下直接写了 L5 的游戏），你必须根据上下文维持层级树的完整性，必要时保留层级但设为空。
3. 年龄范围解析：当 L4 节点出现年龄时（如“9-18个月”、“2岁”），必须将其解析为整型的 `age_min_months` 和 `age_max_months`。若只有上限则 min 为 0；若无年龄说明则设为 null。
4. L5 语料完整性：干预剧本（L5）的内容必须一字不落地保留，不要做任何总结或缩写，这是临床语料的灵魂。
5. 分离材料：从 L5 的文本中，将提及的物理实体（如“发声玩具”、“镜子”、“薯片罐”）单独提取为 L6 节点。

【输出格式】
你只能输出合法的 JSON 数组，不能包含任何 Markdown 标记、解释或多余的文字。严格使用以下 Schema：
[
  {
    "name": "节点完整名称",
    "level": "L1/L2/L3/L4/L5/L6",
    "parent_name": "直接父节点的完整名称",
    "age_min_months": null或整数 (仅适用于L4),
    "age_max_months": null或整数 (仅适用于L4),
    "prompt_corpus": "干预活动的完整描述内容" (仅适用于L5, 其他层级为空字符串)
  }
]
"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the extractor with optional API key"""
        if not GENAI_AVAILABLE:
            logger.warning("google-generativeai is not installed. LLM extraction will not work.")
            return

        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            # Try to get from os.environ first, then check if gemini.env is loaded
            api_key = os.environ.get("GEMINI_API_KEY")
            
        if not api_key:
            logger.warning("No GEMINI_API_KEY found. Please set the environment variable.")
        else:
            genai.configure(api_key=api_key)
            # Use gemini-2.5-pro or 1.5-pro for complex extraction tasks
            self.model = genai.GenerativeModel(
                model_name="gemini-3.1-pro-preview",
                system_instruction=self.SYSTEM_PROMPT,
                generation_config={
                    "temperature": 0.1,  # Low temperature for more deterministic extraction
                    "response_mime_type": "application/json",
                }
            )
            
    def validate_extraction(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates the extracted nodes to ensure structural integrity:
        1. All parent_names must resolve to an existing name (except for L1 roots)
        2. Validates types and required fields
        """
        errors = []
        node_names = {node.get("name") for node in nodes}
        
        for i, node in enumerate(nodes):
            name = node.get("name")
            level = node.get("level")
            parent_name = node.get("parent_name")
            
            # 1. Required fields
            if not name:
                errors.append(f"Node {i} is missing 'name'")
                continue # Skip further checks if name is missing
                
            if level not in ["L1", "L2", "L3", "L4", "L5", "L6"]:
                errors.append(f"Node '{name}' has invalid level: {level}")
                
            # 2. Parent-child integrity check
            if level != "L1" and parent_name:
                if parent_name not in node_names:
                    errors.append(f"Broken link: Node '{name}' references missing parent '{parent_name}'")
            elif level == "L1" and parent_name:
                # Assuming L1 roots might not have parents in this specific chunk
                pass 
                
            # 3. Content validations
            if level == "L5":
                if not node.get("prompt_corpus"):
                    errors.append(f"L5 Node '{name}' is missing 'prompt_corpus'")
            else:
                if node.get("prompt_corpus"):
                    errors.append(f"Non-L5 Node '{name}' has 'prompt_corpus' populated (should be empty)")
                    
            if level == "L4":
                # Ensure age bounds are integers or null
                min_age = node.get("age_min_months")
                max_age = node.get("age_max_months")
                if min_age is not None and not isinstance(min_age, int):
                    errors.append(f"L4 Node '{name}' age_min_months must be int or null")
                if max_age is not None and not isinstance(max_age, int):
                    errors.append(f"L4 Node '{name}' age_max_months must be int or null")
                    
        if errors:
            for error in errors:
                logger.error(f"Validation Error: {error}")
            return {"valid": False, "errors": errors, "data": nodes}
            
        return {"valid": True, "errors": [], "data": nodes}

    def clean_json_response(self, text: str) -> str:
        """Removes markdown formatting if the model accidentally includes it."""
        # Remove markdown code block syntax if present
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return text

    def extract_from_text(self, text_chunk: str, current_path: str = "") -> Dict[str, Any]:
        """
        Extracts structured data from a single text chunk.
        
        Args:
            text_chunk: The markdown text to process
            current_path: Context path like "语言 -> 语言表达 -> 词汇运用" to help the LLM
        """
        if not hasattr(self, 'model'):
            logger.error("Model not initialized. Check API key and dependencies.")
            return {"valid": False, "errors": ["Model not initialized"], "data": None}
            
        user_prompt = f"""
请处理以下协康会文本切片。
当前上下文路径为：[{current_path}]

文本内容：
\"\"\"
{text_chunk}
\"\"\"
"""
        logger.info(f"Sending chunk to model (Context: {current_path})")
        
        try:
            response = self.model.generate_content(user_prompt)
            raw_text = response.text
            
            clean_text = self.clean_json_response(raw_text)
            
            try:
                extracted_data = json.loads(clean_text)
                
                # Run local validation
                validation_result = self.validate_extraction(extracted_data)
                
                if not validation_result["valid"]:
                    logger.warning(f"Extracted data has validation errors.")
                else:
                    logger.info(f"Successfully extracted {len(extracted_data)} valid nodes.")
                    
                # Add raw text to the result for debugging
                validation_result["raw_response"] = raw_text
                return validation_result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Raw response: {raw_text}")
                return {"valid": False, "errors": [f"JSON parsing error: {str(e)}"], "data": None, "raw_response": raw_text}
                
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return {"valid": False, "errors": [f"API Error: {str(e)}"], "data": None}

    def run_sample(self):
        """Runs a sample extraction to test the prompt and logic."""
        sample_text = """
项目一：发出不同的声音
发出哭声 (0-6个月)
活动一：诱发发声
家长可以在婴儿清醒、情绪稳定时，用手轻轻抚摸他的身体，或者用带有声音的玩具（如摇铃）吸引他的注意力，鼓励他发出声音。
"""
        print("Running sample extraction...")
        result = self.extract_from_text(sample_text, "语言 -> 语言表达 -> 发声能力")
        print(json.dumps(result, indent=2, ensure_ascii=False))

# Example usage string if run directly
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract ontology from Heep Hong text")
    parser.add_argument("--sample", action="store_true", help="Run a sample extraction")
    args = parser.parse_args()
    
    if args.sample:
        extractor = HeepHongOntologyExtractor()
        extractor.run_sample()
    else:
        print("This script provides the HeepHongOntologyExtractor class.")
        print("To use it, import it and provide a Gemini API key.")
        print("\nExample usage:")
        print("from scripts.data_extraction.heep_hong_extractor import HeepHongOntologyExtractor")
        print("extractor = HeepHongOntologyExtractor(api_key='YOUR_API_KEY')")
        print("result = extractor.extract_from_text(chunk_text, current_path='语言 -> 语言表达')")
        print("print(json.dumps(result, indent=2, ensure_ascii=False))")
        print("\nRun with --sample to test with a small sample text.")
