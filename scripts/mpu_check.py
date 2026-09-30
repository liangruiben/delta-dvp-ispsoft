# -*- coding: utf-8 -*-
"""导入 ISPSoft 之前的自检。把「导入才报错」变成「生成时就报错」。

检查项（都是踩过的坑）：
  1. 容器：能否解包、CRC 是否正确、重新打包是否一致
  2. 常量：``K1`` 这类带 K 前缀的写法会被 ISPSoft 当成变量 -> 错误码 240
  3. 标识符：每个操作数必须是 DVP 元件（X/Y/M/S/T/C/D/E/F + 数字）或纯数字常量
  4. LOCAL_VAR / VAR_EXTERN 必须为空（常量写数字就不需要声明）
  5. 不生成 END（ISPSoft 编译器自己加，手工输入报「无效指令」）
  6. 网络结构：TYPE=11(源操作数) 必须紧跟 TYPE=9(指令)/TYPE=10(比较)，再跟 TYPE=12/7
  7. 指令编号：SYMB 是否在已知 API_NUM 表里
  8. 计数：各指令条数（可与参考 IL 对照）

用法::

    python mpu_check.py program.mpu
    python mpu_check.py program.mpu --ref .\\src
"""

import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mpu_codec  # noqa: E402

DEVICE_RE = re.compile(r"^(X|Y|M|S|T|C|D|E|F)\d+$")
INT_RE = re.compile(r"^-?\d+$")
KNOWN_API = {28: "MOV", 62: "DADD", 66: "DSUB", 70: "DMUL", 76: "INC",
             130: "ZRST", 170: "DPLSY", 257: "TMR", 264: "STL", 265: "RET"}


def parse_networks(text):
    """把 POU 文本解析成 [{id, root:[node], out:[node]}, ...]"""
    nets = []
    for blk in re.findall(r"<NETWORK_START>(.*?)<NETWORK_END>", text, re.S):
        nid = re.search(r"NET_ID=(\d+)", blk)
        root = re.search(r"<ROOTLINK_START>(.*?)<ROOTLINK_END>", blk, re.S)
        out = re.search(r"<OUTLINK_START>(.*?)<OUTLINK_END>", blk, re.S)
        nets.append({
            "id": int(nid.group(1)) if nid else -1,
            "root": parse_nodes(root.group(1) if root else ""),
            "out": parse_nodes(out.group(1) if out else ""),
        })
    return nets


def parse_nodes(seg):
    nodes = []
    for blk in re.findall(r"\[LD_NODE\](.*?)\[END_LD_NODE\]", seg, re.S):
        t = re.search(r"TYPE=(\d+)", blk)
        n = {
            "type": int(t.group(1)) if t else -1,
            "dev": (re.search(r"DEV_NAME=([^\r\n]*)", blk) or [None, ""])[1]
                   if "DEV_NAME=" in blk else None,
            "symb": (re.search(r"SYMB=([^\r\n]*)", blk) or [None, None])[1],
            "api": int((re.search(r"API_NUM=(-?\d+)", blk) or [None, "0"])[1]),
            "vars": re.findall(r"VAR_NAME=([^\r\n]*)", blk),
            "lnk": None,
        }
        m = re.search(r"LNK_C=(\d+)\r?\nLNK_L=(\d+)", blk)
        if m:
            n["lnk"] = (int(m.group(1)), int(m.group(2)))
        nodes.append(n)
    return nodes


