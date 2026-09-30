# delta-dvp-ispsoft

台达 DVP PLC（DVP-ES2/EX2 等）程序开发助手 + **ISPSoft `.mpu` 工程文件生成/解析工具**。

Delta DVP PLC programming helper and ISPSoft `.mpu` project file toolkit — generate a `.mpu`
that ISPSoft can load directly, instead of typing hundreds of instructions by hand.

---

## 这个项目解决什么问题

ISPSoft 导出/导入程序用的是 `.mpu`（`工具 → 导入/导出 → 导入程序`）。这个格式**闭源、没有公开规范**，
所以正常做法只有两条：在 ISPSoft 里一条一条手敲，或者干脆放弃。

本项目把 `.mpu` 的格式逆向清楚了，于是可以做到：

```
指令表(IL)  ──►  可导入的 .mpu   （一条命令，不用手录）
```

并且在生成阶段就做自检，把"导入才报错"变成"生成时就报错"。

> **不是绕过授权**。这里处理的始终是你**自己的**工程文件；内置口令只是 ISPSoft 用来封装
> 工程内容的容器口令（详见下方[说明](#说明与免责声明)）。

## 需要什么

* Python 3.8+（**无任何第三方依赖**，ZipCrypto 是纯 Python 实现）
* 台达 ISPSoft（DVP 机型）
* 可选：把它作为 Agent Skill 安装（见下）

## 快速开始

```bash
S=./scripts

# 1) 指令表(IL) -> .mpu
python $S/il2mpu.py --src ./examples --out demo.mpu --show

# 2) 导入前自检（这一步务必做）
python $S/mpu_check.py demo.mpu --ref ./examples

# 3) 反向：看看某个 .mpu 里到底是什么逻辑
python $S/mpu2il.py demo.mpu          # 按网络列出「条件 -> 输出」
python $S/mpu2il.py demo.mpu --raw    # 原始内部文本

# 4) 直接读写 .mpu（当库用）
python $S/mpu_codec.py demo.mpu
```

`il2mpu.py` 输出的文件，在 ISPSoft 里用
**`工具 → 导入/导出 → 导入程序`** 载入即可（**新建/已有项目里都要先有 POU**，
否则会报"周期工作必须指派一个以上的POU"）。

### IL 输入格式

每行一条指令，`助记符,操作数1,操作数2,…`：

```
LD,M51
ANI,M30
TMR,T201,K1
LD,T201
DPLSY,D46,D12,Y0
STL,S0
RET
```

## 工具一览

| 脚本 | 作用 |
|---|---|
| `scripts/mpu_codec.py` | `.mpu` 容器读写：152 字节前缀 + ZipCrypto 加密 ZIP，含 CRC 与往返自检 |
| `scripts/il2mpu.py` | 指令表 → `.mpu`（自动切分梯形图网络、自动拆分支） |
| `scripts/mpu2il.py` | `.mpu` → 可读网络清单 / 扁平 IL |
| `scripts/mpu_check.py` | 导入前自检：常量写法、未声明标识符、结构、指令计数对照 |

## 已验证的事实（不是照手册猜的）

| 项 | 结论 |
|---|---|
| 容器 | `[152 字节前缀] + [标准 ZIP（单条目 Unzipped.src，ZipCrypto 加密）]`，前缀 0x94 处 = ZIP 长度 |
| 内部 | **纯文本**（GBK/ANSI，CRLF），标签式结构：`<POU>` / `<NETWORK_START>` / `[LD_NODE]` |
| 节点编码 | 接点 1/2/3/4、并联聚合 6、比较 10、应用指令 11→9→12→7、线圈 13/15/16、多输出聚合 29 |
| 常量 | **必须写纯数字**：`K1` → `VAR_NAME=1`，写成 `K1` 报 `错误码 240 找不到变量K1的定义` |
| `END` | **不要生成**，编译器自动加（手工输入被判"无效指令"） |
| API 编号 | **ISPSoft 自成一套，与台达官方手册不同**：MOV=28、DADD=62、DSUB=66、DMUL=70、INC=76、ZRST=130、DPLSY=170、TMR=257、STL=264、RET=265 |

细节见 [`references/`](references/)：

* [`mpu-format.md`](references/mpu-format.md) —— 完整格式规范与节点表
* [`il-to-network.md`](references/il-to-network.md) —— IL 切分网络规则、错误码速查
* [`dvp-conventions.md`](references/dvp-conventions.md) —— `DPLSY` 取数顺序、完成标志、定时器时基、D 保持区
* [`ispsoft-symbol-csv.md`](references/ispsoft-symbol-csv.md) —— 符号表 CSV 格式

## 作为 Agent Skill 安装

仓库根目录就是技能目录，克隆到位即可被自动发现：

```bash
# WorkBuddy / CodeBuddy
git clone https://github.com/liangruiben/delta-dvp-ispsoft ~/.workbuddy/skills/delta-dvp-ispsoft

# Claude Code 等使用 ~/.claude/skills 的环境
git clone https://github.com/liangruiben/delta-dvp-ispsoft ~/.claude/skills/delta-dvp-ispsoft
```

之后直接用自然语言提问即可（"帮我把这份指令表生成 ISPSoft 工程"、"这个 .mpu 报错 240 怎么改"），
技能会带上 [`SKILL.md`](SKILL.md) 里的完整工作流和硬规则。

## 自检

```bash
python tests/selftest.py
```

会生成一个示例工程、打包、解包比对，并额外用 Python 标准库 `zipfile` 做**独立实现交叉验证**。

## 已知边界

* 只收录了**实测过**的指令（上表 10 条 + 接点/线圈/比较）。遇到新指令（如 `DDIV` / `ALT` / 计数器）
  请按 [`SKILL.md`](SKILL.md)「扩展新指令时」的流程取一次真实样本校准，**不要猜编号**。
* 面向上表机型（DVP-ES2/EX2 等，ISPSoft 里只有「梯形图 / SFC」两种语言的机型）。
* 生成的只是**程序 POU**。机型、脉冲输出模式、任务指派、符号表等属于工程级设置，需在 ISPSoft 里配。
* 未经 ISPSoft 编译验证前不要直接下装到运行中的设备 —— 这毕竟是运动控制程序。

## 说明与免责声明

* **格式来源**：`.mpu` 的容器结构与固定口令最初由开源项目
  [`ahmetdumlupinarr/delta-ispsoft-codec`](https://github.com/ahmetdumlupinarr/delta-ispsoft-codec)（MIT）
  逆向并公开；本项目在其基础上补齐了**内部节点编码、API 编号表、比较接点、网络切分规则**，
  并用真实导出样本逐条校准（含用户实测反馈），且把打包改为**纯 Python 实现**，去掉了对 7z 的依赖。
* **用途**：仅用于读写**你自己**的 ISPSoft 工程，属于互操作性用途。**不用于**绕过任何授权或保护机制。
* **不是官方工具**，与 Delta Electronics 无关联。ISPSoft / DVP 是台达的商标。
* 使用本工具生成的程序在下载到设备前，请自行在 ISPSoft 中编译并核对；
  作者不对设备损坏或人身伤害承担责任。

## 许可

MIT，见 [LICENSE](LICENSE)。
