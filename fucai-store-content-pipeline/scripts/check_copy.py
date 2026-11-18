#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""口播稿合规与格式校验（福彩门店内容流水线 SKILL v1.0）

用法：
    python check_copy.py 口播稿.txt [--cover 八个字的封面文案]

校验项：
    1. 正文字数是否 70-95 字
    2. 四段时间标注是否齐全（0-3 钩子 / 3-8 知识点 / 8-12 提醒 / 12-15 到店咨询）
    3. 字幕每行是否 <=12 字（按文件换行断句）
    4. 封面是否正好 8 字
    5. 禁用词 / 导流交易类表述是否命中
    6. 是否以「理性购彩，量力而行」收尾
    7. 是否含数字金额（需人工确认口径或标【待核对】）

退出码：0 = 通过（可能有提醒），1 = 存在必须修改的硬错误。
"""

import argparse
import re
import sys
from pathlib import Path

BANNED = [
    "必中", "稳赚", "包中", "翻倍", "大奖", "必出", "秘籍", "包赔",
    "专家", "内部", "官方授权", "加注", "倍投", "回本",
    # 五类违规表述的高频变体
    "稳赚不亏", "中奖率", "内部消息", "内部号", "专家推荐", "官方合作",
    "多买多中", "趁活动多囤", "先票后款", "垫资", "记账", "代购", "代刮", "代兑",
]

TRAFFIC = [
    "微信号", "加微信", "加我微信", "微信转账", "扫码", "二维码", "收款码",
    "私信我", "私聊", "转账", "线上买", "线上购", "网售", "加群", "进群",
    "后台下单", "线上下单", "赊销", "赊账",
]

SEGMENTS = [
    ("0–3 秒", "钩子"),
    ("3–8 秒", "知识点"),
    ("8–12 秒", "提醒"),
    ("12–15 秒", "到店咨询"),
]

ENDING = "理性购彩，量力而行"


def char_count(text: str) -> int:
    """按「字」计数：统计字母/数字/汉字，忽略标点与空白。"""
    return sum(1 for c in text if c.isalnum())


MARKER_RE = re.compile(r"\d+\s*[–\-~至]\s*\d+\s*秒\s*(?:钩子|知识点|提醒|到店咨询)?\s*[：:]?")


def clean_lines(content: str) -> list[str]:
    """去掉段标题行（以【开头）与「0–3 秒 钩子：」类时间标注，只留正文句。"""
    out = []
    for ln in content.splitlines():
        s = ln.strip()
        if not s or s.startswith("【"):
            continue
        s = MARKER_RE.sub("", s).strip()
        if s:
            out.append(s)
    return out


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法识别文件编码，请另存为 UTF-8：{path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="福彩口播稿合规校验")
    ap.add_argument("file", help="口播稿文本文件路径（UTF-8）")
    ap.add_argument("--cover", default="", help="封面文案，校验是否正好 8 字")
    ap.add_argument("--min", type=int, default=70, help="正文字数下限，默认 70")
    ap.add_argument("--max", type=int, default=95, help="正文字数上限，默认 95")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"❌ 文件不存在：{path}")
        return 1

    content = read_text(path)
    body_lines = clean_lines(content)
    body = "\n".join(body_lines) if body_lines else content
    errors, warns, notes = [], [], []

    # 1. 字数（只算正文，剔除段标题与时间标注）
    count = char_count(body)
    if count < args.min or count > args.max:
        errors.append(f"正文 {count} 字，不在 {args.min}-{args.max} 字区间")
    else:
        notes.append(f"正文 {count} 字，符合 {args.min}-{args.max}")

    # 2. 四段标注
    flat = content.replace(" ", "")
    missing = [f"{t} {label}" for t, label in SEGMENTS if label not in flat]
    if missing:
        errors.append("缺少时间标注：" + "、".join(missing))
    else:
        notes.append("四段时间标注齐全")

    # 3. 字幕断句（按换行）
    lines = body_lines
    if len(lines) <= 1:
        warns.append("文件只有一行，无法校验字幕断句；请按每行一句≤12 字重新排版后再检查")
    else:
        bad = [(i + 1, char_count(ln), ln) for i, ln in enumerate(lines) if char_count(ln) > 12]
        if bad:
            for no, n, ln in bad:
                errors.append(f"第 {no} 行 {n} 字，超过 12 字：{ln}")
        else:
            notes.append(f"{len(lines)} 行字幕，全部 ≤12 字")

    # 4. 封面
    if args.cover:
        cc = char_count(args.cover)
        if cc != 8:
            errors.append(f"封面「{args.cover}」为 {cc} 字，必须正好 8 字")
        else:
            notes.append("封面正好 8 字")

    # 5. 禁用词 / 导流
    hits = [w for w in BANNED if w in body]
    if hits:
        errors.append("命中禁用词：" + "、".join(sorted(set(hits))))
    traffic = [w for w in TRAFFIC if w in body]
    if traffic:
        errors.append("命中导流/交易类表述：" + "、".join(sorted(set(traffic))))
    if not hits and not traffic:
        notes.append("禁用词与导流表述零命中")

    # 6. 结尾口径
    flat_body = re.sub(r"[\s。.！!，,；;]", "", body)
    flat_ending = re.sub(r"[\s。.！!，,；;]", "", ENDING)
    if flat_body[-len(flat_ending):] != flat_ending:
        errors.append(f"未以「{ENDING}」收尾（当前结尾：…{body.strip()[-14:]}）")
    else:
        notes.append(f"结尾含「{ENDING}」")

    # 7. 数字金额
    if re.search(r"\d", body):
        warns.append("含阿拉伯数字：确认是官方口径，或改为【待核对】后发布")

    # 8. 未成年人
    if re.search("未成年|学生|小学生|中学生|儿童|孩子", body):
        warns.append("含未成年人相关词：仅可用于「不向未成年人售彩/兑奖」的正向表述，逐句核对")

    print(f"\n=== 校验：{path.name} ===")
    for n in notes:
        print(f"✅ {n}")
    for w in warns:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}")
    print("\n结果：" + ("不通过，请改稿后重跑" if errors else "通过（提醒项仍需人工确认）"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
