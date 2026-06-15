# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

SENSENOVA_API_KEY = os.environ.get("API_KEY", "")

REQUEST_TIMEOUT = 15
MAX_RETRY = 3
CRAWL_DELAY = 1
MAX_PAGES = 3
MAX_TEXT_LEN = 4000
MAX_RAW_LEN = 3000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRY,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def _safe_get(session: requests.Session, url: str) -> Optional[str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.RequestException as e:
        log.warning("请求失败 %s: %s", url, e)
        return None


def _extract_content(soup: BeautifulSoup) -> Optional[str]:
    """通用内容提取：尝试多种常见的文章容器"""
    for selector in [
        ("article", None),
        ("div", {"class_": "entry-content"}),
        ("div", {"class_": "article-content"}),
        ("div", {"class_": "post-content"}),
        ("div", {"class_": "content"}),
        ("div", {"class_": "main"}),
    ]:
        tag, attrs = selector[0], selector[1] if len(selector) > 1 else None
        el = soup.find(tag, **(attrs or {}))
        if el:
            text = el.get_text(strip=True)
            text = re.sub(r"\s+", " ", text)
            if len(text) > 50:
                return text[:1500]
    return None


def crawl_hanchacha(lesson_name: str, session: requests.Session) -> str:
    """从 hanchacha.com 爬取所有相关资料"""
    log.info("正在从 hanchacha.com 搜索《%s》...", lesson_name)

    all_parts: list[str] = []
    search_url = f"https://hanchacha.com/?s={lesson_name}"
    html = _safe_get(session, search_url)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    found_urls: list[str] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text().lower()
        if lesson_name.lower() in text and "hanchacha.com" in href:
            if href not in found_urls:
                found_urls.append(href)

    log.info("  hanchacha: 找到 %d 个相关页面", len(found_urls))

    for url in found_urls[:MAX_PAGES]:
        time.sleep(CRAWL_DELAY)
        page_html = _safe_get(session, url)
        if not page_html:
            continue
        page_soup = BeautifulSoup(page_html, "html.parser")
        content = _extract_content(page_soup)
        if content:
            all_parts.append(content)

    return "\n\n---\n".join(all_parts)


def crawl_ruiwen(lesson_name: str, session: requests.Session) -> str:
    """从 ruiwen.com 爬取教学资源"""
    log.info("正在从 ruiwen.com 搜索《%s》...", lesson_name)

    all_parts: list[str] = []
    search_url = f"https://www.ruiwen.com/search/?q={lesson_name}"
    html = _safe_get(session, search_url)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    found_urls: list[str] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text().lower()
        full_url = urljoin("https://www.ruiwen.com", href)
        if lesson_name.lower() in text and "ruiwen.com" in full_url:
            if full_url not in found_urls:
                found_urls.append(full_url)

    log.info("  ruiwen: 找到 %d 个相关页面", len(found_urls))

    for url in found_urls[:MAX_PAGES]:
        time.sleep(CRAWL_DELAY)
        page_html = _safe_get(session, url)
        if not page_html:
            continue
        page_soup = BeautifulSoup(page_html, "html.parser")
        content = _extract_content(page_soup)
        if content:
            all_parts.append(content)

    return "\n\n---\n".join(all_parts)


def crawl_zxxk(lesson_name: str, session: requests.Session) -> str:
    """从 zxxk.com 爬取学科资源"""
    log.info("正在从 zxxk.com 搜索《%s》...", lesson_name)

    all_parts: list[str] = []
    search_url = f"https://www.zxxk.com/search/?keyword={lesson_name}&category=0&grade=0&subject=1"
    html = _safe_get(session, search_url)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    found_urls: list[str] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text().lower()
        full_url = urljoin("https://www.zxxk.com", href)
        if lesson_name.lower() in text and "zxxk.com" in full_url:
            if full_url not in found_urls:
                found_urls.append(full_url)

    log.info("  zxxk: 找到 %d 个相关页面", len(found_urls))

    for url in found_urls[:MAX_PAGES]:
        time.sleep(CRAWL_DELAY)
        page_html = _safe_get(session, url)
        if not page_html:
            continue
        page_soup = BeautifulSoup(page_html, "html.parser")
        content = _extract_content(page_soup)
        if content:
            all_parts.append(content)

    return "\n\n---\n".join(all_parts)


def crawl_all(lesson_name: str) -> str:
    """从多个网站爬取资料并合并"""
    session = _build_session()

    sources = [
        ("hanchacha", crawl_hanchacha),
        ("ruiwen", crawl_ruiwen),
        ("zxxk", crawl_zxxk),
    ]

    all_results: list[str] = []
    for name, crawl_fn in sources:
        try:
            result = crawl_fn(lesson_name, session)
            if result:
                all_results.append(f"[来源: {name}]\n{result}")
        except Exception as e:
            log.warning("  %s 爬取异常: %s", name, e)

    combined = "\n\n===\n\n".join(all_results)
    log.info("共爬取 %d 个来源，总长度 %d 字", len(all_results), len(combined))
    return combined[:MAX_TEXT_LEN]


def generate_with_ai(lesson_name: str, raw_materials: str) -> str:
    """使用 AI 生成详细的学霸笔记"""
    log.info("AI 状态: %s", "已启用" if SENSENOVA_API_KEY else "未配置")

    if not SENSENOVA_API_KEY:
        return _generate_fallback_note(lesson_name, raw_materials)

    prompt = _build_prompt(lesson_name, raw_materials)

    try:
        log.info("正在调用 SenseNova API...")
        resp = requests.post(
            "https://token.sensenova.cn/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {SENSENOVA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sensenova-6.7-flash-lite",
                "messages": [
                    {"role": "system", "content": "你是小学语文特级教师，擅长写超详细、超专业的课文笔记。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 4500,
            },
            timeout=90,
        )
        resp.raise_for_status()
        note = resp.json()["choices"][0]["message"]["content"]
        log.info("AI 生成成功，笔记长度: %d 字", len(note))
        return note
    except Exception as e:
        log.warning("AI 调用异常: %s", e)
        return _generate_fallback_note(lesson_name, raw_materials)


def _build_prompt(lesson_name: str, raw_materials: str) -> str:
    return f"""你是小学语文特级教师。请为课文《{lesson_name}》生成一份超级详细的学霸笔记。

【要求】
1. 必须像下面示例一样详细、专业
2. 每个表格都要填满具体内容
3. 写出具体的词语、句子、分析、写作技巧
4. 绝对不能留空或用"请根据课文填写"

【参考详细程度】：
《海底世界》示例：
- 课文简介：科普性说明文，从环境、动物、植物、矿产四方面介绍
- 文章结构：表格（部分、自然段、内容、作用）
- 写作特色：对比+拟人，有具体例子和写作小技巧
- 词语积累：必会字词、近义词、反义词、AABC式词语
- 仿写句式：有的...有的...有的...，有原句和仿写
- 课后挑战：3个具体任务

请按以下格式输出：

# 🌊 探秘{lesson_name} · 学霸综合笔记 🐠

> 一份集**知识点、课堂笔记、教学思路**于一体的超实用手册

---

## 📚 一、课文一瞥：它讲了什么？

（写具体内容）

*   **核心问题**：
*   **主要内容**：
*   **中心句**：

---

## 🧱 二、文章结构：总分总，超清晰！

| 部分 | 自然段 | 内容 | 作用 |
|------|--------|------|------|
| 开头 | | | |
| 中间 | | | |
| 结尾 | | | |

> 💡 **写作要点：**

---

## ✨ 三、阅读与写作：深挖课文"宝藏"

### 写作特色分析

| 阅读要点 | 写法分析 | 写作小技巧 |
|----------|----------|------------|
| | | |
| | | |
| | | |

> 💡 **写作要点：**

---

## 📝 四、语言积累：词语库+句式库

### 重点词语

| 类别 | 词语 |
|------|------|
| 必会字词 | |
| 近义词 | |
| 反义词 | |
| 成语/AABC | |

### 仿写句式

> **句式名称**
>
> *   **课文原句**：
> *   **仿写示例**：

---

## 🎯 五、课后挑战：小试牛刀

1. **朗读小能手**：
2. **小小解说员**：
3. **妙笔生花**：

---

【参考资料】
{raw_materials[:MAX_RAW_LEN]}

请直接输出笔记，不要输出解释。"""


def _generate_fallback_note(lesson_name: str, raw_materials: str) -> str:
    content = raw_materials[:500] if raw_materials else f"《{lesson_name}》是一篇优美的课文。"
    return f"""# 📖 {lesson_name} · 学习笔记

> 正在努力生成中...

---

## 📚 课文内容

{content}

---

## 📝 学习建议

1. 朗读课文3遍
2. 标出生字词
3. 思考课文主要内容

---

*生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}*
"""


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python crawler.py <课文名称>")
        sys.exit(1)

    lesson_name = sys.argv[1]
    log.info("=" * 50)
    log.info("正在为《%s》生成笔记...", lesson_name)
    log.info("SenseNova API: %s", "已配置" if SENSENOVA_API_KEY else "未配置")
    log.info("=" * 50)

    raw = crawl_all(lesson_name)
    note = generate_with_ai(lesson_name, raw)

    os.makedirs("data", exist_ok=True)
    output_file = f"data/{lesson_name}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(note)

    log.info("笔记已保存: %s", output_file)


if __name__ == "__main__":
    main()
