; delta-dvp-ispsoft 示例程序（演示各类指令如何编码）
; 每行一条指令：助记符,操作数1,操作数2,...
; 分号 / # / // 开头的行会被忽略

; --- 普通接点与线圈 ---
LD,M0
OUT,Y0

; --- 并联（OR）+ 串联 + 上升沿起新支路 ---
LD,M1
OR,M2
ANI,M3
OUT,M5
LDP,M4
OUT,M6

; --- 比较接点 + 16 位应用指令（常量写 K，生成时会转成纯数字） ---
LD=,D0,K10
MOV,K1,D2
LD,M10
AND>,D3,K5
OUT,M11

; --- 定时器（T200 是 10ms 时基）+ 定量脉冲输出 ---
LD,M20
TMR,T200,K10
LD,T200
DPLSY,D10,K100,Y0

; --- 一个条件驱动多个输出 ---
LD,M30
SET,M40
RST,M41

; --- 步进：STL / RET，注意 S2=K0 是连续输出 ---
STL,S0
LDI,M50
DPLSY,D12,K0,Y1
LD,X0
SET,M60
RST,S0
SET,S1
RET

; END 不生成（ISPSoft 编译器自动加）
