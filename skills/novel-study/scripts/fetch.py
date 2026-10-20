#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
novel-study 采集层（collector）。

契约见 ../CONTRACT.md，本文件只依赖 Python 标准库。

子命令：
    search "书名" [--platform fanqie|tianxi|qidian|all] [--json]
    info   --source fanqie --book-id 7143038691944959011 [--json]
    book   --source fanqie --book-id 7143038691944959011 --from 1 --to 10 [--outdir DIR] [--json]

源适配可插拔：新源实现 Source 接口并注册到 SOURCES。

番茄正文有字体反爬（私有区码位 + 自定义 woff2）。本文件内置了当前线上字体
（awesome-font/c/dc027189e0ba4cd）的码位→字符映射作为 bootstrap；遇到新字体
时会下载子集字体并尝试用参考字体（SourceHanSansSC-Normal）的轮廓做匹配重建映射。
参考字体只在需要重建时下载，缓存在 .cache/novel-study/fonts/。
"""

from __future__ import annotations

import argparse
import glob
import html as htmlmod
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(SKILL_DIR))

DEFAULT_OUTDIR = os.environ.get("NOVEL_STUDY_CACHE") or os.path.join(PROJECT_ROOT, ".cache", "novel-study", "books")
FONT_DIR = os.path.join(PROJECT_ROOT, ".cache", "novel-study", "fonts")

UA_PC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

TIMEOUT = 25
MAX_RETRY = 3
RATE_MIN, RATE_MAX = 0.8, 1.5

# 正文里常见的站点广告/导航行，清洗时整行丢弃
AD_LINE_PATTERNS = [
    r"本章未完[，,]?\s*请点击下一页继续阅读",
    r"请点击下一页继续阅读",
    r"点击下一页继续阅读",
    r"本章未完",
    r"手机版阅读网址",
    r"最新网址[:：]",
    r"请记住本书首发域名",
    r"天才一秒记住",
    r"百度搜索[^\n]{0,30}(小说|网站)",
    r"喜欢[^\n]{2,20}请收藏",
    r"加入书签[,，]?方便下次阅读",
    r"章节错误[，,]?\s*点此举报",
    r"^\s*[（(]?本章完[）)]?\s*$",
    r"^\s*第[一二三四五六七八九十百千0-9]+页\s*$",
    r"^\s*(上一章|下一章|目录|加入书签|返回书页)\s*$",
]
AD_LINE_RE = re.compile("|".join(AD_LINE_PATTERNS), re.IGNORECASE)


def log(msg: str) -> None:
    """日志一律走 stderr，保证 --json 时 stdout 只有 JSON。"""
    print(msg, file=sys.stderr, flush=True)


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def book_key(source: str, book_id: str) -> str:
    return f"{source}-{book_id}"


# ---------------------------------------------------------------------------
# HTTP：限速 + 超时 + 重试
# ---------------------------------------------------------------------------

class FetchError(RuntimeError):
    pass


class Http:
    def __init__(self, timeout: int = TIMEOUT, retries: int = MAX_RETRY,
                 rate=(RATE_MIN, RATE_MAX)):
        self.timeout = timeout
        self.retries = retries
        self.rate = rate
        self._last = 0.0
        self._opener = urllib.request.build_opener()
        self.cookie = self._load_cookie()

    @staticmethod
    def _load_cookie() -> str:
        """登录态：优先环境变量 NOVEL_COOKIE，其次 .cache/novel-study/cookie.txt。

        番茄未登录只能看前 10 章，登录后 cookie 必须带上才能取完整正文。
        cookie 只存仓库外的缓存目录，不进 git。
        """
        c = os.environ.get("NOVEL_COOKIE", "").strip()
        if c:
            return c
        # scripts/fetch.py -> novel-study -> skills -> 写点小说
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        path = os.path.join(root, ".cache", "novel-study", "cookie.txt")
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return ""

    def _throttle(self) -> None:
        delay = random.uniform(*self.rate)
        wait = self._last + delay - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def get(self, url: str, headers: dict | None = None, binary: bool = False):
        hdrs = {
            "User-Agent": UA_PC,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if headers:
            hdrs.update(headers)
        if self.cookie and "fanqienovel.com" in url:
            hdrs.setdefault("Cookie", self.cookie)
        last_err = None
        for attempt in range(1, self.retries + 1):
            self._throttle()
            req = urllib.request.Request(url, headers=hdrs)
            try:
                with self._opener.open(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                return raw if binary else raw.decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code} {url}"
                if e.code in (403, 404, 410):
                    break  # 不重试
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = f"{type(e).__name__}: {e} ({url})"
            if attempt < self.retries:
                time.sleep(1.2 * attempt + random.random())
        raise FetchError(f"请求失败（已重试{self.retries}次）：{last_err}")


HTTP = Http()


# ---------------------------------------------------------------------------
# 原子写 / 目录
# ---------------------------------------------------------------------------

def atomic_write(path: str, data) -> None:
    if isinstance(data, str):
        data = data.encode("utf-8")
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 文本清洗
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_P_RE = re.compile(r"</\s*p\s*>", re.IGNORECASE)


def clean_html_content(content: str) -> str:
    """把章节 HTML 转成纯文本：段落换行、去标签、去广告行、压空行。"""
    if not content:
        return ""
    text = _BR_RE.sub("\n", content)
    text = _P_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = htmlmod.unescape(text)

    lines = []
    for line in text.splitlines():
        s = line.replace("\u3000", " ").strip()
        s = re.sub(r"[ \t]+", " ", s)
        if not s:
            continue
        if AD_LINE_RE.search(s):
            continue
        lines.append(s)
    # 合并连续空行（上面已丢空行，这里保持段落）
    return "\n".join(lines)


def normalize_spaces(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


# ---------------------------------------------------------------------------
# 番茄字体解码
# ---------------------------------------------------------------------------

# 当前线上番茄字体（awesome-font/c/dc027189e0ba4cd）的私有区码位 → 字符。
# 由子集字体的 CFF 轮廓与 SourceHanSansSC-Normal 的轮廓逐一匹配得到
# （362/362 精确匹配）。番茄换字体后本表失效，会走下面的动态重建逻辑。
_KNOWN_FONT_MAPS = {
    "dc027189e0ba4cd":        {
            58344:"D", 58345:"在", 58346:"主", 58347:"特", 58348:"家", 58349:"军", 58350:"然", 58351:"表", 58352:"场", 58353:"4", 58354:"要", 58355:"只",
            58356:"v", 58357:"和", 58359:"6", 58360:"别", 58361:"还", 58362:"g", 58363:"现", 58364:"儿", 58365:"岁", 58368:"此", 58369:"象", 58370:"月",
            58371:"3", 58372:"出", 58373:"战", 58374:"工", 58375:"相", 58376:"o", 58377:"男", 58378:"直", 58379:"失", 58380:"世", 58381:"F", 58382:"都",
            58383:"平", 58384:"文", 58385:"什", 58386:"V", 58387:"O", 58388:"将", 58389:"真", 58390:"T", 58391:"那", 58392:"当", 58394:"会", 58395:"立",
            58396:"些", 58397:"u", 58398:"是", 58399:"十", 58400:"张", 58401:"学", 58402:"气", 58403:"大", 58404:"爱", 58405:"两", 58406:"命", 58407:"全",
            58408:"后", 58409:"东", 58410:"性", 58411:"通", 58412:"被", 58413:"1", 58414:"它", 58415:"乐", 58416:"接", 58417:"而", 58418:"感", 58419:"车",
            58420:"山", 58421:"公", 58422:"了", 58423:"常", 58424:"以", 58425:"何", 58426:"可", 58427:"话", 58428:"先", 58429:"p", 58430:"i", 58431:"叫",
            58432:"轻", 58433:"M", 58434:"士", 58435:"w", 58436:"着", 58437:"变", 58438:"尔", 58439:"快", 58440:"l", 58441:"个", 58442:"说", 58443:"少",
            58444:"色", 58445:"里", 58446:"安", 58447:"花", 58448:"远", 58449:"7", 58450:"难", 58451:"师", 58452:"放", 58453:"t", 58454:"报", 58455:"认",
            58456:"面", 58457:"道", 58458:"S", 58460:"克", 58461:"地", 58462:"度", 58463:"I", 58464:"好", 58465:"机", 58466:"U", 58467:"民", 58468:"写",
            58469:"把", 58470:"万", 58471:"同", 58472:"水", 58473:"新", 58474:"没", 58475:"书", 58476:"电", 58477:"吃", 58478:"像", 58479:"斯", 58480:"5",
            58481:"为", 58482:"y", 58483:"白", 58484:"几", 58485:"日", 58486:"教", 58487:"看", 58488:"但", 58489:"第", 58490:"加", 58491:"候", 58492:"作",
            58493:"上", 58494:"拉", 58495:"住", 58496:"有", 58497:"法", 58498:"r", 58499:"事", 58500:"应", 58501:"位", 58502:"利", 58503:"你", 58504:"声",
            58505:"身", 58506:"国", 58507:"问", 58508:"马", 58509:"女", 58510:"他", 58511:"Y", 58512:"比", 58513:"父", 58514:"x", 58515:"A", 58516:"H",
            58517:"N", 58518:"s", 58519:"X", 58520:"边", 58521:"美", 58522:"对", 58523:"所", 58524:"金", 58525:"活", 58526:"回", 58527:"意", 58528:"到",
            58529:"z", 58530:"从", 58531:"j", 58532:"知", 58533:"又", 58534:"内", 58535:"因", 58536:"点", 58537:"Q", 58538:"三", 58539:"定", 58540:"8",
            58541:"R", 58542:"b", 58543:"正", 58544:"或", 58545:"夫", 58546:"向", 58547:"德", 58548:"听", 58549:"更", 58551:"得", 58552:"告", 58553:"并",
            58554:"本", 58555:"q", 58556:"过", 58557:"记", 58558:"L", 58559:"让", 58560:"打", 58561:"f", 58562:"人", 58563:"就", 58564:"者", 58565:"去",
            58566:"原", 58567:"满", 58568:"体", 58569:"做", 58570:"经", 58571:"K", 58572:"走", 58573:"如", 58574:"孩", 58575:"c", 58576:"G", 58577:"给",
            58578:"使", 58579:"物", 58581:"最", 58582:"笑", 58583:"部", 58585:"员", 58586:"等", 58587:"受", 58588:"k", 58589:"行", 58590:"一", 58591:"条",
            58592:"果", 58593:"动", 58594:"光", 58595:"门", 58596:"头", 58597:"见", 58598:"往", 58599:"自", 58600:"解", 58601:"成", 58602:"处", 58603:"天",
            58604:"能", 58605:"于", 58606:"名", 58607:"其", 58608:"发", 58609:"总", 58610:"母", 58611:"的", 58612:"死", 58613:"手", 58614:"入", 58615:"路",
            58616:"进", 58617:"心", 58618:"来", 58619:"h", 58620:"时", 58621:"力", 58622:"多", 58623:"开", 58624:"已", 58625:"许", 58626:"d", 58627:"至",
            58628:"由", 58629:"很", 58630:"界", 58631:"n", 58632:"小", 58633:"与", 58634:"Z", 58635:"想", 58636:"代", 58637:"么", 58638:"分", 58639:"生",
            58640:"口", 58641:"再", 58642:"妈", 58643:"望", 58644:"次", 58645:"西", 58646:"风", 58647:"种", 58648:"带", 58649:"J", 58651:"实", 58652:"情",
            58653:"才", 58654:"这", 58656:"E", 58657:"我", 58658:"神", 58659:"格", 58660:"长", 58661:"觉", 58662:"间", 58663:"年", 58664:"眼", 58665:"无",
            58666:"不", 58667:"亲", 58668:"关", 58669:"结", 58670:"0", 58671:"友", 58672:"信", 58673:"下", 58674:"却", 58675:"重", 58676:"己", 58677:"老",
            58678:"2", 58679:"音", 58680:"字", 58681:"m", 58682:"呢", 58683:"明", 58684:"之", 58685:"前", 58686:"高", 58687:"P", 58688:"B", 58689:"目",
            58690:"太", 58691:"e", 58692:"9", 58693:"起", 58694:"稜", 58695:"她", 58696:"也", 58697:"W", 58698:"用", 58699:"方", 58700:"子", 58701:"英",
            58702:"每", 58703:"理", 58704:"便", 58705:"四", 58706:"数", 58707:"期", 58708:"中", 58709:"C", 58710:"外", 58711:"样", 58712:"a", 58713:"海",
            58714:"们", 58715:"任",
        },
}


def _extract_font_hash(page_html: str) -> str | None:
    m = re.search(r"awesome-font/c/([0-9a-f]{8,})\.", page_html)
    return m.group(1) if m else None


def _extract_font_url(page_html: str) -> str | None:
    m = re.search(r"(https://[a-z0-9.\-]*bytetos\.com/obj/awesome-font/c/[0-9a-f]+\.otf)", page_html)
    if m:
        return m.group(1)
    m = re.search(r"(https://[a-z0-9.\-]*bytetos\.com/obj/awesome-font/c/[0-9a-f]+\.woff2)", page_html)
    return m.group(1) if m else None


def _font_cache_path(font_hash: str) -> str:
    return os.path.join(FONT_DIR, f"fontmap-{font_hash}.json")


def get_font_map(font_hash: str, font_url: str | None = None,
                 page_html: str = "") -> dict[int, str]:
    """返回 {私有区码位: 字符}。优先内置表/缓存，缺失时重建。"""
    if font_hash in _KNOWN_FONT_MAPS:
        return {int(k): v for k, v in _KNOWN_FONT_MAPS[font_hash].items()}
    cached = read_json(_font_cache_path(font_hash))
    if cached:
        return {int(k): v for k, v in cached.items()}
    log(f"[字体] 遇到新字体 {font_hash}，尝试重建映射表…")
    mapping = rebuild_font_map(font_hash, font_url, page_html)
    if mapping:
        atomic_write(_font_cache_path(font_hash),
                     json.dumps({str(k): v for k, v in mapping.items()},
                                ensure_ascii=False, indent=0))
        log(f"[字体] 映射表重建成功，共 {len(mapping)} 字，已缓存")
        return mapping
    log("[字体] 警告：无法解码私有区字符，正文将保留原码位")
    return {}


def decode_private_use(text: str, font_map: dict[int, str]) -> str:
    if not font_map:
        return text
    return "".join(font_map.get(ord(ch), ch) for ch in text)


# --- 字体轮廓解析（纯标准库） ------------------------------------------------

def _read_tables(data: bytes) -> dict:
    num = struct.unpack(">H", data[4:6])[0]
    out = {}
    off = 12
    for _ in range(num):
        tag = data[off:off + 4].decode("latin1")
        _, t_off, t_len = struct.unpack(">III", data[off + 4:off + 16])
        out[tag] = (t_off, t_len)
        off += 16
    return out


def _read_index(buf: bytes, off: int):
    cnt = struct.unpack(">H", buf[off:off + 2])[0]
    if cnt == 0:
        return [], off + 2
    size = buf[off + 2]
    offs = [int.from_bytes(buf[off + 3 + i * size: off + 3 + (i + 1) * size], "big")
            for i in range(cnt + 1)]
    base = off + 3 + (cnt + 1) * size - 1
    return [buf[base + offs[i]:base + offs[i + 1]] for i in range(cnt)], base + offs[-1]


def _parse_dict(d: bytes) -> dict:
    out, ops, i = {}, [], 0
    while i < len(d):
        b = d[i]
        if b <= 21:
            op = b
            i += 1
            if op == 12:
                op = 1200 + d[i]
                i += 1
            out[op] = ops
            ops = []
        elif b == 28:
            ops.append(struct.unpack(">h", d[i + 1:i + 3])[0])
            i += 3
        elif b == 29:
            ops.append(struct.unpack(">i", d[i + 1:i + 5])[0])
            i += 5
        elif b == 30:
            i += 1
            while i < len(d):
                c = d[i]
                i += 1
                if (c >> 4) == 15 or (c & 15) == 15:
                    break
            ops.append(0)
        elif 32 <= b <= 246:
            ops.append(b - 139)
            i += 1
        elif 247 <= b <= 250:
            ops.append((b - 247) * 256 + d[i + 1] + 108)
            i += 2
        elif 251 <= b <= 254:
            ops.append(-(b - 251) * 256 - d[i + 1] - 108)
            i += 2
        else:
            i += 1
    return out


class _CFFFont:
    """够用来做轮廓比对的 CFF 解析器（Type2 charstring → 绝对坐标点列）。"""

    def __init__(self, path: str):
        with open(path, "rb") as fh:
            data = fh.read()
        self._raw = data
        tables = _read_tables(data)
        if "CFF " not in tables:
            raise FetchError(f"不是 CFF 字体：{path}")
        co, cl = tables["CFF "]
        self.cff = data[co:co + cl]
        self.tables = tables
        p = self.cff[2]
        _, p = _read_index(self.cff, p)          # name INDEX
        tops, p = _read_index(self.cff, p)       # top DICT INDEX
        _, p = _read_index(self.cff, p)          # string INDEX
        self.gsubrs, p = _read_index(self.cff, p)
        td = _parse_dict(tops[0])
        self.charstrings, _ = _read_index(self.cff, td[17][0])
        self.lsubrs = []
        self.fdarray = []
        priv = td.get(18)
        if priv:
            self.lsubrs = self._priv_subrs(priv[0], priv[1])
        if 1236 in td:  # CID-keyed: FDArray / FDSelect
            fdas, _ = _read_index(self.cff, td[1236][0])
            for fd in fdas:
                d = _parse_dict(fd)
                pr = d.get(18)
                self.fdarray.append(self._priv_subrs(pr[0], pr[1]) if pr else [])
        self.fdselect_off = td.get(1237, [None])[0]
        self.charset_off = td.get(15, [None])[0]
        self.cmap = self._parse_cmap()

    def _priv_subrs(self, size: int, off: int):
        d = _parse_dict(self.cff[off:off + size])
        so = d.get(19, [0])[0]
        if so:
            subs, _ = _read_index(self.cff, off + so)
            return subs
        return []

    def _fdselect(self, gid: int) -> int:
        if self.fdselect_off is None:
            return 0
        off = self.fdselect_off
        fmt = self.cff[off]
        if fmt == 0:
            return self.cff[off + 1 + gid]
        if fmt == 3:
            n = struct.unpack(">H", self.cff[off + 1:off + 3])[0]
            ranges, p = [], off + 3
            for _ in range(n):
                first = struct.unpack(">H", self.cff[p:p + 2])[0]
                ranges.append((first, self.cff[p + 2]))
                p += 3
            for i in range(len(ranges) - 1):
                if ranges[i][0] <= gid < ranges[i + 1][0]:
                    return ranges[i][1]
            return ranges[-1][1] if ranges else 0
        return 0

    def _parse_cmap(self) -> dict:
        if "cmap" not in self.tables:
            return {}
        data_off, _ = self.tables["cmap"]
        data = self._raw
        n = struct.unpack(">H", data[data_off + 2:data_off + 4])[0]
        best = []
        for i in range(n):
            pid, eid, so = struct.unpack(">HHI", data[data_off + 4 + i * 8: data_off + 12 + i * 8])
            o = data_off + so
            fmt = struct.unpack(">H", data[o:o + 2])[0]
            if fmt in (4, 12):
                best.append((fmt, o))
        u2g = {}
        for fmt, o in best:
            if fmt == 12:
                _, _, _, _, cnt = struct.unpack(">HHIII", data[o:o + 16])
                for i in range(cnt):
                    s, e, sg = struct.unpack(">III", data[o + 16 + i * 12:o + 28 + i * 12])
                    for u in range(s, e + 1):
                        u2g.setdefault(u, sg + (u - s))
            else:
                seg_x2 = struct.unpack(">H", data[o + 6:o + 8])[0]
                seg = seg_x2 // 2
                end = o + 14
                start = end + seg_x2 + 2
                delta = start + seg_x2
                ro = delta + seg_x2
                for i in range(seg):
                    e = struct.unpack(">H", data[end + i * 2:end + i * 2 + 2])[0]
                    s = struct.unpack(">H", data[start + i * 2:start + i * 2 + 2])[0]
                    d = struct.unpack(">h", data[delta + i * 2:delta + i * 2 + 2])[0]
                    r = struct.unpack(">H", data[ro + i * 2:ro + i * 2 + 2])[0]
                    if e == 0xFFFF:
                        continue
                    for u in range(s, e + 1):
                        if u == 0xFFFF:
                            continue
                        if r == 0:
                            g = (u + d) & 0xFFFF
                        else:
                            addr = ro + i * 2 + r + (u - s) * 2
                            g = struct.unpack(">H", data[addr:addr + 2])[0]
                            if g:
                                g = (g + d) & 0xFFFF
                        if g:
                            u2g.setdefault(u, g)
        return u2g

    def bias(self, n: int) -> int:
        return 107 if n < 1240 else (1131 if n < 33900 else 32768)

    def outline(self, gid: int, subrs=None) -> list:
        if subrs is None:
            subrs = []
            if self.fdarray:
                idx = self._fdselect(gid)
                if 0 <= idx < len(self.fdarray):
                    subrs = self.fdarray[idx]
            else:
                subrs = self.lsubrs
        self._stems = [0]
        cmds: list = []
        self._run(self.charstrings[gid], subrs, 0.0, 0.0, [], cmds, 0)
        return cmds

    def _run(self, cs, subrs, x, y, stack, cmds, depth):
        if depth > 12:
            return x, y
        i, n = 0, len(cs)
        while i < n:
            b = cs[i]
            if b >= 32:
                if b <= 246:
                    stack.append(b - 139); i += 1
                elif b <= 250:
                    stack.append((b - 247) * 256 + cs[i + 1] + 108); i += 2
                elif b <= 254:
                    stack.append(-(b - 251) * 256 - cs[i + 1] - 108); i += 2
                else:
                    stack.append(0); i += 1
                continue
            if b == 28:
                stack.append(struct.unpack(">h", cs[i + 1:i + 3])[0]); i += 3; continue
            if b == 255:
                stack.append(struct.unpack(">i", cs[i + 1:i + 5])[0] / 65536.0); i += 5; continue
            if b in (1, 3, 18, 23):
                self._stems[0] += len(stack) // 2
                stack = []; i += 1; continue
            if b in (19, 20):
                self._stems[0] += len(stack) // 2
                stack = []; i += 1 + (self._stems[0] + 7) // 8; continue
            if b == 21:
                if len(stack) >= 2:
                    x += stack[-2]; y += stack[-1]; cmds.append(("m", x, y))
                stack = []; i += 1; continue
            if b == 22:
                if stack:
                    x += stack[-1]; cmds.append(("m", x, y))
                stack = []; i += 1; continue
            if b == 4:
                if stack:
                    y += stack[-1]; cmds.append(("m", x, y))
                stack = []; i += 1; continue
            if b == 5:
                for k in range(0, len(stack) - 1, 2):
                    x += stack[k]; y += stack[k + 1]; cmds.append(("l", x, y))
                stack = []; i += 1; continue
            if b == 6:
                for k in range(len(stack)):
                    if k % 2 == 0:
                        x += stack[k]
                    else:
                        y += stack[k]
                    cmds.append(("l", x, y))
                stack = []; i += 1; continue
            if b == 7:
                for k in range(len(stack)):
                    if k % 2 == 0:
                        y += stack[k]
                    else:
                        x += stack[k]
                    cmds.append(("l", x, y))
                stack = []; i += 1; continue
            if b == 8:
                while len(stack) >= 6:
                    c = stack[:6]; del stack[:6]
                    cmds.append(("c", x + c[0], y + c[1], x + c[0] + c[2],
                                 y + c[1] + c[3], x + c[0] + c[2] + c[4],
                                 y + c[1] + c[3] + c[5]))
                    x += c[0] + c[2] + c[4]; y += c[1] + c[3] + c[5]
                stack = []; i += 1; continue
            if b == 24:
                while len(stack) >= 8:
                    c = stack[:6]; del stack[:6]
                    cmds.append(("c", x + c[0], y + c[1], x + c[0] + c[2],
                                 y + c[1] + c[3], x + c[0] + c[2] + c[4],
                                 y + c[1] + c[3] + c[5]))
                    x += c[0] + c[2] + c[4]; y += c[1] + c[3] + c[5]
                if len(stack) >= 2:
                    x += stack[0]; y += stack[1]; cmds.append(("l", x, y))
                stack = []; i += 1; continue
            if b == 25:
                while len(stack) >= 8:
                    x += stack[0]; y += stack[1]; cmds.append(("l", x, y)); del stack[0:2]
                while len(stack) >= 6:
                    c = stack[:6]; del stack[:6]
                    cmds.append(("c", x + c[0], y + c[1], x + c[0] + c[2],
                                 y + c[1] + c[3], x + c[0] + c[2] + c[4],
                                 y + c[1] + c[3] + c[5]))
                    x += c[0] + c[2] + c[4]; y += c[1] + c[3] + c[5]
                stack = []; i += 1; continue
            if b in (26, 27):
                st = stack[:]; stack = []
                if b == 26:
                    dx1 = st.pop(0) if len(st) % 4 == 1 else 0
                    while len(st) >= 4:
                        dy1, dx2, dy2, dy3 = st[:4]; del st[:4]
                        cmds.append(("c", x + dx1, y + dy1, x + dx1 + dx2,
                                     y + dy1 + dy2, x + dx1 + dx2, y + dy1 + dy2 + dy3))
                        x += dx1 + dx2; y += dy1 + dy2 + dy3; dx1 = 0
                else:
                    dy1 = st.pop(0) if len(st) % 4 == 1 else 0
                    while len(st) >= 4:
                        dx1, dx2, dy2, dx3 = st[:4]; del st[:4]
                        cmds.append(("c", x + dx1, y + dy1, x + dx1 + dx2,
                                     y + dy1 + dy2, x + dx1 + dx2 + dx3, y + dy1 + dy2))
                        x += dx1 + dx2 + dx3; y += dy1 + dy2; dy1 = 0
                i += 1; continue
            if b in (30, 31):
                st = stack[:]; stack = []
                vertical = (b == 30)
                while len(st) >= 4:
                    if vertical:
                        dx1, dy1, dx2, dy2 = st[:4]; del st[:4]
                        tail = st.pop(0) if len(st) == 1 else 0
                        cmds.append(("c", x + dx1, y + dy1, x + dx1 + dx2,
                                     y + dy1 + dy2, x + dx1 + dx2, y + dy1 + dy2 + tail))
                        x += dx1 + dx2; y += dy1 + dy2 + tail
                    else:
                        dy1, dx1, dy2, dx2 = st[:4]; del st[:4]
                        tail = st.pop(0) if len(st) == 1 else 0
                        cmds.append(("c", x + dx1, y + dy1, x + dx1 + dx2,
                                     y + dy1 + dy2, x + dx1 + dx2 + tail, y + dy1 + dy2))
                        x += dx1 + dx2 + tail; y += dy1 + dy2
                    vertical = not vertical
                i += 1; continue
            if b == 10:
                if stack:
                    idx = int(stack.pop())
                    bi = idx + self.bias(len(subrs))
                    if 0 <= bi < len(subrs):
                        x, y = self._run(subrs[bi], subrs, x, y, stack, cmds, depth + 1)
                stack = []; i += 1; continue
            if b == 29:
                if stack:
                    idx = int(stack.pop())
                    bi = idx + self.bias(len(self.gsubrs))
                    if 0 <= bi < len(self.gsubrs):
                        x, y = self._run(self.gsubrs[bi], self.gsubrs, x, y, stack, cmds, depth + 1)
                stack = []; i += 1; continue
            if b == 12:
                esc = cs[i + 1] if i + 1 < n else 0
                if esc in (34, 35, 36, 37):
                    st = stack[:]
                    if esc == 34 and len(st) >= 7:
                        c = st[:7]
                        cmds.append(("c", x + c[0], y, x + c[0] + c[2], y + c[1],
                                     x + c[0] + c[2] + c[4], y + c[1] + c[3]))
                        x += c[0] + c[2] + c[4] + c[6]; y += c[1] + c[3] + c[5]
                    elif esc == 35 and len(st) >= 13:
                        c = st[:13]
                        cmds.append(("c", x + c[0], y + c[1], x + c[0] + c[2], y + c[1] + c[3],
                                     x + c[0] + c[2] + c[4], y + c[1] + c[3] + c[5]))
                        x += c[0] + c[2] + c[4]; y += c[1] + c[3] + c[5]
                        cmds.append(("c", x + c[6], y + c[7], x + c[6] + c[8], y + c[7] + c[9],
                                     x + c[6] + c[8] + c[10], y + c[7] + c[9] + c[11]))
                        x += c[6] + c[8] + c[10]; y += c[7] + c[9] + c[11]
                stack = []; i += 2; continue
            if b in (11, 14):
                i += 1; continue
            stack = []; i += 1
        return x, y


def _outline_sig(cmds) -> tuple:
    return tuple((c[0],) + tuple(round(float(v), 2) for v in c[1:]) for c in cmds)


_REF_FONT_URLS = [
    "https://raw.githubusercontent.com/adobe-fonts/source-han-sans/2.002R/OTF/SimplifiedChinese/SourceHanSansSC-Normal.otf",
    "https://cdn.jsdelivr.net/gh/adobe-fonts/source-han-sans@2.002R/OTF/SimplifiedChinese/SourceHanSansSC-Normal.otf",
]


def _ensure_ref_font() -> str | None:
    """参考字体（SourceHanSansSC-Normal 2.002R）缓存；缺失时下载一次。"""
    target = os.path.join(FONT_DIR, "SourceHanSansSC-Normal-2.002R.otf")
    if os.path.exists(target) and os.path.getsize(target) > 10_000_000:
        return target
    os.makedirs(FONT_DIR, exist_ok=True)
    for url in _REF_FONT_URLS:
        try:
            log(f"[字体] 下载参考字体（约16MB，仅首次）：{url}")
            data = HTTP.get(url, binary=True)
            if len(data) < 10_000_000:
                log(f"[字体] 参考字体体积异常（{len(data)}），换下一个源")
                continue
            atomic_write(target, data)
            return target
        except FetchError as e:
            log(f"[字体] 下载失败：{e}")
    return None


def _fonttools_available() -> bool:
    """fontTools 是可选加速：装了就用它做字形轮廓比对，没装走纯标准库实现。"""
    try:
        import fontTools  # noqa: F401
        from fontTools.ttLib import TTFont  # noqa: F401
        from fontTools.pens.recordingPen import RecordingPen  # noqa: F401
        return True
    except Exception:
        return False


def _rebuild_with_fonttools(sub_path: str, ref_path: str) -> dict[int, str]:
    from fontTools.ttLib import TTFont
    from fontTools.pens.recordingPen import RecordingPen

    def sig(cs):
        pen = RecordingPen()
        cs.draw(pen)
        out = []
        for op, args in pen.value:
            if op == "moveTo":
                out.append(("m",) + tuple(args[0]))
            elif op == "lineTo":
                out.append(("l",) + tuple(args[0]))
            elif op == "curveTo":
                out.append(("c",) + tuple(c for pt in args for c in pt))
        return tuple((o,) + tuple(round(float(v), 2) for v in rest) for o, *rest in out)

    sub = TTFont(sub_path)
    sub_cs = sub["CFF "].cff.topDictIndex[0].CharStrings
    sub_cmap = {}
    for table in sub["cmap"].tables:
        sub_cmap.update(table.cmap)

    ref = TTFont(ref_path)
    ref_cs = ref["CFF "].cff.topDictIndex[0].CharStrings
    ref_cmap = {}
    for table in ref["cmap"].tables:
        for u, nm in table.cmap.items():
            ref_cmap.setdefault(u, nm)

    def priority(u):
        if 0x4E00 <= u <= 0x9FFF:
            return (0, u)
        if 0x3400 <= u <= 0x4DBF:
            return (1, u)
        if u < 0x2E80 or 0xFF00 <= u <= 0xFFEF:
            return (2, u)
        return (3, u)

    sig2u = {}
    for u in sorted(ref_cmap, key=priority):
        try:
            sig2u.setdefault(sig(ref_cs[ref_cmap[u]]), u)
        except Exception:
            continue
    mapping = {}
    for cp, nm in sub_cmap.items():
        try:
            u = sig2u.get(sig(sub_cs[nm]))
        except Exception:
            u = None
        if u:
            mapping[cp] = chr(u)
    return mapping


def rebuild_font_map(font_hash: str, font_url: str | None,
                     page_html: str) -> dict[int, str]:
    """下载子集字体 + 参考字体，用轮廓匹配重建 {码位: 字符}。"""
    if not font_url:
        font_url = f"https://lf6-awef.bytetos.com/obj/awesome-font/c/{font_hash}.otf"
    sub_path = os.path.join(FONT_DIR, f"subset-{font_hash}.otf")
    try:
        if not (os.path.exists(sub_path) and os.path.getsize(sub_path) > 1000):
            raw = HTTP.get(font_url, binary=True)
            atomic_write(sub_path, raw)
        ref_path = _ensure_ref_font()
        if not ref_path:
            return {}
        if _fonttools_available():
            log("[字体] 使用 fontTools 做轮廓比对")
            mapping = _rebuild_with_fonttools(sub_path, ref_path)
            if mapping:
                return mapping
            log("[字体] fontTools 路径失败，回退纯标准库")
        sub = _CFFFont(sub_path)
        ref = _CFFFont(ref_path)
        if not ref.cmap:
            return {}
        # 参考字体：轮廓签名 → 字符（优先 CJK 统一汉字，避免解成康熙部首）
        sig2u = {}
        priority = []
        for u, gid in ref.cmap.items():
            if 0x4E00 <= u <= 0x9FFF:
                priority.append((0, u, gid))
            elif 0x3400 <= u <= 0x4DBF:
                priority.append((1, u, gid))
            elif u < 0x2E80 or 0xFF00 <= u <= 0xFFEF:
                priority.append((2, u, gid))
            else:
                priority.append((3, u, gid))
        priority.sort()
        for _, u, gid in priority:
            try:
                sig2u.setdefault(_outline_sig(ref.outline(gid)), u)
            except Exception:
                continue
        mapping = {}
        for cp, gid in sub.cmap.items():
            try:
                u = sig2u.get(_outline_sig(sub.outline(gid)))
            except Exception:
                u = None
            if u:
                mapping[cp] = chr(u)
        return mapping
    except (FetchError, OSError, struct.error, IndexError) as e:
        log(f"[字体] 重建映射失败：{type(e).__name__}: {e}")
        return {}


# ---------------------------------------------------------------------------
# 初始状态提取（括号平衡扫描）
# ---------------------------------------------------------------------------

def extract_initial_state(page_html: str, marker: str = "__INITIAL_STATE__") -> dict:
    """括号平衡扫描提取 SSR JSON。正则 {.*?} 会被正文里的花括号截断。"""
    idx = page_html.find(marker)
    if idx < 0:
        raise FetchError("页面里没有 __INITIAL_STATE__（可能是风控页或页面改版）")
    start = page_html.find("{", idx)
    if start < 0:
        raise FetchError("__INITIAL_STATE__ 后没有 JSON 对象")
    depth = 0
    in_str = False
    esc = False
    quote = ""
    i = start
    n = len(page_html)
    while i < n:
        ch = page_html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        else:
            if ch in "\"'":
                in_str = True
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw = page_html[start:i + 1]
                    try:
                        return json.loads(raw)
                    except ValueError as e:
                        raise FetchError(f"__INITIAL_STATE__ JSON 解析失败：{e}")
        i += 1
    raise FetchError("__INITIAL_STATE__ 括号不平衡")


# ---------------------------------------------------------------------------
# 源适配器
# ---------------------------------------------------------------------------

class Source:
    name = ""
    label = ""

    def search(self, query: str) -> dict:
        return {"query": query, "results": [], "error": f"{self.label} 不支持站内搜索"}

    def info(self, book_id: str) -> dict:
        raise NotImplementedError

    def chapter_ids(self, book_id: str) -> list:
        raise NotImplementedError

    def chapter_ids_range(self, book_id: str, lo: int, hi: int):
        """返回 (lo..hi 内的条目, 总章数)。默认全量抓取后切片。"""
        ids = self.chapter_ids(book_id)
        total = len(ids)
        return ids[max(1, lo) - 1:min(total, hi)], total

    def chapter_text(self, book_id: str, item, index: int) -> tuple:
        """返回 (标题, 纯文本正文)。"""
        raise NotImplementedError


# --- 番茄 --------------------------------------------------------------------

class FanqieSource(Source):
    name = "fanqie"
    label = "番茄小说"
    BASE = "https://fanqienovel.com"

    def search(self, query: str) -> dict:
        # 番茄搜索页/搜索 API 直连拿不到（见 CONTRACT.md 已验证事实）
        return {
            "query": query,
            "results": [],
            "error": "fanqie_search_unavailable",
            "note": "番茄搜索接口不可直连；请用 web_search 或扫榜脚本找 bookId 后走 info/book。",
        }

    def info(self, book_id: str) -> dict:
        page_url = f"{self.BASE}/page/{book_id}"
        page_html = HTTP.get(page_url)
        state = extract_initial_state(page_html)
        page = state.get("page") or {}
        if not page.get("bookName"):
            raise FetchError("作品页 SSR 里没有 page.bookName（可能是风控页）")

        tags = []
        cat_raw = page.get("categoryV2") or ""
        try:
            cats = json.loads(cat_raw) if isinstance(cat_raw, str) else cat_raw
            if isinstance(cats, list):
                for c in cats:
                    nm = (c or {}).get("Name") if isinstance(c, dict) else None
                    if nm and nm not in tags:
                        tags.append(nm)
        except ValueError:
            pass
        if not tags and page.get("category"):
            tags = [page["category"]]

        creation = page.get("creationStatus")
        if isinstance(creation, (int, float)):
            status = {0: "连载中", 1: "已完结", 2: "已完结"}.get(int(creation), "连载中")
        else:
            status = str(creation or "连载中")

        abstract = page.get("abstract") or page.get("description") or ""
        abstract = htmlmod.unescape(re.sub(r"<[^>]+>", "", abstract)).strip()
        author_desc = page.get("description") or ""
        author_desc = htmlmod.unescape(re.sub(r"<[^>]+>", "", author_desc)).strip()
        desc = abstract or author_desc

        return {
            "key": book_key(self.name, str(book_id)),
            "source": self.name,
            "book_id": str(book_id),
            "name": page.get("bookName") or "",
            "author": page.get("author") or page.get("authorName") or "",
            "desc": desc,
            "tags": tags,
            "word_count": int(page.get("wordNumber") or 0),
            "read_count": int(page.get("readCount") or 0),
            "creation_status": status,
            "chapter_total": int(page.get("chapterTotal") or 0),
            "url": page_url,
            "fetched_at": now_iso(),
            "source_note": "官方SSR",
        }

    def chapter_ids(self, book_id: str) -> list:
        api = f"{self.BASE}/api/reader/directory/detail?bookId={book_id}"
        raw = HTTP.get(api, headers={"Accept": "application/json, text/plain, */*",
                                     "Referer": f"{self.BASE}/"})
        try:
            data = json.loads(raw).get("data") or {}
        except ValueError:
            raise FetchError("目录 API 返回的不是 JSON")
        ids = data.get("allItemIds") or []
        if not ids:
            raise FetchError("目录 API 里没有 allItemIds")
        return [str(x) for x in ids]

    def chapter_text(self, book_id: str, item, index: int) -> tuple:
        url = f"{self.BASE}/reader/{item}"
        page_html = HTTP.get(url)
        state = extract_initial_state(page_html)
        reader = state.get("reader") or {}
        cd = reader.get("chapterData") or {}
        if not cd:
            raise FetchError(f"章节 {index} SSR 里没有 chapterData")
        title = (cd.get("title") or f"第{index}章").strip()
        content = cd.get("content") or ""
        font_hash = _extract_font_hash(page_html)
        if font_hash:
            font_url = _extract_font_url(page_html)
            fmap = get_font_map(font_hash, font_url, page_html)
            content = decode_private_use(content, fmap)
        text = clean_html_content(content)
        return title, text


# --- 天禧（www.tianxixsw.com） ----------------------------------------------

class TianxiSource(Source):
    name = "tianxi"
    label = "天禧小说"
    BASE = "https://www.tianxixsw.com"
    PAGE_SIZE = 300

    def search(self, query: str) -> dict:
        return {
            "query": query,
            "results": [],
            "error": "tianxi_search_disabled",
            "note": "站内 /search/ 已由站长关闭（弹窗提示）；请用 web_search 找 bookId 后走 info/book。",
        }

    def info(self, book_id: str) -> dict:
        url = f"{self.BASE}/book/{book_id}/"
        page_html = HTTP.get(url)
        og = dict(re.findall(
            r'<meta property="og:novel:([a-z_]+)" content=["\']([^"\']*)["\']', page_html))
        if not og.get("book_name"):
            raise FetchError("书籍页缺少 og:novel 元数据（可能已下架）")

        chapter_total, chapter_ids, titles = self._directory(book_id)
        tags = [og["category"]] if og.get("category") else []
        return {
            "key": book_key(self.name, str(book_id)),
            "source": self.name,
            "book_id": str(book_id),
            "name": og.get("book_name", ""),
            "author": og.get("author", ""),
            "desc": self._og_desc(page_html),
            "tags": tags,
            "word_count": 0,
            "read_count": 0,
            "creation_status": og.get("status", ""),
            "chapter_total": chapter_total,
            "url": url,
            "fetched_at": now_iso(),
            "source_note": f"站内SSR({self.BASE})",
        }

    @staticmethod
    def _og_desc(page_html: str) -> str:
        m = re.search(r'<meta name="description" content="([^"]*)"', page_html)
        if not m:
            m = re.search(r'<meta property="og:description" content="([^"]*)"', page_html)
        if not m:
            return ""
        txt = htmlmod.unescape(m.group(1))
        txt = re.sub(r"<[^>]+>", "", txt)
        txt = re.sub(r"\s+", " ", txt)
        # 去掉站点 SEO 尾巴："《书名》是作者的最新小说，本站提供…请关注…"
        txt = re.split(r"[。！!]\s*[^。！!]{0,30}是[^。！!]{0,25}的最新小说", txt)[0]
        for pat in ("新天禧小说小说网", "最新章节全文免费阅读", "无弹窗全文免费阅读",
                    "全文免费阅读", "请关注"):
            if pat in txt:
                txt = txt[:txt.index(pat)]
        txt = re.sub(r"^(简介[:：])?\s*", "", txt).strip()
        txt = re.sub(r"[，,。！!\s]+$", "", txt)
        txt = re.sub(r"[。！!]{2,}", "。", txt)
        return txt

    def _page_url(self, book_id: str, page: int) -> str:
        if page <= 1:
            return f"{self.BASE}/xiaoshuo/{book_id}/"
        return f"{self.BASE}/xiaoshuo/{book_id}/{page}/"

    @staticmethod
    def _to_items(pairs):
        return [{"id": cid, "title": title} for cid, title in pairs]

    def _parse_dir_page(self, page_html: str, book_id: str) -> list:
        pairs = re.findall(
            r'href="(/xiaoshuo/%s/(\d+)\.html)"[^>]*>\s*<dd>([^<]*)</dd>' % re.escape(book_id),
            page_html)
        out = []
        for _href, cid, title in pairs:
            title = htmlmod.unescape(title).strip()
            if title:
                out.append((cid, title))
        return out

    def _max_page(self, page_html: str) -> int:
        pages = [int(x) for x in re.findall(r"/xiaoshuo/\d+/(\d+)/", page_html)]
        return max(pages) if pages else 1

    def _directory(self, book_id: str) -> tuple:
        """返回 (章节总数, [(chapter_id, title), ...])，按需要跨页抓取。"""
        first = HTTP.get(self._page_url(book_id, 1))
        max_page = self._max_page(first)
        items = self._parse_dir_page(first, book_id)
        total = len(items)
        if max_page > 1:
            last = HTTP.get(self._page_url(book_id, max_page))
            last_items = self._parse_dir_page(last, book_id)
            total = (max_page - 1) * self.PAGE_SIZE + len(last_items)
            if len(items) < self.PAGE_SIZE:  # 首页不足一页，说明总数就是首页数量
                total = len(items)
        return total, [cid for cid, _ in items], [t for _, t in items]

    def chapter_ids(self, book_id: str) -> list:
        return self._to_items(self._iter_all_dir(book_id))

    def _iter_all_dir(self, book_id: str):
        first = HTTP.get(self._page_url(book_id, 1))
        max_page = self._max_page(first)
        for p in range(1, max_page + 1):
            html = first if p == 1 else HTTP.get(self._page_url(book_id, p))
            for cid, title in self._parse_dir_page(html, book_id):
                yield cid, title

    def chapter_ids_range(self, book_id: str, lo: int, hi: int):
        """只抓 lo..hi 落在的目录页，避免遍历全书目录。"""
        first = HTTP.get(self._page_url(book_id, 1))
        max_page = self._max_page(first)
        if max_page == 1:
            items = self._to_items(self._parse_dir_page(first, book_id))
            total = len(items)
            return items[max(1, lo) - 1:min(total, hi)], total
        last = HTTP.get(self._page_url(book_id, max_page))
        last_items = self._parse_dir_page(last, book_id)
        first_items = self._parse_dir_page(first, book_id)
        total = (max_page - 1) * self.PAGE_SIZE + len(last_items)
        if len(first_items) < self.PAGE_SIZE:
            total = len(first_items)
        lo2, hi2 = max(1, lo), min(total, hi)
        if lo2 > hi2:
            return [], total
        page_from = (lo2 - 1) // self.PAGE_SIZE + 1
        page_to = (hi2 - 1) // self.PAGE_SIZE + 1
        pool = []
        for pg in range(page_from, page_to + 1):
            if pg == 1:
                pool.extend(first_items)
            elif pg == max_page:
                pool.extend(last_items)
            else:
                pool.extend(self._parse_dir_page(HTTP.get(self._page_url(book_id, pg)), book_id))
        base = (page_from - 1) * self.PAGE_SIZE
        return self._to_items(pool[lo2 - base - 1: hi2 - base]), total

    def chapter_text(self, book_id: str, item, index: int) -> tuple:
        if isinstance(item, dict):
            cid, title_hint = item["id"], item.get("title") or f"第{index}章"
        elif isinstance(item, (tuple, list)):
            cid, title_hint = item[0], (item[1] if len(item) > 1 else f"第{index}章")
        else:
            cid, title_hint = str(item), f"第{index}章"
        base = f"/xiaoshuo/{book_id}/{cid}"
        pieces = []
        seen = set()
        suffix = ""
        for _ in range(12):  # 单章最多跟 12 页
            url = f"{self.BASE}{base}{suffix}.html"
            if url in seen:
                break
            seen.add(url)
            page_html = HTTP.get(url)
            body = self._extract_body(page_html)
            if body:
                pieces.append(body)
            m = re.search(r'<a[^>]+rel="next"[^>]+href="([^"]+)"', page_html)
            if not m:
                break
            nxt = m.group(1)
            if f"/{cid}_" not in nxt:
                break
            mm = re.search(rf'/{re.escape(cid)}(_\d+)\.html', nxt)
            if not mm:
                break
            suffix = mm.group(1)
        text = "\n".join(x for x in pieces if x)
        text = clean_html_content(text)
        return title_hint, text

    @staticmethod
    def _extract_body(page_html: str) -> str:
        m = re.search(r'<div id="content"[^>]*>(.*?)</div>\s*</div>', page_html, re.S)
        if not m:
            m = re.search(r'<div id="content"[^>]*>(.*?)</div>', page_html, re.S)
        if not m:
            return ""
        body = m.group(1)
        body = re.sub(r'<div id="booktxt"[^>]*>', "", body)
        body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
        body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
        return body


# --- 起点（只做榜单找书的轻量复用） ------------------------------------------

class QidianSource(Source):
    name = "qidian"
    label = "起点中文网"

    def _scraper(self) -> str:
        return os.path.join(PROJECT_ROOT, "skills", "story-long-scan",
                            "scripts", "qidian-rank-scraper.js")

    def search(self, query: str) -> dict:
        script = self._scraper()
        if not os.path.exists(script):
            return {"query": query, "results": [],
                    "error": "qidian_scraper_missing",
                    "note": "未找到 story-long-scan/scripts/qidian-rank-scraper.js"}
        node = shutil.which("node")
        if not node:
            return {"query": query, "results": [],
                    "error": "node_not_found",
                    "note": "起点榜单脚本需要本机 Node"}
        # 榜单脚本把结果写成 md 到 CWD，放到临时目录跑，避免污染工作区
        try:
            with tempfile.TemporaryDirectory(prefix="qidian-rank-") as td:
                proc = subprocess.run([node, script, "--type", "hotsales"],
                                      capture_output=True, text=True,
                                      timeout=120, cwd=td)
                md_text = ""
                for md in glob.glob(os.path.join(td, "*.md")):
                    with open(md, "r", encoding="utf-8", errors="replace") as fh:
                        md_text += fh.read()
        except (subprocess.TimeoutExpired, OSError) as e:
            return {"query": query, "results": [], "error": f"qidian_scraper_failed: {e}"}
        if proc.returncode != 0 or not md_text:
            return {"query": query, "results": [],
                    "error": "qidian_scraper_failed",
                    "note": (proc.stderr or "榜单脚本无输出")[-300:]}
        results = []
        for block in re.split(r"^## #\d+ ", md_text, flags=re.M)[1:]:
            lines = [x.strip() for x in block.splitlines() if x.strip()]
            if not lines:
                continue
            name = lines[0].strip()
            author = ""
            for ln in lines[1:4]:
                m = re.match(r"\*(.+?)(?:\s*·.*)?\*$", ln)
                if m:
                    author = m.group(1).strip()
                    break
            url_m = re.search(r"\]\((https?://[^)]+)\)", block)
            if query and query not in name and query not in author:
                continue
            results.append({
                "source": self.name,
                "book_id": "",
                "key": "",
                "name": name,
                "author": author,
                "desc": "起点榜单条目（本站正文有风控，请换免费源抓正文）",
                "word_count": 0,
                "url": url_m.group(1) if url_m else "",
            })
        return {"query": query, "results": results,
                "note": (None if results else
                         "起点畅销榜里没有匹配条目；本站正文有风控，仅用于找书。")}

    def info(self, book_id: str) -> dict:
        raise FetchError("起点本站正文不可直连（202 风控），请用 fanqie/tianxi 的 bookId；起点只做榜单找书兜底。")

    def chapter_ids(self, book_id: str) -> list:
        raise FetchError("起点不支持章节抓取")

    def chapter_text(self, book_id: str, item, index: int) -> tuple:
        raise FetchError("起点不支持章节抓取")


SOURCES = {
    "fanqie": FanqieSource(),
    "tianxi": TianxiSource(),
    "qidian": QidianSource(),
}


# ---------------------------------------------------------------------------
# 书籍落盘
# ---------------------------------------------------------------------------

def save_book(meta: dict, outdir: str) -> str:
    key = meta["key"]
    book_dir = os.path.join(outdir, key)
    os.makedirs(os.path.join(book_dir, "chapters"), exist_ok=True)
    atomic_write(os.path.join(book_dir, "meta.json"),
                 json.dumps(meta, ensure_ascii=False, indent=2))
    return book_dir


def fetch_book(source: Source, book_id: str, ch_from: int, ch_to: int,
               outdir: str) -> dict:
    key = book_key(source.name, book_id)
    book_dir = os.path.join(outdir, key)
    meta = source.info(book_id)
    save_book(meta, outdir)

    items, total = source.chapter_ids_range(book_id, ch_from, ch_to)
    if total == 0:
        return {"ok": False, "key": key, "outdir": book_dir, "downloaded": [],
                "failed": [], "chapter_total": 0, "error": "目录为空"}

    lo = max(1, ch_from)
    hi = min(total, ch_to)
    if lo > hi:
        return {"ok": False, "key": key, "outdir": book_dir, "downloaded": [],
                "failed": [], "chapter_total": total,
                "error": f"章节范围无效：--from {ch_from} --to {ch_to}（共 {total} 章）"}

    downloaded, failed = [], []
    chapters_dir = os.path.join(book_dir, "chapters")
    os.makedirs(chapters_dir, exist_ok=True)
    for n in range(lo, hi + 1):
        item = items[n - lo]
        try:
            title, text = source.chapter_text(book_id, item, n)
            if not text.strip():
                raise FetchError("正文为空（可能需付费/已下架）")
            body = f"# {title}\n\n{text}\n"
            atomic_write(os.path.join(chapters_dir, f"{n:04d}.txt"), body)
            downloaded.append(n)
            log(f"[{key}] 第{n}章 OK（{len(text)} 字）{title}")
        except FetchError as e:
            failed.append(n)
            log(f"[{key}] 第{n}章 失败：{e}")
        except (OSError, ValueError) as e:
            failed.append(n)
            log(f"[{key}] 第{n}章 异常：{type(e).__name__}: {e}")

    if meta.get("chapter_total") != total:
        meta["chapter_total"] = total
        save_book(meta, outdir)

    ok = bool(downloaded) and not failed
    err = None
    if not downloaded:
        err = "全部章节抓取失败"
    elif failed:
        err = f"{len(failed)} 章失败：{failed[:10]}"
    return {"ok": ok, "key": key, "outdir": book_dir,
            "downloaded": downloaded, "failed": failed,
            "chapter_total": total, "error": err}


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------

def cmd_search(args) -> int:
    platforms = ["fanqie", "tianxi", "qidian"] if args.platform == "all" else [args.platform]
    all_results, notes = [], []
    for p in platforms:
        src = SOURCES[p]
        try:
            res = src.search(args.query)
        except FetchError as e:
            notes.append(f"{p}: {e}")
            continue
        all_results.extend(res.get("results") or [])
        if res.get("note"):
            notes.append(f"{p}: {res['note']}")
        if res.get("error"):
            notes.append(f"{p}: {res['error']}")
    payload = {"query": args.query, "results": all_results}
    if notes:
        payload["notes"] = notes
        for n in notes:
            log(f"[search] {n}")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if not all_results:
            print(f"没有找到「{args.query}」的直接结果。")
            for n in notes:
                print(f"  - {n}")
        for r in all_results:
            print(f"{r['source']:<8} {r['name']}  {r.get('author','')}  {r.get('url','')}")
    return 0 if all_results else 3


def cmd_info(args) -> int:
    src = SOURCES[args.source]
    try:
        meta = src.info(args.book_id)
        out = {"ok": True, "meta": meta, "error": None}
    except (FetchError, OSError) as e:
        out = {"ok": False, "meta": None, "error": str(e)}
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        if out["ok"]:
            m = out["meta"]
            print(f"《{m['name']}》 {m['author']}  [{m['source']}]")
            print(f"  章节：{m['chapter_total']}  字数：{m['word_count']}  "
                  f"阅读：{m['read_count']}  状态：{m['creation_status']}")
            print(f"  标签：{', '.join(m['tags']) or '—'}")
            print(f"  {m['url']}")
        else:
            print(f"失败：{out['error']}", file=sys.stderr)
    return 0 if out["ok"] else 1


def cmd_book(args) -> int:
    src = SOURCES[args.source]
    outdir = os.path.abspath(args.outdir) if args.outdir else DEFAULT_OUTDIR
    try:
        result = fetch_book(src, args.book_id, args.from_, args.to, outdir)
    except (FetchError, OSError) as e:
        result = {"ok": False, "key": book_key(args.source, args.book_id),
                  "outdir": os.path.join(outdir, book_key(args.source, args.book_id)),
                  "downloaded": [], "failed": [], "chapter_total": 0,
                  "error": str(e)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        if result["ok"]:
            print(f"完成：{result['key']} 下载 {len(result['downloaded'])} 章 → {result['outdir']}")
        else:
            print(f"失败：{result.get('error')}", file=sys.stderr)
            if result["downloaded"]:
                print(f"  已下载 {len(result['downloaded'])} 章", file=sys.stderr)
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fetch.py", description="novel-study 采集层（番茄 / 天禧 / 起点榜单兜底）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="按书名搜索")
    s.add_argument("query")
    s.add_argument("--platform", default="all",
                   choices=["fanqie", "tianxi", "qidian", "all"])
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    i = sub.add_parser("info", help="取书籍元数据")
    i.add_argument("--source", required=True, choices=sorted(SOURCES))
    i.add_argument("--book-id", required=True)
    i.add_argument("--json", action="store_true")
    i.set_defaults(func=cmd_info)

    b = sub.add_parser("book", help="抓取指定章节范围")
    b.add_argument("--source", required=True, choices=sorted(SOURCES))
    b.add_argument("--book-id", required=True)
    b.add_argument("--from", dest="from_", type=int, default=1)
    b.add_argument("--to", dest="to", type=int, default=10)
    b.add_argument("--outdir", default=None)
    b.add_argument("--json", action="store_true")
    b.set_defaults(func=cmd_book)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        log("已中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
