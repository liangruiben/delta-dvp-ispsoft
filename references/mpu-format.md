# ISPSoft `.mpu` 格式规范（实测）

> 来源：对 Delta ISPSoft（DVP 机型）导出的样本逐一逆向 + 用户实测反馈校准。
> 起点线索来自开源项目 `ahmetdumlupinarr/delta-ispsoft-codec`（MIT）。
> 所有条目均已在真实样本上验证，未验证的会明确标注。

## 1. 容器结构

```
[152 字节前缀] + [标准 ZIP 包]
```

### 1.1 前缀（152 字节，小端）

| 偏移 | 长度 | 内容 |
|---|---|---|
| 0x00 | 12 | 全 0 |
| 0x0C | 4 | `1020`（固定） |
| 0x10 | 4 | `8`（固定） |
| 0x14 | 128 | 全 0 |
| 0x94 | 4 | **ZIP 部分的字节长度** |

### 1.2 ZIP 包

* 只含 **一个** 条目，条目名固定为 `Unzipped.src`
* **ZipCrypto 加密**，口令是 ISPSoft 内置的固定值：`eL$@.i$-$TuP!D~`
  （**不是用户设的密码**；无论导出时是否勾选「保护选项」，都会加密 —— 已实测确认）
* 压缩方式 deflate，flags 实测为 `0x0003`（bit0 加密 + bit1 最大压缩）
* 条目内容是用 ANSI/GBK 写的**纯文本**，**CRLF** 换行

打包/解包直接用技能自带的 `scripts/mpu_codec.py`（纯 Python，无第三方依赖）。

## 2. 内部文本结构

```
<GroupPOUFolder><ProgramFolder><FolderContent>…</FolderContent></ProgramFolder></GroupPOUFolder>
<POU>
P_Name=Prog0
P_En_Eno=TRUE
P_Last_Chg=
P_type=0
P_Rtn_Type=
P_Lang=1
P_Step=0
P_Version=1.00
P_DeltaFB=FALSE
P_Security=
P_Active=TRUE
P_Priority=9999
P_DFBName=
(*

*)
<LOCAL_VAR>
</LOCAL_VAR>            ← 必须为空（常量写数字就无需声明）
<VAR_EXTERN>
</VAR_EXTERN>
<VAR_EXTERN_C>
</VAR_EXTERN_C>
<NETWORK_START>
<PROPERTIES_START>
NET_ID=1
NET_LABEL=
NET_ACTIVE=TRUE
NET_BOOKMARK=FALSE
NET_MODIFY=TRUE
NET_FOLD=FALSE
(*

*)
<PROPERTIES_END>
<ROOTLINK_START>
…输入侧（接点、比较）…
<ROOTLINK_END>
<OUTLINK_START>
…输出侧（线圈、应用指令）…
<OUTLINK_END>
<NETWORK_END>
…
</POU>
```

* `NET_MODIFY` 取 TRUE/FALSE 都能导入（自己生成的用 TRUE）。
* 每个网络 = 一条支路。**一个网络里只有一条从母线到输出的路径**。

## 3. 节点（`[LD_NODE] … [END_LD_NODE]`）

接点/线圈操作数用 `DEV_NAME=`，**应用指令的操作数用 `<VAR_NODE_S>` 包起来、写成 `VAR_NAME=`**。

