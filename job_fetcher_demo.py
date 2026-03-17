import re
import json
import asyncio
import subprocess
from dataclasses import dataclass
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

try:
    from langchain_ollama import OllamaLLM
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

LLM_MODEL = "qwen3.5:4b"
MCP_CONFIG_PATH = "mcp_config.json"

@dataclass
class JobInfo:
    job_title: str
    location: str
    department: Optional[str] = None
    job_id: Optional[str] = None

class MCPWebResearchClient:
    def __init__(self):
        self.session = None
        self.tools = []
        self._context = None
    
    async def connect(self):
        if not MCP_AVAILABLE:
            raise ImportError("MCP库未安装，请运行: pip install mcp")
        
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@mzxrai/mcp-webresearch@latest"],
        )
        
        self._context = stdio_client(server_params)
        self.read, self.write = await self._context.__aenter__()
        self.session = ClientSession(self.read, self.write)
        await self.session.__aenter__()
        await self.session.initialize()
        
        response = await self.session.list_tools()
        self.tools = {t.name: t for t in response.tools}
        print(f"已连接 MCP 服务器，可用工具: {list(self.tools.keys())}")
    
    async def disconnect(self):
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if self._context:
                await self._context.__aexit__(None, None, None)
        except Exception:
            pass
    
    async def search_google(self, query: str) -> str:
        if not self.session:
            raise RuntimeError("MCP 未连接")
        
        if "search_google" not in self.tools:
            raise RuntimeError("search_google 工具不可用")
        
        print(f"使用 MCP 工具: search_google")
        
        result = await self.session.call_tool("search_google", {"query": query})
        
        if result.content:
            return "".join([c.text for c in result.content if hasattr(c, 'text')])
        return ""
    
    async def visit_page(self, url: str) -> str:
        if not self.session:
            raise RuntimeError("MCP 未连接")
        
        if "visit_page" not in self.tools:
            raise RuntimeError("visit_page 工具不可用")
        
        print(f"使用 MCP 工具: visit_page")
        print(f"访问 URL: {url}")
        
        result = await self.session.call_tool("visit_page", {"url": url})
        
        if result.content:
            return "".join([c.text for c in result.content if hasattr(c, 'text')])
        return ""
    
    async def search_and_extract_jobs(self, keyword: str) -> str:
        search_url = f"https://jobs.bytedance.com/campus/position?keywords={keyword}&project=7525009396952582407&limit=10"
        
        content = await self.visit_page(search_url)
        
        return content

