from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.config import settings


class LLMService:
    def __init__(self):
        self.llm = OllamaLLM(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL
        )
        self.embeddings = OllamaEmbeddings(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL
        )
    
    def chat(self, message: str, context: str = "") -> str:
        template = """
你是一个专业的求职助手，帮助用户分析简历、推荐职位、优化简历内容。

{context}

用户消息: {message}

请给出专业、有帮助的回复:
"""
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()
        
        return chain.invoke({"message": message, "context": context})
    
    def analyze_resume(self, resume_content: str) -> str:
        template = """
请分析以下简历内容，提取关键信息并以JSON格式输出：

简历内容:
{resume}

请提取以下信息（JSON格式）：
- name: 姓名
- phone: 电话
- email: 邮箱
- skills: 技能列表，必须为数组
- experience: 工作经验或实习经历摘要
- education: 学历或教育背景
- location: 期望工作地点，没有则为空字符串
- summary: 个人简介或优势总结
- target_positions: 目标职位列表，必须为数组

输出要求：
1. 只输出 JSON，不要其他内容。
2. 如果某字段缺失，字符串字段返回 ""，数组字段返回 []。
3. 不要生成 Markdown。
"""
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()
        
        result = chain.invoke({"resume": resume_content})
        return result
    
    def get_embeddings(self, text: str) -> list:
        return self.embeddings.embed_query(text)


llm_service = LLMService()
