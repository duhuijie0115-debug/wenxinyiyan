#Requires AutoHotkey v2.0
#SingleInstance Force
#Warn All, StdOut
#Include result_format.ahk
Persistent
SetWorkingDir(A_ScriptDir)
SendMode("Input")
SetKeyDelay(30, 30)

global Busy := false, Interrupted := false, LastResult := "", Job := 0
global Root := A_ScriptDir "\..", StateDir := A_ScriptDir "\state"
global Python := Root "\.venv\Scripts\pythonw.exe"
DirCreate(StateDir)
A_IconTip := "提示词优化：Ctrl+Alt+O`n粘贴最近结果：Ctrl+Alt+P"
A_TrayMenu.Delete()
A_TrayMenu.Add("提示词优化 · Ctrl+Alt+O", (*) => Tip("选中文字后按 Ctrl+Alt+O"))
A_TrayMenu.Add("粘贴最近结果 · Ctrl+Alt+P", (*) => PasteLatest())
A_TrayMenu.Add("重新登录 WorkBuddy", (*) => Run('"' Python '" "' A_ScriptDir '\agent.py" --login', Root, "Hide"))
A_TrayMenu.Add("打开使用说明", (*) => Run('"' Root '\快捷键使用说明.md"'))
A_TrayMenu.Add()
A_TrayMenu.Add("退出（下次登录自动启动）", (*) => ExitApp(0))
global WatchInput := InputHook("V")
WatchInput.KeyOpt("{All}", "N")
WatchInput.OnKeyDown := (*) => MarkInterrupted()
OnExit(Cleanup)

^!o::BeginOptimize()
^!p::PasteLatest()
~*LButton::MarkInterrupted()
~*RButton::MarkInterrupted()
~*MButton::MarkInterrupted()
~*WheelUp::MarkInterrupted()
~*WheelDown::MarkInterrupted()

MarkInterrupted() {
    global Interrupted
    if Busy
        Interrupted := true
}

Tip(text) {
    TrayTip(text, "wenxinyiyan 提示词优化", 1)
}

RestoreClipboard(saved, sequence) {
    if DllCall("GetClipboardSequenceNumber", "UInt") = sequence
        A_Clipboard := saved
}

BeginOptimize() {
    global Busy, Interrupted, Job
    if Busy {
        Tip("正在优化，请稍候。")
        return
    }
    ; Release shortcut modifiers before synthesizing Ctrl+C.
    KeyWait("o")
    KeyWait("Ctrl")
    KeyWait("Alt")
    hwnd := WinExist("A")
    try control := ControlGetFocus("ahk_id " hwnd)
    catch
        control := ""
    saved := ClipboardAll()
    A_Clipboard := ""
    Send("^c")
    if !ClipWait(1) {
        sequence := DllCall("GetClipboardSequenceNumber", "UInt")
        RestoreClipboard(saved, sequence)
        Tip("未复制到文本。请先选中文字；管理员窗口需同等权限。")
        return
    }
    text := A_Clipboard
    sequence := DllCall("GetClipboardSequenceNumber", "UInt")
    RestoreClipboard(saved, sequence)
    if !Trim(text) || StrLen(text) > 16000 {
        Tip("请选择 1～16000 字符的文本。")
        return
    }
    token := A_TickCount "-" Random(100000, 999999)
    file := StateDir "\request-" token ".txt"
    try {
        FileAppend(text, file, "UTF-8-RAW")
        Run('"' Python '" "' A_ScriptDir '\agent.py" --worker "' file '"', Root, "Hide", &pid)
    } catch {
        if FileExist(file)
            FileDelete(file)
        Tip("后台启动失败，请检查工具目录和 Python 环境。")
        return
    }
    Job := {hwnd: hwnd, control: control, original: text, file: file,
            output: StrReplace(file, ".txt", ".out"), pid: pid, started: A_TickCount}
    Busy := true
    Interrupted := false
    WatchInput.Start()
    SetTimer(PollResult, 100)
}

PollResult() {
    global Busy, Interrupted, Job, LastResult
    if !Busy
        return
    if WinExist("A") != Job.hwnd
        Interrupted := true
    if !FileExist(Job.output) {
        if A_TickCount - Job.started > 80000 || !ProcessExist(Job.pid) {
            ; Atomic output can appear just after process termination; allow next tick.
            if A_TickCount - Job.started < 1500
                return
            FinishJob()
            Tip("后台未完成请求，原文保持不变，请重试。")
        }
        return
    }
    try payload := FileRead(Job.output, "UTF-8")
    catch
        return
    WatchInput.Stop()
    SetTimer(PollResult, 0)
    result := ParseWorkerOutput(payload)
    if !result.ok {
        Tip(result.text)
        FinishJob()
        return
    }
    LastResult := result.text
    if !Interrupted && WinExist("A") = Job.hwnd {
        try focus := ControlGetFocus("ahk_id " Job.hwnd)
        catch
            focus := ""
        if focus = Job.control {
            ; Re-copy to ensure the same selection still exists before replacing.
            saved := ClipboardAll()
            A_Clipboard := ""
            Send("^c")
            if ClipWait(0.8) && A_Clipboard = Job.original && WinExist("A") = Job.hwnd {
                A_Clipboard := LastResult
                Send("^v")
                FinishJob()
                return
            }
            sequence := DllCall("GetClipboardSequenceNumber", "UInt")
            RestoreClipboard(saved, sequence)
        }
    }
    A_Clipboard := LastResult
    Tip("优化完成，结果已复制到剪贴板。按 Ctrl+V 粘贴，或 Ctrl+Alt+P 粘贴最近结果。")
    FinishJob()
}

PasteLatest() {
    if !LastResult {
        Tip("还没有优化结果。")
        return
    }
    KeyWait("p")
    KeyWait("Ctrl")
    KeyWait("Alt")
    A_Clipboard := LastResult
    Send("^v")
}

FinishJob() {
    global Busy, Job
    WatchInput.Stop()
    SetTimer(PollResult, 0)
    for file in [Job.file, Job.output] {
        try FileDelete(file)
    }
    Busy := false
    Job := 0
}

Cleanup(*) {
    if Busy {
        try ProcessClose(Job.pid)
        FinishJob()
    }
}
