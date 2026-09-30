# -*- coding: utf-8 -*-
"""自检：不依赖 ISPSoft，验证「生成 -> 打包 -> 解包」整条链路。

    python tests/selftest.py

做四件事：
  1. 用 examples/demo.il 生成 .mpu
  2. 解包回来与源文本逐字节比对（往返一致）
  3. 用 Python 标准库 zipfile（独立实现）解密读取，交叉验证容器合法
  4. 跑 mpu_check 的导入前自检，要求 0 错误
"""

import io
import os
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import il2mpu          # noqa: E402
import mpu_check       # noqa: E402
import mpu_codec       # noqa: E402

EXAMPLES = os.path.join(ROOT, "examples")


def main():
    ok = True

    # --- 1. 生成 ---
    ins, files = il2mpu.parse_il([EXAMPLES])
    nets = il2mpu.split_nets(ins)
    text = il2mpu.build_pou(nets)
    tmp = os.path.join(tempfile.gettempdir(), "deltadvp_selftest.mpu")
    size = mpu_codec.pack_file(text, tmp)
    print("[1] 生成    : %d 条指令 -> %d 个网络 -> %d 字节" % (len(ins), len(nets), size))

    # --- 2. 往返一致 ---
    back = mpu_codec.extract_bytes(tmp)
    same = back == text.encode("latin-1")
    print("[2] 往返一致: %s" % ("OK" if same else "失败"))
    ok &= same

    # --- 3. 标准库交叉验证 ---
    with open(tmp, "rb") as f:
        blob = f.read()
    z = zipfile.ZipFile(io.BytesIO(blob))
    std = z.read(mpu_codec.ENTRY_NAME, pwd=mpu_codec.ZIP_PASSWORD)
    cross = std == back and z.namelist() == [mpu_codec.ENTRY_NAME]
    print("[3] 标准库交叉验证: %s（条目 %s）"
          % ("OK" if cross else "失败", z.namelist()))
    ok &= cross

    # --- 4. 导入前自检 ---
    issues, warns, notes = mpu_check.check(tmp, ref=EXAMPLES)
    print("[4] 自检    : %s" % ("OK" if not issues else "有 %d 处错误" % len(issues)))
    for n in notes:
        print("      · " + n)
    for w in warns:
        print("      [警告] " + w)
    for i in issues:
        print("      [错误] " + i)
    ok &= not issues

    print()
    print("结果: %s" % ("全部通过 ✓" if ok else "有失败项 ✗"))
    os.remove(tmp)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