class ByteDanceJobFetcher:
    def __init__(self, use_llm: bool = True, use_mcp: bool = True):
        self.use_llm = use_llm and LLM_AVAILABLE
        self.use_mcp = use_mcp and MCP_AVAILABLE
        self.mcp_client = None
        
        if self.use_llm:
            try:
                self.llm = OllamaLLM(model=LLM_MODEL)
            except Exception as e:
                print(f"LLM初始化失败: {e}")
                self.use_llm = False
    
    async def init_mcp(self):
        if self.use_mcp:
            self.mcp_client = MCPWebResearchClient()
            await self.mcp_client.connect()
    
    async def close_mcp(self):
        if self.mcp_client:
            await self.mcp_client.disconnect()
    
    def parse_jobs_from_text(self, content: str) -> List[JobInfo]:
        jobs = []
        
        cities = ['北京', '上海', '深圳', '杭州', '广州', '成都', '武汉', '南京', '西安', 
                  '苏州', '厦门', '重庆', '天津', '长沙', '郑州', '青岛', '大连', '宁波']
        
        pattern = r'([^\n]{5,80}?)(北京|上海|深圳|杭州|广州|成都|武汉|南京|西安|苏州|厦门|重庆|天津|长沙|郑州|青岛|大连|宁波)(正式|实习)'
        
        matches = re.findall(pattern, content)
        
        for match in matches:
            job_title_raw = match[0].strip()
            location = match[1]
            
            job_title = re.sub(r'^\d+[、\.]?\s*', '', job_title_raw)
            job_title = re.sub(r'职位\s*ID[:：]?\s*\w+', '', job_title).strip()
            job_title = re.sub(r'\s+', '', job_title)
            
            if len(job_title) > 5 and ('工程师' in job_title or '经理' in job_title or '专员' in job_title or '产品' in job_title):
                dept_match = re.search(r'[-—](.+?)(?=' + '|'.join(cities) + ')', job_title_raw)
                department = dept_match.group(1).strip() if dept_match else None
                
                jobs.append(JobInfo(
                    job_title=job_title,
                    location=location,
                    department=department
                ))
        
        seen = set()
        unique_jobs = []
        for job in jobs:
            key = (job.job_title, job.location)
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs
    
    def parse_jobs_with_llm(self, raw_content: str) -> List[JobInfo]:
        if not self.use_llm:
            return []
        
        template = """
从以下网页内容中提取职位信息。

网页内容：
{content}

请提取所有职位信息，每行输出一个职位，格式如下（用|分隔）：
职位名称|城市|部门

例如：
大模型应用开发工程师|北京|风控研发团队
前端开发工程师|深圳|抖音团队

只输出职位列表，不要其他说明。
"""
        
        try:
            prompt = ChatPromptTemplate.from_template(template)
            chain = prompt | self.llm | StrOutputParser()
            
            max_content = raw_content[:5000] if len(raw_content) > 5000 else raw_content
            
            print("正在调用 LLM 解析...")
            result = chain.invoke({"content": max_content})
            print(f"LLM 返回内容长度: {len(result)} 字符")
            
            jobs = []
            lines = result.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('例如') or line.startswith('只输出'):
                    continue
                
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        job_title = parts[0].strip()
                        location = parts[1].strip() if len(parts) > 1 else None
                        department = parts[2].strip() if len(parts) > 2 else None
                        
                        if job_title and len(job_title) > 3:
                            jobs.append(JobInfo(
                                job_title=job_title,
                                location=location if location and location != '-' else None,
                                department=department if department and department != '-' else None
                            ))
            
            print(f"LLM 解析到 {len(jobs)} 个职位")
            return jobs
        except Exception as e:
            print(f"LLM解析失败: {e}")
            import traceback
            traceback.print_exc()
        
        return []
    
    async def fetch_via_mcp(self, keyword: str) -> str:
        if not self.mcp_client:
            await self.init_mcp()
        
        return await self.mcp_client.search_and_extract_jobs(keyword)
    
    async def fetch_and_parse_async(self, keyword: str = "大模型应用") -> List[JobInfo]:
        print(f"正在获取职位信息: {keyword}")
        
        if self.use_mcp:
            try:
                print("使用 MCP Web Research 获取网页内容...")
                await self.init_mcp()
                content = await self.fetch_via_mcp(keyword)
                
                if content:
                    print(f"MCP 获取到内容 ({len(content)} 字符)")
                    
                    print("尝试从文本解析职位...")
                    jobs = self.parse_jobs_from_text(content)
                    
                    if jobs:
                        await self.close_mcp()
                        return jobs
                    
                    if self.use_llm:
                        print("尝试使用LLM解析...")
                        result = self.parse_jobs_with_llm(content)
                        await self.close_mcp()
                        return result
                    
                    await self.close_mcp()
                    return []
                
                await self.close_mcp()
            except Exception as e:
                print(f"MCP 获取失败: {e}")
                try:
                    await self.close_mcp()
                except Exception:
                    pass
        
        return []
    
    def fetch_and_parse(self, keyword: str = "大模型应用") -> List[JobInfo]:
        return asyncio.run(self.fetch_and_parse_async(keyword))

def print_jobs_table(jobs: List[JobInfo]):
    print("\n" + "=" * 80)
    print(f"{'序号':<4} {'职位名称':<40} {'工作地点':<10} {'部门':<20}")
    print("=" * 80)
    
    for i, job in enumerate(jobs, 1):
        title = job.job_title[:38] if job.job_title and len(job.job_title) > 38 else (job.job_title or "-")
        location = job.location or "-"
        dept = job.department[:18] if job.department and len(job.department) > 18 else (job.department or "-")
        print(f"{i:<4} {title:<40} {location:<10} {dept:<20}")
    
    print("=" * 80)
    print(f"共找到 {len(jobs)} 个职位\n")

def print_jobs_json(jobs: List[JobInfo]):
    jobs_dict = [
        {
            "job_title": job.job_title,
            "location": job.location,
            "department": job.department,
            "job_id": job.job_id
        }
        for job in jobs
    ]
    print("\n结构化JSON输出:")
    print(json.dumps(jobs_dict, ensure_ascii=False, indent=2))

def check_dependencies():
    print("检查依赖...")
    print(f"  - LLM (langchain_ollama): {'✓' if LLM_AVAILABLE else '✗'}")
    print(f"  - MCP (mcp): {'✓' if MCP_AVAILABLE else '✗ (pip install mcp)'}")
    print()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="字节跳动职位获取工具 (支持MCP)")
    parser.add_argument("--keyword", "-k", default="大模型应用", help="搜索关键词")
    parser.add_argument("--json", "-j", action="store_true", help="输出JSON格式")
    parser.add_argument("--no-llm", action="store_true", help="禁用LLM解析")
    parser.add_argument("--no-mcp", action="store_true", help="禁用MCP")
    parser.add_argument("--check", "-c", action="store_true", help="检查依赖")
    
    args = parser.parse_args()
    
    if args.check:
        check_dependencies()
        return
    
    fetcher = ByteDanceJobFetcher(use_llm=not args.no_llm, use_mcp=not args.no_mcp)
    
    jobs = fetcher.fetch_and_parse(args.keyword)
    
    if jobs:
        print_jobs_table(jobs)
        if args.json:
            print_jobs_json(jobs)
    else:
        print("未找到职位信息")

if __name__ == "__main__":
    main()