def check(path, ref=None):
    issues, warnings, notes = [], [], []
    with open(path, "rb") as f:
        blob = f.read()

    # --- 1. 容器 ---
    try:
        raw = mpu_codec.extract_bytes(path)
    except Exception as e:
        return ["[致命] 无法解包: %s" % e], [], []
    text = raw.decode("latin-1")
    repacked = mpu_codec.pack(raw, encoding=None)
    if mpu_codec.extract_bytes.__module__ and mpu_codec._parse_zip(repacked)[1] != raw:
        issues.append("重新打包后内容不一致，容器有问题")

    nets = parse_networks(text)
    notes.append("网络数 %d，POU 闭合 %s" % (len(nets), text.rstrip().endswith("</POU>")))

    # --- 2/3. 操作数检查 ---
    names = [v for v in re.findall(r"(?:VAR_NAME|DEV_NAME)=([^\r\n]+)", text) if v.strip()]
    bad_k = sorted({v for v in names if re.match(r"^[Kk]-?\d+$", v)})
    if bad_k:
        issues.append("下例常量带 K 前缀，ISPSoft 会当成变量（错误码 240）：%s"
                      % ", ".join(bad_k))
    unknown = sorted({v for v in names
                      if not DEVICE_RE.match(v) and not INT_RE.match(v)
                      and v not in ("STL", "RET", "TMR", "DPLSY", "MOV", "DADD",
                                    "DSUB", "DMUL", "INC", "ZRST")})
    if unknown:
        issues.append("下列操作数既不是 DVP 元件也不是数字常量，必须声明或改正：%s"
                      % ", ".join(unknown))

    # --- 4. 变量表 ---
    for tag in ("LOCAL_VAR", "VAR_EXTERN"):
        seg = re.search(r"<%s>(.*?)</%s>" % (tag, tag), text, re.S)
        if seg and seg.group(1).strip():
            warnings.append("%s 非空：%s" % (tag, seg.group(1).strip()[:80]))

    # --- 5. END ---
    if re.search(r"SYMB=END\r?\n", text):
        issues.append("文件里含 END，ISPSoft 会报「无效指令」（END 由编译器自动加）")

    # --- 6/7. 结构 + 编号 ---
    for n in nets:
        for role in ("root", "out"):
            ns = n[role]
            i = 0
            while i < len(ns):
                nd = ns[i]
                if nd["type"] == 11:
                    if i + 1 >= len(ns) or ns[i + 1]["type"] not in (9, 10):
                        issues.append("网络 %d 的 %s：TYPE=11 后未紧跟 TYPE=9/10"
                                      % (n["id"], role))
                        i += 1
                        continue
                    body = ns[i + 1]
                    if body["api"] not in KNOWN_API and body["api"] != -1:
                        warnings.append("网络 %d：未知 API_NUM=%s（SYMB=%s），"
                                        "需用真实样本校准" % (n["id"], body["api"], body["symb"]))
                    i += 1
                i += 1

    # --- 8. 计数 ---
    syms = Counter(re.findall(r"SYMB=([A-Z]+)", text))
    notes.append("指令统计：" + "  ".join("%s=%d" % (k, syms[k]) for k in sorted(syms)))
    notes.append("比较接点=%d  线圈 OUT=%d SET=%d RST=%d"
                 % (text.count("TYPE=10\r\n"), text.count("TYPE=13\r\n"),
                    text.count("TYPE=15\r\n"), text.count("TYPE=16\r\n")))

    if ref:
        files = [ref] if os.path.isfile(ref) else [
            os.path.join(ref, f) for f in sorted(os.listdir(ref)) if f.endswith(".il")]
        il, total = Counter(), 0
        for p in files:
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith(("#", ";", "//")):
                        il[line.split(",")[0].strip().upper()] += 1
                        total += 1

        def cnt(k):
            return len(re.findall(r"TYPE=%d\r?\n" % k, text))

        def s(*keys):
            return sum(il.get(k, 0) for k in keys)

        # 可以精确对上的项
        for label, want, got in [
                ("上升沿接点 LDP/ANDP", s("LDP", "ANDP", "ORP"), cnt(3)),
                ("OUT 线圈", il.get("OUT", 0), cnt(13)),
                ("SET", il.get("SET", 0), cnt(15)),
                ("RST", il.get("RST", 0), cnt(16)),
                ("比较接点", s("LD=", "LD<=", "LD>", "LD<",
                               "AND=", "AND<=", "AND>", "AND<"), cnt(10)),
        ]:
            if want != got:
                issues.append("%s 数量不符：IL=%d 生成=%d" % (label, want, got))

        for k in sorted(set(list(il) + list(syms))):
            if k == "END" or k in ("LD", "LDI", "LDP", "LDF", "AND", "ANI", "ANDP",
                                   "ANDF", "OR", "ORI", "ORP", "ORF", "OUT", "SET",
                                   "RST", "LD=", "LD<=", "LD>", "LD<", "AND=",
                                   "AND<=", "AND>", "AND<"):
                continue
            a, b = il.get(k, 0), syms.get(k, 0)
            if a != b:
                issues.append("指令 %s 数量不符：IL=%d 生成=%d" % (k, a, b))

        # 接点：常开 / 常闭 —— 注意 OR 与 LD/AND 共用同一组节点类型编码，
        # 所以同一极性的三类接点要合并统计（沿触发在上面已单独精确校验）。
        for label, want, got in [
                ("常开接点 LD+AND+OR", s("LD", "AND", "OR"), cnt(1)),
                ("常闭接点 LDI+ANI+ORI", s("LDI", "ANI", "ORI"), cnt(2)),
        ]:
            if got < want:
                issues.append("%s 偏少：IL=%d 生成=%d（可能有条件被漏掉）" % (label, want, got))
            elif got > want:
                notes.append("%s：IL=%d 生成=%d（分支拆网络导致的正常复制）"
                             % (label, want, got))

        # 并联接点：一个 TYPE=6 节点聚合 LNK_C-1 个并联支路
        or_block = 0
        for blk in re.findall(r"\[LD_NODE\]\r?\nTYPE=6\r?\n(.*?)\[END_LD_NODE\]", text, re.S):
            m = re.search(r"LNK_C=(\d+)", blk)
            if m:
                or_block += int(m.group(1)) - 1
        want_or = s("OR", "ORI", "ORP", "ORF")
        if or_block != want_or:
            issues.append("并联接点 OR 数量不符：IL=%d 生成=%d" % (want_or, or_block))

        notes.append("参考 IL 文件 %d 个，指令总数 = %d" % (len(files), total))
    return issues, warnings, notes


def main():
    ap = argparse.ArgumentParser(description="ISPSoft .mpu 导入前自检")
    ap.add_argument("mpu")
    ap.add_argument("--ref", help="参考 .il 文件或目录，用于核对各指令条数")
    a = ap.parse_args()
    issues, warns, notes = check(a.mpu, a.ref)
    print("== 自检: %s ==" % a.mpu)
    for n in notes:
        print("   · " + n)
    for w in warns:
        print("   [警告] " + w)
    for i in issues:
        print("   [错误] " + i)
    print()
    print("结论: %s" % ("通过，可以导入" if not issues else
                        "有 %d 处必须先修正" % len(issues)))
    raise SystemExit(1 if issues else 0)


if __name__ == "__main__":
    main()
