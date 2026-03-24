from html import unescape
import json
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.models.models import CompanyLink, Position
from app.services.llm_service import llm_service

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:
    PlaywrightTimeoutError = Exception
    sync_playwright = None


class JobCrawlerService:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    JOB_KEYWORDS = (
        "职位",
        "岗位",
        "招聘",
        "工作地点",
        "任职要求",
        "岗位职责",
        "校招",
        "社招",
        "实习",
        "工程师",
        "开发",
        "算法",
        "产品",
        "测试",
        "运营",
    )
    PAGINATION_LABELS = ("下一页", "下页", "next", "more", "加载更多", "更多职位")
    PREFERRED_API_PATTERNS = (
        "searchposition",
        "/position/search",
        "/positions/search",
        "/job/search",
        "/jobs/search",
        "/position/list",
        "/jobs/list",
        "/campus/position",
        "/recruit/position",
    )
    REJECT_API_PATTERNS = (
        "dictionary",
        "config",
        "filter",
        "family",
        "positionfamily",
        "postfamily",
        "category",
        "city",
        "workcity",
        "workcities",
        "locationlist",
        "enum",
        "metadata",
        "projectlist",
        "postlist",
    )
    LLM_REVIEW_LIMIT = 5

    def is_rejected_api(self, url: str) -> bool:
        url_lower = (url or "").lower()
        return any(token in url_lower for token in self.REJECT_API_PATTERNS)

    def score_job_api_candidate(self, url: str, data) -> tuple[int, list[dict]]:
        url_lower = (url or "").lower()
        if self.is_rejected_api(url_lower):
            return -100, []
        
        positions = self.extract_positions_from_json(data, base_url=url)
        score = 0
        if any(pattern in url_lower for pattern in self.PREFERRED_API_PATTERNS):
            score += 50
        if "search" in url_lower or "list" in url_lower:
            score += 20
        if "position" in url_lower or "job" in url_lower:
            score += 20
            
        if positions:
            score += 30 + min(len(positions), 20) * 2
            if self.looks_like_real_job_list(positions, base_url=url):
                score += 50
        else:
            score -= 30

        return score, positions

    def looks_like_real_job_list(self, positions: list[dict], base_url: str = "") -> bool:
        if not positions:
            return False

        sample = positions[: min(len(positions), 10)]
        rich_items = 0
        detail_links = 0
        filled_locations = 0
        filled_descriptions = 0

        for item in sample:
            extras = 0
            if item.get("location"):
                filled_locations += 1
                extras += 1
            if item.get("salary"):
                extras += 1
            if item.get("jd"):
                filled_descriptions += 1
                extras += 1
            link = item.get("link")
            if link and link != base_url:
                detail_links += 1
                extras += 1
            if extras >= 1:
                rich_items += 1

        # 城市/枚举接口通常只有 name，没有地点、详情链接、JD 这些职位特征
        if rich_items == 0:
            return False
        if detail_links == 0 and filled_locations == 0 and filled_descriptions == 0:
            return False
        return True

    # 批量判别的方法替换为逐个判别（见后文 fetch_page_payload）
    def review_api_candidates_with_llm(self, candidates: list[dict]) -> list[dict]:
        return candidates

    def normalize_job_item(self, item: dict, base_url: str = "") -> dict | None:
        if not isinstance(item, dict):
            return None

        name_keys = (
            "name",
            "title",
            "positionName",
            "jobName",
            "recruitName",
            "postName",
            "job_name",
            "jobTitle"
        )
        location_keys = (
            "location",
            "city",
            "workLocation",
            "address",
            "jobCity",
            "locationName",
            "cityName",
            "city_list",
            "cityList",
            "city_name"
        )
        salary_keys = ("salary", "salaryDesc", "salaryRange", "pay", "salaryName")
        link_keys = (
            "link",
            "url",
            "positionUrl",
            "jobUrl",
            "applyUrl",
            "redirectUrl",
            "postUrl",
            "pcUrl",
        )
        jd_keys = (
            "jd",
            "description",
            "jobDescription",
            "requirement",
            "responsibility",
            "summary",
            "positionDetail",
            "postDescription",
        )
        id_keys = ("id", "positionId", "postId", "jobId")

        def pick(keys):
            for key in keys:
                value = item.get(key)
                if value is None:
                    continue
                value = str(value).strip()
                if value:
                    return value
            return ""

        name = pick(name_keys)
        if not name:
            return None

        link = pick(link_keys)
        item_id = pick(id_keys)
        if link:
            link = urljoin(base_url, link)
        elif item_id and "join.qq.com" in base_url:
            link = f"https://join.qq.com/post.html?query={item_id}"
        return {
            "name": name,
            "location": pick(location_keys) or None,
            "salary": pick(salary_keys) or None,
            "link": link or base_url or None,
            "jd": pick(jd_keys) or None,
        }

    def extract_positions_from_json(self, data, base_url: str = "") -> list[dict]:
        positions = []

        def walk(node):
            if len(positions) >= 50:
                return
            if isinstance(node, list):
                normalized_batch = [self.normalize_job_item(item, base_url) for item in node]
                normalized_batch = [item for item in normalized_batch if item]
                if normalized_batch:
                    positions.extend(normalized_batch)
                    return
                for item in node:
                    walk(item)
                return
            if isinstance(node, dict):
                normalized = self.normalize_job_item(node, base_url)
                if normalized:
                    positions.append(normalized)
                    return
                for value in node.values():
                    walk(value)

        walk(data)

        unique = []
        seen = set()
        for item in positions:
            signature = (item["name"], item.get("location"), item.get("link"))
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(item)
            if len(unique) >= 20:
                break
        return unique

    def normalize_text(self, raw_text: str) -> str:
        text = unescape(raw_text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def clean_html_soup(self, html: str) -> BeautifulSoup:
        soup = BeautifulSoup(html, "lxml")
        
        # 移除完全无关的标签
        for tag in soup(["script", "style", "noscript", "svg", "path", "head", "meta", "link", "iframe"]):
            tag.decompose()
            
        # 移除常见的非主体布局元素（导航、页眉、页脚、侧边栏等）
        for tag in soup(["nav", "header", "footer", "aside"]):
            tag.decompose()
            
        # 仅限定非常明确的类名/ID，避免误删带有组合 class 的 main container
        exact_ignore_patterns = re.compile(r"^(sidebar|menu|nav|header|footer|pagination)$", re.I)
        
        for tag in soup.find_all(lambda t: t.has_attr('class') and any(exact_ignore_patterns.search(str(c)) for c in t['class'])):
            tag.decompose()
            
        for tag in soup.find_all(lambda t: t.has_attr('id') and exact_ignore_patterns.search(str(t['id']))):
            tag.decompose()
            
        return soup

    def html_to_text(self, html: str) -> str:
        try:
            soup = self.clean_html_soup(html)
            clean_text = soup.get_text(separator=" ", strip=True)
            return self.normalize_text(clean_text)
        except Exception:
            # Fallback to regex if parsing fails
            clean_text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
            clean_text = re.sub(r"<style[\s\S]*?</style>", " ", clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            return self.normalize_text(clean_text)

    def route_resource(self, route) -> None:
        if route.request.resource_type in {"image", "media", "font"}:
            route.abort()
            return
        route.continue_()

    def collect_job_snippets(self, html: str, base_url: str) -> list[str]:
        try:
            soup = self.clean_html_soup(html)
        except Exception:
            soup = BeautifulSoup(html, "lxml")
            
        snippets = []
        seen = set()

        candidates = soup.find_all(["li", "div", "section", "article", "tr", "a"])
        for node in candidates:
            text = self.normalize_text(node.get_text(" ", strip=True))
            if len(text) < 20 or len(text) > 1000:
                continue
            if not any(keyword in text for keyword in self.JOB_KEYWORDS):
                continue

            link = ""
            anchor = node.find("a", href=True)
            if anchor:
                link = urljoin(base_url, anchor["href"])

            snippet = {
                "text": text[:1000],
                "html": str(node)[:2000],
                "link": link,
            }
            signature = f"{snippet['text'][:200]}::{snippet['link']}"
            if signature in seen:
                continue
            seen.add(signature)
            snippets.append(json.dumps(snippet, ensure_ascii=False))
            if len(snippets) >= 30:
                break

        return snippets

    def add_debug_step(self, debug_steps: list[str], message: str, progress_callback=None) -> None:
        debug_steps.append(message)
        if progress_callback:
            progress_callback(debug_steps)

    def click_pagination(self, page, debug_steps: list[str], progress_callback=None) -> bool:
        try:
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            
            # DOM Filtering: find candidate pagination nodes
            pagination_wrappers = soup.find_all(attrs={"class": re.compile(r"(?i)pagination|paging|page")})
            candidates = []
            if pagination_wrappers:
                for wrapper in pagination_wrappers:
                    for a in wrapper.find_all(["a", "button", "span", "li", "div"]):
                        text = self.normalize_text(a.get_text(" ", strip=True))
                        if text and len(text) < 20:
                            candidates.append({"text": text, "tag": a.name})
            else:
                for a in soup.find_all(["a", "button"]):
                    text = self.normalize_text(a.get_text(" ", strip=True))
                    if text and any(keyword in text.lower() for keyword in ["下", "next", "more", ">", "更多"]):
                        candidates.append({"text": text, "tag": a.name})

            unique_candidates = []
            seen = set()
            for c in candidates:
                if c["text"] not in seen and c["text"].strip():
                    seen.add(c["text"])
                    unique_candidates.append(c)

            best_text = None
            if unique_candidates:
                prompt = f"""
You are an assistant finding the "Next Page" or "Load More" button from DOM elements.
Usually it has text like "下一页", "Next", ">", "加载更多", "更多职位".
Return JSON only:
{{
   "best_text": "下一页",
   "confidence": 90
}}
If none look correct, set best_text to null.
Candidates: {json.dumps(unique_candidates[:20], ensure_ascii=False)}
"""
                response = llm_service.chat(prompt)
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    decision = json.loads(response[json_start:json_end])
                    best_text = decision.get("best_text")

            if best_text:
                for exact in [True, False]:
                    try:
                        locator = page.get_by_text(best_text, exact=exact).first
                        if locator.is_visible(timeout=1000):
                            locator.click(timeout=3000)
                            page.wait_for_load_state("domcontentloaded", timeout=8000)
                            time.sleep(1)
                            self.add_debug_step(debug_steps, f"LLM 辅助触发翻页: {best_text}", progress_callback)
                            return True
                    except Exception:
                        pass
        except Exception as e:
            self.add_debug_step(debug_steps, f"LLM 翻页辅助执行出错，切换回退模式", progress_callback)

        # Fallback to predefined keywords
        for label in self.PAGINATION_LABELS:
            locator = page.get_by_text(label).first
            try:
                locator.wait_for(timeout=1500)
                if locator.is_visible():
                    locator.click(timeout=3000)
                    page.wait_for_load_state("domcontentloaded", timeout=8000)
                    time.sleep(1)
                    self.add_debug_step(debug_steps, f"触发预设模式翻页: {label}", progress_callback)
                    return True
            except Exception:
                continue
        return False

    def fetch_page_payload(self, url: str, progress_callback=None) -> dict:
        if sync_playwright is None:
            raise RuntimeError("Playwright is not installed")

        debug_steps = [f"Start crawling with Playwright: {url}"]
        if progress_callback:
            progress_callback(debug_steps)
        api_candidates = []

        def handle_response(response):
            content_type = (response.headers or {}).get("content-type", "").lower()
            response_url = response.url
            if "json" not in content_type and not response_url.lower().endswith(".json"):
                return
            try:
                data = response.json()
            except Exception:
                return
            score, positions = self.score_job_api_candidate(response_url, data)
            if score <= 0:
                return
            api_candidates.append(
                {
                    "url": response_url,
                    "data": data,
                    "score": score,
                    "positions": positions,
                }
            )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=self.USER_AGENT,
                locale="zh-CN",
                viewport={"width": 1440, "height": 2200},
            )
            page = context.new_page()
            page.route("**/*", self.route_resource)
            page.on("response", handle_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                self.add_debug_step(debug_steps, "Page opened and first render completed", progress_callback)
            except PlaywrightTimeoutError:
                self.add_debug_step(debug_steps, "Page open timed out, continue with loaded content", progress_callback)

            for step in range(4):
                page.mouse.wheel(0, 1800)
                time.sleep(1)
                self.add_debug_step(debug_steps, f"Scroll load step {step + 1}", progress_callback)

            pages_html = [page.content()]
            clicked = self.click_pagination(page, debug_steps, progress_callback)
            if clicked:
                for step in range(3):
                    page.mouse.wheel(0, 1800)
                    time.sleep(1)
                    self.add_debug_step(debug_steps, f"Post-pagination scroll step {step + 1}", progress_callback)
                pages_html.append(page.content())

            time.sleep(2)

            context.close()
            browser.close()

        final_html = "\n".join(pages_html)
        page_text = self.html_to_text(final_html)[:20000]
        snippets = self.collect_job_snippets(final_html, url)
        api_positions = []
        api_preview = ""
        api_url = ""
        api_candidates.sort(key=lambda item: item["score"], reverse=True)
        api_candidates = api_candidates[:7] # Only check top 7 to save LLM tokens and time
        
        for candidate in api_candidates:
            if candidate["score"] <= 0:
                continue # strictly ignore poor candidates
                
            preview = json.dumps(candidate["data"], ensure_ascii=False)[:3000]
            if len(candidate["positions"]) == 0:
                continue
                
            prompt = f"""
Please act as an API analyzer. Check the following JSON response text from URL '{candidate["url"]}'.
Is this a real job listing API containing actual job/position records (not dictionary, not purely config)?
Return JSON only:
{{
   "is_job_api": true,
   "confidence": 95,
   "reason": "It contains job titles and locations"
}}

JSON Content Preview:
{preview}
"""
            try:
                response = llm_service.chat(prompt)
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    decision = json.loads(response[json_start:json_end])
                    is_job_api = bool(decision.get("is_job_api"))
                    confidence = int(decision.get("confidence") or 0)
                    reason = decision.get("reason", "")
                    
                    if is_job_api and confidence >= 60:
                        api_positions = candidate["positions"]
                        api_url = candidate["url"]
                        api_preview = preview
                        self.add_debug_step(debug_steps, f"LLM 确认职位获取接口有效: {api_url}", progress_callback)
                        break
                    else:
                        self.add_debug_step(debug_steps, f"LLM 排除非职位接口: {candidate['url']} (原因: {reason})", progress_callback)
            except Exception:
                continue

        if api_positions:
            self.add_debug_step(debug_steps, f"Captured job API response: {api_url}", progress_callback)
            self.add_debug_step(debug_steps, f"Parsed jobs directly from API: {len(api_positions)}", progress_callback)
        self.add_debug_step(debug_steps, f"Page text normalized, length: {len(page_text)}", progress_callback)
        self.add_debug_step(debug_steps, f"Job snippets collected: {len(snippets)}", progress_callback)
        return {
            "api_positions": api_positions,
            "api_response_preview": api_preview,
            "api_url": api_url,
            "page_text": page_text,
            "snippets": snippets,
            "debug_steps": debug_steps,
        }

    def extract_positions(
        self, company_link: CompanyLink, snippets: list[str], page_text: str
    ) -> tuple[list[dict], str]:
        snippet_text = "\n\n".join(snippets[:20])
        fallback_text = page_text[:4000]
        prompt = f"""
You are a job information extraction assistant. Extract jobs for this company and return a JSON array only.

Company: {company_link.company_name}
Entry URL: {company_link.link}
Recruitment type: {company_link.type or "other"}

Use "job snippets" first. Use "page text summary" only as fallback.

Output fields:
- name
- location
- salary
- link
- jd

Rules:
1. Return JSON array only.
2. At most 20 items.
3. If there are no clear jobs, return [].
4. Every item must have name.
5. If link is missing, use {company_link.link}.

Job snippets:
{snippet_text}

Page text summary:
{fallback_text}
"""

        response = llm_service.chat(prompt)
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start < 0 or json_end <= json_start:
            return [], response

        try:
            data = json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            return [], response

        if not isinstance(data, list):
            return [], response

        positions = []
        for item in data[:20]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            positions.append(
                {
                    "name": name,
                    "location": str(item.get("location", "")).strip() or None,
                    "salary": str(item.get("salary", "")).strip() or None,
                    "link": str(item.get("link", "")).strip() or company_link.link,
                    "jd": str(item.get("jd", "")).strip() or None,
                }
            )
        return positions, response

    def prepare_crawl_result(self, company_link: CompanyLink, progress_callback=None) -> dict:
        payload = self.fetch_page_payload(company_link.link, progress_callback)
        debug_steps = payload["debug_steps"]
        api_positions = payload.get("api_positions", [])
        snippets = payload["snippets"]
        page_text = payload["page_text"]

        llm_raw_response = ""
        if api_positions:
            positions = api_positions
            self.add_debug_step(debug_steps, "Skipped LLM extraction because API data was available", progress_callback)
            llm_raw_response = payload.get("api_response_preview", "")
        else:
            positions, llm_raw_response = self.extract_positions(company_link, snippets, page_text)
            self.add_debug_step(debug_steps, f"LLM extraction completed, jobs found: {len(positions)}", progress_callback)

        if not positions:
            self.add_debug_step(debug_steps, "No valid jobs parsed from snippets", progress_callback)
            return {
                "message": "No job information was parsed from the page",
                "debug_steps": debug_steps,
                "page_text_preview": page_text[:3000],
                "llm_raw_response": llm_raw_response[:5000] if llm_raw_response else "",
                "extracted_positions": [],
            }

        return {
            "message": f"Crawl completed, parsed {len(positions)} jobs",
            "debug_steps": debug_steps,
            "page_text_preview": page_text[:3000],
            "llm_raw_response": llm_raw_response[:5000] if llm_raw_response else "",
            "extracted_positions": positions,
        }

    def upsert_positions(self, db, company_link: CompanyLink, positions: list[dict]) -> tuple[int, int]:
        inserted = 0
        updated = 0

        for item in positions:
            existing = db.query(Position).filter(
                Position.company == company_link.company_name,
                Position.name == item["name"],
                Position.location == item["location"],
            ).first()

            if existing:
                existing.jd = item["jd"] or existing.jd
                existing.salary = item["salary"] or existing.salary
                existing.link = item["link"] or existing.link
                existing.source = company_link.type or existing.source or "company_link_crawl"
                updated += 1
                continue

            db.add(
                Position(
                    name=item["name"],
                    location=item["location"],
                    jd=item["jd"],
                    salary=item["salary"],
                    link=item["link"],
                    company=company_link.company_name,
                    source=company_link.type or "company_link_crawl",
                )
            )
            inserted += 1

        return inserted, updated


job_crawler_service = JobCrawlerService()