| TYPE | 含义 | 字段 |
|---|---|---|
| 1 | 常开接点（LD / AND） | `DEV_NAME=X0` |
| 2 | 常闭接点（LDI / ANI） | `DEV_NAME=M1` |
| 3 | 上升沿（LDP / ANDP） | `DEV_NAME=X2` |
| 4 | 下降沿（LDF / ANDF） | `DEV_NAME=X2` |
| 6 | 并联聚合点 | `LNK_C=n+1`、`LNK_L=n`（n = 并联支路数） |
| 10 | 比较接点 | `SYMB=<运算符>`、`API_NUM=-1` |
| 11 | 应用指令的**源操作数** | `<VAR_NODE_S>` + 若干 `VAR_NAME=` |
| 9 | 应用指令本体 | `SYMB=助记符`、`DEV_NAME=`（空）、`API_NUM=n` |
| 12 | 应用指令的**目标操作数** | `<VAR_NODE_S>` + 若干 `VAR_NAME=` |
| 7 | 应用指令终止 | — |
| 13 | 输出线圈 OUT | `DEV_NAME=Y0` |
| 15 | SET | `DEV_NAME=M5` |
| 16 | RST | `DEV_NAME=M6` |
| 29 | 多输出聚合点 | `LNK_C=n`、`LNK_L=n-1`（n = 并联的输出个数） |

### 应用指令的固定 4 节点

```
[LD_NODE] TYPE=11  <VAR_NODE_S> VAR_NAME=S1 VAR_NAME=S2 <VAR_NODE_E> [END_LD_NODE]
[LD_NODE] TYPE=9   SYMB=DADD  DEV_NAME=  API_NUM=62                [END_LD_NODE]
[LD_NODE] TYPE=12  <VAR_NODE_S> VAR_NAME=D                        <VAR_NODE_E> [END_LD_NODE]
[LD_NODE] TYPE=7                                                   [END_LD_NODE]
```

**规律：`TYPE=11` 放源操作数 S，`TYPE=12` 放目标操作数 D。** 没有源操作数的指令（如 `INC`）
`TYPE=11` 就写空；没有目标操作数的（如 `TMR`、`ZRST`）`TYPE=12` 写空。
两个操作数都写空时只留 `TYPE=11` / `TYPE=12` 一行（没有 `<VAR_NODE_S>` 包裹）。

### 比较接点的 4 节点

```
[LD_NODE] TYPE=11  <VAR_NODE_S> VAR_NAME=D500 VAR_NAME=0 <VAR_NODE_E> [END_LD_NODE]
[LD_NODE] TYPE=10  SYMB==   DEV_NAME=  API_NUM=-1                    [END_LD_NODE]
[LD_NODE] TYPE=12                                                    [END_LD_NODE]
[LD_NODE] TYPE=7                                                     [END_LD_NODE]
```

运算符取自 `LD=` / `LD<=` / `LD>` / `LD<` / `AND=` / `AND<=` / `AND>` / `AND<` 的后半部分。

### 常量写法（关键）

**常量必须写纯数字**，不带 `K` 前缀：

| IL 里写 | 文件里写 |
|---|---|
| `K0` | `VAR_NAME=0` |
| `K1` | `VAR_NAME=1` |
| `K200` | `VAR_NAME=200` |

写成 `VAR_NAME=K1`，ISPSoft 会把它当成**变量名**去查声明，报
`错误代码 240 找不到变量K1的定义`。

## 4. ISPSoft 侧的 API 编号（实测）

**与台达官方手册的 API 编号不是同一套**，必须用本表 / 真实样本，不能查官方表。

| 指令 | API_NUM | 指令 | API_NUM |
|---|---|---|---|
| MOV | 28 | ZRST | 130 |
| DADD | 62 | DPLSY | 170 |
| DSUB | 66 | TMR | 257 |
| DMUL | 70 | STL | 264 |
| INC | 76 | RET | 265 |

`END` 在 ISPSoft 里是**无效指令**（编译器自动加），**不要生成**。

> 新指令（如 `DDIV` / `ALT` / `CALL`）的编号必须用一次真实导出样本校准后再加入
> `il2mpu.py` 的 `API_NUM` 表。

## 5. 未实测、需留意的点

* 计数器 `C`、32 位比较、`MC/MCR` 主控、子程序 `CALL/SRET` 的编码未验证。
* 符号表 CSV 的定时器类型是 `TIMER`（见 `ispsoft-symbol-csv.md`）。
* 不同 ISPSoft 版本可能微调，遇到新报错优先"取一份真实样本对照"。
